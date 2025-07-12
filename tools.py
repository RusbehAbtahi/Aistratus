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
    run([tf, "init", "-backend-config=../../backend.auto.tfvars"], cwd=TERRAFORM_DIR)
    run([tf, "apply", "-auto-approve"], cwd=TERRAFORM_DIR)
    safe_print("OK   : terraform apply finished")

def lambda_rollback(version: str) -> None:
    if not version.isdigit():
        safe_print("ERROR: --version must be an integer (Lambda numeric version)")
        sys.exit(1)
    if not ROLLBACK_SH.exists():
        safe_print(f"ERROR: rollback script not found: {ROLLBACK_SH}")
        sys.exit(1)
    run(["bash", str(ROLLBACK_SH), version])

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
