#!/usr/bin/env python
"""
Minimal, admin-free replacement for the old Makefile.

Commands
--------
python tools.py lambda-package        # build router.zip
python tools.py tf-apply              # build + terraform init/apply
python tools.py lambda-rollback --version 17
"""
from __future__ import annotations
import argparse
import shutil
import subprocess as sp
import sys
import zipfile
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths – adjust only if your repo layout changes
# --------------------------------------------------------------------------- #
REPO_ROOT      = Path(__file__).resolve().parent
SRC_ROOT       = REPO_ROOT / "01_src"
ZIP_OUT        = REPO_ROOT / "router.zip"
TERRAFORM_DIR  = REPO_ROOT / "terraform" / "10_global_backend"
LOCAL_TF_BIN   = REPO_ROOT / "04_scripts" / "no_priv" / "tools" / "terraform"
ROLLBACK_SH    = REPO_ROOT / "04_scripts" / "no_priv" / "rollback_router.sh"
ZIP_SIZE_LIMIT = 5 * 1024 * 1024       # 5 MiB Lambda limit

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def safe_print(text: str) -> None:
    """Prints without bombing on code-page issues (cp1252, etc.)."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode())

def run(cmd: list[str] | str, cwd: Path | None = None) -> None:
    """Run a command and abort if it fails."""
    printable = cmd if isinstance(cmd, str) else " ".join(cmd)
    safe_print(f"[RUN] {printable}")
    proc = sp.Popen(cmd, cwd=cwd, shell=False)
    proc.communicate()
    if proc.returncode:
        sys.exit(proc.returncode)

def add_tree(zf: zipfile.ZipFile, root: Path, arc_prefix: str) -> None:
    """Zip an entire directory tree under a fixed archive prefix."""
    for f in root.rglob("*"):
        if f.is_dir():
            continue
        if "__pycache__" in f.parts or f.suffix == ".pyc":
            continue
        zf.write(f, Path(arc_prefix) / f.relative_to(root))

def terraform_bin() -> str:
    """
    Return the Terraform binary path to use.
    1) whatever 'terraform' resolves to on PATH
    2) repo-local fallback binary
    """
    global_tf = shutil.which("terraform")
    if global_tf:
        safe_print(f"[INFO] Using global terraform -> {global_tf}")
        return global_tf
    if LOCAL_TF_BIN.exists():
        safe_print(f"[INFO] Using repo-local terraform -> {LOCAL_TF_BIN}")
        return str(LOCAL_TF_BIN)
    safe_print(
        "ERROR: terraform not found on PATH and local fallback binary "
        f"does not exist ({LOCAL_TF_BIN})."
    )
    sys.exit(1)

# --------------------------------------------------------------------------- #
# Tasks
# --------------------------------------------------------------------------- #
def lambda_package() -> None:
    router_dir = SRC_ROOT / "tinyllama" / "router"
    utils_dir  = SRC_ROOT / "tinyllama" / "utils"

    for p in (router_dir, utils_dir):
        if not p.exists():
            safe_print(f"ERROR: required path missing – {p}")
            sys.exit(1)

    with zipfile.ZipFile(ZIP_OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("tinyllama/__init__.py", "# package marker\n")
        add_tree(zf, router_dir, "tinyllama/router")
        add_tree(zf, utils_dir,  "tinyllama/utils")

    size = ZIP_OUT.stat().st_size
    if size > ZIP_SIZE_LIMIT:
        ZIP_OUT.unlink(missing_ok=True)
        safe_print(f"ERROR: {ZIP_OUT.name} is {(size/1024):,.0f} KiB (> 5 MiB)")
        sys.exit(1)

    safe_print(f"OK   : created {ZIP_OUT}  {(size/1024):,.0f} KiB")

def tf_apply() -> None:
    tf = terraform_bin()          # resolve binary
    lambda_package()              # always rebuild first

    # ----- locate backend.auto.tfvars wherever it really is -------------
    backend_cfg = REPO_ROOT / "terraform" / "backend.auto.tfvars"
    init_cmd = [tf, "init"]
    if backend_cfg.exists():
        init_cmd += [f"-backend-config={backend_cfg}"]
    else:
        safe_print(f"[WARN] {backend_cfg} not found – running terraform init with workspace-defaults")

    # --------------------------------------------------------------------
    run(init_cmd, cwd=TERRAFORM_DIR)
    run([tf, "apply", "-auto-approve"], cwd=TERRAFORM_DIR)
    safe_print("OK   : terraform apply finished")
    update_env_public_with_api_url()

def lambda_rollback(version: str) -> None:
    import subprocess, sys
    FN = "tinyllama-router"
    # verify version is numeric
    if not version.isdigit():
        print("ERROR: --version must be an integer (Lambda numeric version)")
        sys.exit(1)
    # call AWS CLI to update alias 'prod' to this version
    cmd = [
        "aws", "lambda", "update-alias",
        "--function-name", FN,
        "--name", "prod",
        "--function-version", version,
        "--region", "eu-central-1"
    ]
    print(f"[RUN] {' '.join(cmd)}")
    proc = subprocess.Popen(cmd)
    proc.communicate()
    if proc.returncode:
        sys.exit(proc.returncode)
    print(f"Rolled back tinyllama-router to version {version}")

def update_env_public_with_api_url():
    import json
    import subprocess

    tf_output_cmd = [
        terraform_bin(), "output", "-json"
    ]
    proc = subprocess.run(
        tf_output_cmd,
        cwd=TERRAFORM_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    outputs = json.loads(proc.stdout)
    # Extract router_api_url from inside global_ids
    api_url = outputs["global_ids"]["value"]["router_api_url"]

    env_path = REPO_ROOT / ".env_public"
    lines = []
    if env_path.exists():
        with open(env_path, "r") as f:
            lines = f.readlines()
    lines = [l for l in lines if not l.startswith("API_BASE_URL=")]
    lines.append(f"API_BASE_URL={api_url}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)
    print(f"OK   : .env_public updated with API_BASE_URL={api_url}")

# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> None:
    p = argparse.ArgumentParser(prog="tools.py")
    sp_ = p.add_subparsers(dest="cmd", required=True)

    sp_.add_parser("lambda-package", help="build router.zip")
    sp_.add_parser("tf-apply",       help="zip + terraform init/apply")
    rb = sp_.add_parser("lambda-rollback")
    rb.add_argument("--version", required=True, help="Lambda numeric version")

    args = p.parse_args()
    if args.cmd == "lambda-package":
        lambda_package()
    elif args.cmd == "tf-apply":
        tf_apply()
    elif args.cmd == "lambda-rollback":
        lambda_rollback(args.version)

if __name__ == "__main__":
    main()
