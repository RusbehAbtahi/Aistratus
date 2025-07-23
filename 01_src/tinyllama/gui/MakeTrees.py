import os
import fnmatch

# --- CONFIGURATION ---
base_path = r"C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus_2"
include_dirs = [
    ".github",
    #"00_infra",
    "01_src",
    "02_tests",
    "04_scripts",
    #"05_docs",
    "terraform",
    "api"
]

# --- FILTERS ---
# List of directory paths (relative to base_path) whose contents should be skipped.
filter_dirs = [
    r"01_src\lambda_layersXXX",
    r"XXX",
    # add more relative paths here...
]
# List of file-name patterns to exclude (e.g. "*.pyc", "*.tmp", etc.)
filter_file_patterns = [
    "*.pyc",
    "*.sh"
    # add more patterns here...
]

def print_tree(path, prefix=""):
    # Compute the path relative to base_path and normalize for comparison
    rel = os.path.normcase(os.path.normpath(os.path.relpath(path, base_path)))
    # If this directory is in the filter list, do not recurse into it
    if any(rel == os.path.normcase(os.path.normpath(fd)) for fd in filter_dirs):
        return

    items = sorted(os.listdir(path))
    for index, name in enumerate(items):
        full_path = os.path.join(path, name)
        # Skip files matching any of the file-type filters
        if os.path.isfile(full_path) and any(fnmatch.fnmatch(name, pat) for pat in filter_file_patterns):
            continue

        connector = "└── " if index == len(items) - 1 else "├── "
        print(prefix + connector + name)

        if os.path.isdir(full_path):
            # Recurse unless this subdir is itself filtered
            print_tree(full_path, prefix + ("    " if index == len(items) - 1 else "│   "))


# --- PRINT FILES IN ROOT ---
print(f"{base_path}")
for name in sorted(os.listdir(base_path)):
    full_path = os.path.join(base_path, name)
    # only files, and skip filtered file types
    if os.path.isfile(full_path) and not any(fnmatch.fnmatch(name, pat) for pat in filter_file_patterns):
        print("├── " + name)

# --- PRINT SELECTED DIRECTORIES ---
for idx, d in enumerate(include_dirs):
    full_dir = os.path.join(base_path, d)
    if os.path.isdir(full_dir):
        print("├── " + d)
        # skip recursing into this dir if it's in the directory-filters
        if any(os.path.normcase(os.path.normpath(d)) == os.path.normcase(os.path.normpath(fd)) for fd in filter_dirs):
            continue
        print_tree(full_dir, "│   ")
