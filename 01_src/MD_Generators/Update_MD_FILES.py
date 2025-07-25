#!/usr/bin/env python3
import os
import sys
import subprocess

def run_script(script_name):
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
    if not os.path.isfile(script_path):
        print(f"❌ {script_name} not found at {script_path}")
        sys.exit(1)
    print(f"🔄 Running {script_name}...")
    result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ {script_name} completed successfully.\n")
    else:
        print(f"❌ {script_name} failed with exit code {result.returncode}.")
        if result.stdout:
            print("── STDOUT ──")
            print(result.stdout)
        if result.stderr:
            print("── STDERR ──")
            print(result.stderr)
        sys.exit(result.returncode)

def main():
    scripts = [
        "MakeTree_MD.py",
        "AWSreader_MD.py",
        "Terraforms_MD.py",
        "PythonCode_MD.py"
    ]
    for script in scripts:
        run_script(script)
    print("🎉 All scripts executed successfully.")

if __name__ == "__main__":
    main()
