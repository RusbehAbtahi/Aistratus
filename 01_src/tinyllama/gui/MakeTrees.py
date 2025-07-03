import os

# --- CONFIGURATION ---
base_path = r"C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus"
include_dirs = [
    ".github",
    "00_infra",
    "01_src",
    "02_tests",
    "04_scripts",
    "05_docs",
    "terraform",
    "api"
]

def print_tree(path, prefix=""):
    items = sorted(os.listdir(path))
    for index, name in enumerate(items):
        full_path = os.path.join(path, name)
        connector = "└── " if index == len(items) - 1 else "├── "
        print(prefix + connector + name)
        if os.path.isdir(full_path):
            print_tree(full_path, prefix + ("    " if index == len(items) - 1 else "│   "))

# --- PRINT FILES IN ROOT ---
print(f"{base_path}")
for name in sorted(os.listdir(base_path)):
    full_path = os.path.join(base_path, name)
    if os.path.isfile(full_path):
        print("├── " + name)

# --- PRINT SELECTED DIRECTORIES ---
for idx, d in enumerate(include_dirs):
    full_dir = os.path.join(base_path, d)
    if os.path.isdir(full_dir):
        print("├── " + d)
        print_tree(full_dir, "│   ")
