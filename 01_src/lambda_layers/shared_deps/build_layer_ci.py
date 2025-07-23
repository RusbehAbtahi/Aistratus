#!/usr/bin/env python3
"""
TinyLlama - build shared_deps.zip layer (cross-platform, pure Python)

- Reuses an existing virtual-env (if $VIRTUAL_ENV is set) or creates `.venv`
  in the script directory.
- Installs/updates pip + wheel.
- Installs all dependencies from requirements.txt into a local `python/` dir.
- Produces shared_deps.zip using the std-lib `zipfile` module.
- Prints resulting archive size.

Tested on Windows 10 (Git Bash), Ubuntu 22.04, and macOS 14.
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VENV_DIR = SCRIPT_DIR / ".venv"
LAYER_ROOT = SCRIPT_DIR / "python"
ZIP_NAME = SCRIPT_DIR / "shared_deps.zip"
REQ_FILE = SCRIPT_DIR / "requirements.txt"


def run(cmd, **kw):
    """Run a subprocess, streaming output, exit on failure."""
    cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
    print(cmd_str)
    subprocess.check_call(cmd, **kw)


def ensure_venv() -> Path:
    """Return the python executable inside the (existing or new) venv."""
    if "VIRTUAL_ENV" in os.environ:
        py = Path(os.environ["VIRTUAL_ENV"]) / (
            "Scripts" if os.name == "nt" else "bin"
        ) / "python"
        print(f"Using existing venv -> {py}")
        return py

    print("Creating local .venv ...")
    run([sys.executable, "-m", "venv", str(VENV_DIR)])
    py = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / "python"
    return py


def pip_install(py: Path, *args):
    run([str(py), "-m", "pip", *args])


def build_layer():
    py = ensure_venv()

    # upgrade tooling
    pip_install(py, "install", "--upgrade", "pip", "wheel")

    # clean old layer dir
    if LAYER_ROOT.exists():
        shutil.rmtree(LAYER_ROOT)
    LAYER_ROOT.mkdir()

    print("Installing requirements into layer folder ...")
    pip_install(
        py,
        "install",
        "-r",
        str(REQ_FILE),
        "--target",
        str(LAYER_ROOT),
        "--upgrade",
    )

    # build zip
    if ZIP_NAME.exists():
        ZIP_NAME.unlink()
    print("Zipping layer ...")
    with zipfile.ZipFile(ZIP_NAME, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in LAYER_ROOT.rglob("*"):
            zf.write(path, path.relative_to(LAYER_ROOT.parent))

    size = ZIP_NAME.stat().st_size / (1024 * 1024)
    print(f"{ZIP_NAME.name} built ({size:.2f} MiB)")


if __name__ == "__main__":
    try:
        build_layer()
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
