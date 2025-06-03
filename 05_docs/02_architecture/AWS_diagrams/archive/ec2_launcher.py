import boto3
import botocore

# ----- CONFIG -----
REGION = "eu-central-1"
AMI_ID = "ami-05f7491af5eef733a"  # Ubuntu 22.04 LTS (Frankfurt)
INSTANCE_TYPE = "t2.micro"
KEY_NAME = "gptrusbeh-key"
SECURITY_GROUP_NAME = "gptrusbeh-sg"
TAG_NAME = "gptrusbeh-test-instance"

# ----- Set up client -----
ec2 = boto3.client("ec2", region_name=REGION)

# ----- Step 1: Create security group if it doesn't exist -----
def ensure_security_group():
    try:
        resp = ec2.describe_security_groups(GroupNames=[SECURITY_GROUP_NAME])
        return resp['SecurityGroups'][0]['GroupId']
    except botocore.exceptions.ClientError as e:
        if "InvalidGroup.NotFound" in str(e):
            vpc_id = ec2.describe_vpcs()['Vpcs'][0]['VpcId']
            resp = ec2.create_security_group(
                GroupName=SECURITY_GROUP_NAME,
                Description="Allow SSH",
                VpcId=vpc_id
            )
            gid = resp['GroupId']
            ec2.authorize_security_group_ingress(
                GroupId=gid,
                IpPermissions=[{
                    'IpProtocol':'tcp',
                    'FromPort':22,
                    'ToPort':22,
                    'IpRanges':[{'CidrIp':'0.0.0.0/0'}]
                }]
            )
            return gid
        raise

# ----- Step 2: Launch EC2 instance -----
def launch_instance():
    sg_id = ensure_security_group()
    resp = ec2.run_instances(
        ImageId=AMI_ID,
        InstanceType=INSTANCE_TYPE,
        KeyName=KEY_NAME,
        MinCount=1,
        MaxCount=1,
        SecurityGroupIds=[sg_id],
        TagSpecifications=[{
            'ResourceType':'instance',
            'Tags':[{'Key':'Name','Value':TAG_NAME}]
        }]
    )
    iid = resp['Instances'][0]['InstanceId']
    print(f"Launched: {iid}")
    ec2.get_waiter('instance_running').wait(InstanceIds=[iid])
    ip = ec2.describe_instances(InstanceIds=[iid])['Reservations'][0]['Instances'][0].get('PublicIpAddress','N/A')
    print(f"Running; IP: {ip}")
    return iid

# ----- Step 3: List all non-terminated instances -----
def list_all_instances():
    resp = ec2.describe_instances(
        Filters=[{'Name':'instance-state-name','Values':['pending','running','stopping','stopped']}]
    )
    ids = []
    print("\nYour instances:")
    for r in resp['Reservations']:
        for inst in r['Instances']:
            iid = inst['InstanceId']
            state = inst['State']['Name']
            ip = inst.get('PublicIpAddress','N/A')
            print(f"- {iid}: {state}, IP: {ip}")
            ids.append(iid)
    if not ids:
        print("  (none)")
    return ids

# ----- Step 4: Terminate given instances -----
def terminate_instances(iids):
    if not iids:
        return
    print("\nTerminating instances...")
    ec2.terminate_instances(InstanceIds=iids)
    ec2.get_waiter('instance_terminated').wait(InstanceIds=iids)
    print("Instances terminated.")

# ----- Step 5: Delete volumes of terminated instances -----
def delete_volumes_for_instances(iids):
    for iid in iids:
        mappings = ec2.describe_instances(InstanceIds=[iid])['Reservations'][0]['Instances'][0]['BlockDeviceMappings']
        for bd in mappings:
            vol_id = bd['Ebs']['VolumeId']
            try:
                print(f"Deleting volume {vol_id}...")
                ec2.delete_volume(VolumeId=vol_id)
            except botocore.exceptions.ClientError as e:
                print(f"  Could not delete volume {vol_id}: {e}")

# ----- Step 6: Delete security group -----
def delete_security_group():
    try:
        print(f"\nDeleting security group '{SECURITY_GROUP_NAME}'...")
        ec2.delete_security_group(GroupName=SECURITY_GROUP_NAME)
        print("Security group deleted.")
    except botocore.exceptions.ClientError as e:
        print(f"  Could not delete security group: {e}")

# ----- Step 7: Delete key pair -----
def delete_key_pair():
    try:
        print(f"\nDeleting key pair '{KEY_NAME}'...")
        ec2.delete_key_pair(KeyName=KEY_NAME)
        print("Key pair deleted.")
    except botocore.exceptions.ClientError as e:
        print(f"  Could not delete key pair: {e}")

# ----- MAIN -----
if __name__ == "__main__":
    launch_instance()
    all_ids = list_all_instances()
    choice = input("\nDo you want to DELETE ALL resources (terminate, delete volumes, SG, key)? (yes/no): ").strip().lower()
    if choice in ('yes','y'):
        terminate_instances(all_ids)
        delete_volumes_for_instances(all_ids)
        list_all_instances()
    else:
        print("Cleanup skipped; resources remain.")
