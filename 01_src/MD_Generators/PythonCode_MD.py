#!/usr/bin/env python3
import os
import json

# === Configuration ===
# Absolute path to your project root
PROJECT_ROOT = r"C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus_2"
# Directories to scan (non-recursively) – use '~' to represent the project root
ONLY_PATTERNS = [
    "~",
    "~\\01_src\\tinyllama\\router",
    "~\\01_src\\tinyllama\\utils",
    "~\\api",
    "~\\01_src\\tinyllama\\gui",
    "~\\01_src\\tinyllama\\gui\\controllers",
    "~\\02_tests",
    "~\\02_tests\\api",
    "~\\02_tests\\router",
    "~\\02_tests\\gui",
]

# Output files
OUTPUT_MD = os.path.join(os.path.dirname(__file__), "python_files.md")
OUTPUT_JSON = os.path.join(os.path.dirname(__file__), "python_files.json")

def generate_python_md(
    project_root: str = PROJECT_ROOT,
    patterns: list = ONLY_PATTERNS,
    output_md: str = OUTPUT_MD,
    output_json: str = OUTPUT_JSON
):
    """
    Scans specified directories (non-recursively) for .py files (excluding __init__.py),
    writes a Markdown document with code blocks, and creates a JSON index of file paths
    with '~' replacing the project root.
    """
    md_lines = ["# Python Files Index", ""]
    json_index = []

    for pat in patterns:
        # Resolve absolute directory path
        if pat.startswith("~"):
            abs_dir = project_root + pat[1:]
        else:
            abs_dir = pat

        if not os.path.isdir(abs_dir):
            continue

        # Directory heading
        md_lines.append(f"## {abs_dir}")
        md_lines.append("")

        # List .py files (non-recursive), excluding __init__.py
        files = [f for f in os.listdir(abs_dir)
                 if f.endswith(".py")
                 and f != "__init__.py"
                 and os.path.isfile(os.path.join(abs_dir, f))]
        files.sort(key=lambda x: x.lower())

        for fname in files:
            full_path = os.path.join(abs_dir, fname)
            # Build tilde-prefixed path for JSON index
            rel_path = os.path.relpath(full_path, project_root).replace(os.sep, "\\")
            tilde_path = f"~\\{rel_path}"
            json_index.append(tilde_path)

            # Markdown entry
            md_lines.append(f"### {fname}")
            md_lines.append("```python")
            with open(full_path, "r", encoding="utf-8") as f:
                for line in f:
                    md_lines.append(line.rstrip("\n"))
            md_lines.append("```")
            md_lines.append("")

        md_lines.append("")  # blank line between directories

    # Write Markdown
    with open(output_md, "w", encoding="utf-8") as md_file:
        md_file.write("\n".join(md_lines))

    # Write JSON index
    with open(output_json, "w", encoding="utf-8") as json_file:
        json.dump(json_index, json_file, indent=2, ensure_ascii=False)

    print(f"✅ Markdown written to: {output_md}")
    print(f"✅ JSON index written to: {output_json}")


if __name__ == "__main__":
    generate_python_md()
