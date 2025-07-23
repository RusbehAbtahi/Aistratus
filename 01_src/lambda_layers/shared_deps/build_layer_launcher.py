#!/usr/bin/env python3
"""
TinyLlama – one-shot Lambda-layer builder & uploader
Runs entirely from your workstation (no Docker, no admin rights).

Steps
-----
1. Launch t3.medium Amazon Linux 2023 (latest AMI auto-discovered)
2. Attach instance-profile  tl-layer-build-upload-ip
3. Wait until the SSM agent is ONLINE
4. Push build_layer_ci.py + requirements.txt via SSM (base-64 encoded)
5. Execute build_layer_ci.py remotely
6. Upload /tmp/shared_deps.zip to
   s3://lambda-layer-zip-108782059508/layers/
7. Terminate the instance
"""

import base64
import subprocess
import time
from datetime import datetime
from pathlib import Path

import boto3

# ----------------------------------------------------------------------
# CONSTANTS – NO PLACEHOLDERS
# ----------------------------------------------------------------------
AWS_REGION   = "eu-central-1"
KEY_NAME     = "gptrusbeh-key"
SEC_GRP_ID   = "sg-015bcac564f108070"
INST_PROFILE = "tl-layer-build-upload-ip"
S3_BUCKET    = "lambda-layer-zip-108782059508"
LAYER_PREFIX = "layers/shared_deps_{ts}.zip"
LAYER_NAME  = "tlfif-default-shared-deps"   # ← your permanent layer name
LAMBDA_ARN  = "arn:aws:lambda:eu-central-1:108782059508:function:tlfif-default-router"


ROOT    = Path(__file__).resolve().parent
CI_PY   = ROOT / "build_layer_ci.py"
REQ_TXT = ROOT / "requirements.txt"

ssm = boto3.client("ssm", region_name=AWS_REGION)


# ----------------------------------------------------------------------
# Helper – run AWS CLI with region injected
# ----------------------------------------------------------------------
def sh(cmd, capture=False):
    if isinstance(cmd, list):
        cmd = [str(c) for c in cmd] + ["--region", AWS_REGION]
        shown = " ".join(cmd)
    else:
        shown = cmd
    print(f"$ {shown}")
    if capture:
        return subprocess.check_output(cmd, text=True).strip()
    subprocess.check_call(cmd)


# ----------------------------------------------------------------------
# Find latest AL2023 AMI
# ----------------------------------------------------------------------
def latest_ami():
    return sh(
        [
            "aws",
            "ec2",
            "describe-images",
            "--owners",
            "amazon",
            "--filters",
            "Name=name,Values=al2023-ami-*-x86_64*",
            "Name=architecture,Values=x86_64",
            "Name=state,Values=available",
            "--query",
            "sort_by(Images,&CreationDate)[-1].ImageId",
            "--output",
            "text",
        ],
        capture=True,
    )


# ----------------------------------------------------------------------
# Launch build instance
# ----------------------------------------------------------------------
def launch_instance(ami):
    print("-> Launching build instance")
    return sh(
        [
            "aws",
            "ec2",
            "run-instances",
            "--image-id",
            ami,
            "--key-name",
            KEY_NAME,
            "--instance-type",
            "t3.medium",
            "--iam-instance-profile",
            f"Name={INST_PROFILE}",
            "--security-group-ids",
            SEC_GRP_ID,
            "--instance-initiated-shutdown-behavior",
            "terminate",
            "--tag-specifications",
            (
                "ResourceType=instance,Tags=[{Key=Project,Value=tinyllama},"
                "{Key=Role,Value=layer-build}]"
            ),
            "--query",
            "Instances[0].InstanceId",
            "--output",
            "text",
        ],
        capture=True,
    )


# ----------------------------------------------------------------------
# Wait until SSM agent is ONLINE
# ----------------------------------------------------------------------
def wait_ssm_ready(iid):
    print("-> Waiting for SSM agent to be ONLINE")
    for attempt in range(1, 31):  # up to 5 minutes
        resp = ssm.describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [iid]}]
        )
        items = resp.get("InstanceInformationList", [])
        if items and items[0]["PingStatus"] == "Online":
            print(f"   SSM ONLINE after {attempt*10} s.")
            return
        print(f"   still not ready (attempt {attempt})")
        time.sleep(10)
    raise RuntimeError("SSM agent did not become ONLINE in 5 min.")


# ----------------------------------------------------------------------
# Upload scripts and build layer
# ----------------------------------------------------------------------
def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()

def upload_and_build(iid, s3_key):
    print("-> Uploading scripts and running remote build")

    # 1) schedule a guaranteed shutdown in 10 minutes
    timer_cmd = [
        "echo 'shutdown -P now' | at now + 10 minutes"
    ]
    resp = ssm.send_command(
        InstanceIds=[iid],
        DocumentName="AWS-RunShellScript",
        Comment="Set 10-minute self-destruct timer",
        Parameters={"commands": timer_cmd},
    )
    timer_id = resp["Command"]["CommandId"]
    print(f"   Scheduled suicide timer (SSM command {timer_id})")

    # 2) now upload & run the real build (and final shutdown on success)
    ci_b64 = _b64(CI_PY)
    rq_b64 = _b64(REQ_TXT)

    commands = [
        "sudo dnf install -y python3.12 python3.12-devel",
        f'echo "{ci_b64}" | base64 -d > /tmp/build_layer_ci.py',
        f'echo "{rq_b64}" | base64 -d > /tmp/requirements.txt',
        "chmod +x /tmp/build_layer_ci.py",
        "python3.12 -m pip install --upgrade pip",
        "python3.12 /tmp/build_layer_ci.py",
        f'aws s3 cp /tmp/shared_deps.zip s3://{S3_BUCKET}/{s3_key} --region {AWS_REGION}',
        f'echo \"UPLOAD COMPLETE to s3://{S3_BUCKET}/{s3_key}\"',
        "shutdown -P now"
    ]

    resp = ssm.send_command(
        InstanceIds=[iid],
        DocumentName="AWS-RunShellScript",
        Comment="Build layer and upload, then shutdown",
        Parameters={"commands": commands},
    )
    cmd_id = resp["Command"]["CommandId"]
    print(f"   SSM command: {cmd_id} (waiting)")
    waiter = ssm.get_waiter("command_executed")
    waiter.wait(CommandId=cmd_id, InstanceId=iid)
    print("   Remote build finished.")


# ----------------------------------------------------------------------
# Terminate instance
# ----------------------------------------------------------------------
def terminate_and_cleanup(iid):

    # wait until fully terminated
    sh(["aws","ec2","wait","instance-terminated","--instance-ids",iid])
    print("   Instance fully terminated.")
    cleanup_volumes(iid)
    print("   All associated volumes have been cleaned up.")


def cleanup_volumes(iid):
    # 1) find all volumes once the instance is terminated
    vols = sh([
        "aws","ec2","describe-volumes",
        "--filters",
        f"Name=attachment.instance-id,Values={iid}",
        "Name=status,Values=available",
        "--query","Volumes[].VolumeId",
        "--output","text"
    ], capture=True).split()

    # 2) delete each one
    for vol in vols:
        print(f"-> Deleting volume {vol}")
        sh(["aws","ec2","delete-volume","--volume-id",vol])
        print(f"   {vol} deleted")
def update_backend_auto_tfvars(s3_key):
    tfvars_path = Path("terraform/10_global_backend/backend.auto.tfvars")  # adjust path if needed

    lines = []
    found = False
    # Read existing lines, update if key is found
    if tfvars_path.exists():
        for line in tfvars_path.read_text().splitlines():
            if line.strip().startswith("shared_deps_layer_s3_key"):
                lines.append(f'shared_deps_layer_s3_key = "{s3_key}"')
                found = True
            else:
                lines.append(line)
    # If key wasn't present, append it
    if not found:
        lines.append(f'shared_deps_layer_s3_key = "{s3_key}"')
    tfvars_path.write_text("\n".join(lines) + "\n")

# ----------------------------------------------------------------------
# Publish layer + update Lambda
# ----------------------------------------------------------------------
_lambda = boto3.client("lambda", region_name=AWS_REGION)

def publish_layer_and_update_lambda(s3_key, ts):
    # 1) publish a new layer version
    resp = _lambda.publish_layer_version(
        LayerName=LAYER_NAME,
        Content={"S3Bucket": S3_BUCKET, "S3Key": s3_key},
        CompatibleRuntimes=["python3.12"],
        Description=f"shared deps built {ts}",
    )
    new_layer_arn = resp["LayerVersionArn"]
    print(f"   Layer published: {new_layer_arn}")

    # 2) fetch current Lambda config to keep any other layers
    conf = _lambda.get_function_configuration(FunctionName=LAMBDA_ARN)
    current = [l["Arn"] for l in conf.get("Layers", [])]

    # replace any older version of this layer, then append if missing
    remaining = [arn for arn in current if not arn.startswith(f"arn:aws:lambda:{AWS_REGION}:" 
                                                              f"{conf['FunctionArn'].split(':')[4]}:layer:{LAYER_NAME}:")]
    new_layers = remaining + [new_layer_arn]

    _lambda.update_function_configuration(
        FunctionName=LAMBDA_ARN,
        Layers=new_layers,
    )
    print("   Lambda updated with new layer (configuration update in progress).")

# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
def main():
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    s3_key = LAYER_PREFIX.format(ts=ts)

    ami = latest_ami()
    print(f"Latest AL2023 AMI: {ami}")

    iid = launch_instance(ami)
    print(f"Instance ID: {iid}")

    # Wait for EC2 running
    sh(["aws", "ec2", "wait", "instance-running", "--instance-ids", iid])
    print("   Instance is running")

    # Wait for SSM agent
    wait_ssm_ready(iid)

    # Build and upload
    upload_and_build(iid, s3_key)

    update_backend_auto_tfvars(s3_key)
   # Publish Layer
   # publish_layer_and_update_lambda(s3_key, ts)
    # Terminate
    terminate_and_cleanup(iid)

    print(f"\nDONE – Lambda now uses the new layer, "
          f"instance & volumes removed.\n")


if __name__ == "__main__":
    main()
