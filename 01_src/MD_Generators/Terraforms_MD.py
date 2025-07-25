#!/usr/bin/env python3
import os
import json

def generate_terraform_md():
    # === Configuration ===
    project_root = r"C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus_2"
    tf_root = os.path.join(project_root, "terraform", "10_global_backend")
    ignore_dirs = {".terraform"}
    output_md   = os.path.join(os.path.dirname(__file__), "terraform_files.md")
    output_json = os.path.join(os.path.dirname(__file__), "terraform_check.json")

    # === Prepare containers ===
    md_lines = ["# All Terraform Files and Corresponding Data", ""]
    json_index = []            # final JSON index
    seen = set()
    collected_json = []        # JSON files to emit after all TF

    def process_directory(dir_path):
        # List all entries in this directory
        try:
            entries = os.listdir(dir_path)
        except OSError:
            return

        # Separate files and subdirectories
        files = [f for f in entries if os.path.isfile(os.path.join(dir_path, f))]
        dirs  = [d for d in entries if os.path.isdir(os.path.join(dir_path, d)) and d not in ignore_dirs]

        # Filter to .tf and .tfvars only
        tfs = [f for f in files if f.lower().endswith(('.tf', '.tfvars'))]

        # Order .tf/.tfvars: main.tf, outputs.tf, variables.tf, then rest alphabetically
        ordered_tf = []
        for special in ("main.tf", "outputs.tf", "variables.tf"):
            if special in tfs:
                ordered_tf.append(special)
        others = sorted([f for f in tfs if f not in ("main.tf", "outputs.tf", "variables.tf")], key=lambda x: x.lower())
        ordered_tf.extend(others)

        # Emit each Terraform file
        for fname in ordered_tf:
            full_path = os.path.join(dir_path, fname)
            rel_path = os.path.relpath(full_path, project_root).replace(os.sep, "\\")
            if rel_path in seen:
                continue
            seen.add(rel_path)
            json_index.append(rel_path)

            # Markdown entry
            md_lines.append(f"## {rel_path}")
            md_lines.append("")
            md_lines.append("```hcl")
            with open(full_path, "r", encoding="utf-8") as f:
                md_lines.extend(line.rstrip("\n") for line in f)
            md_lines.append("```")
            md_lines.append("")

        # Collect JSON files for later
        json_files = [f for f in files if f.lower().endswith('.json')]
        for fname in sorted(json_files, key=lambda x: x.lower()):
            full_path = os.path.join(dir_path, fname)
            rel_path = os.path.relpath(full_path, project_root).replace(os.sep, "\\")
            if rel_path in seen:
                continue
            seen.add(rel_path)
            collected_json.append((dir_path, fname))

        # Recurse into subdirectories (alphabetical)
        for sub in sorted(dirs, key=lambda x: x.lower()):
            process_directory(os.path.join(dir_path, sub))

    # Kick off recursion
    process_directory(tf_root)

    # After all TF files, append collected JSON files
    for dir_path, fname in collected_json:
        full_path = os.path.join(dir_path, fname)
        rel_path = os.path.relpath(full_path, project_root).replace(os.sep, "\\")
        json_index.append(rel_path)

        md_lines.append(f"## {rel_path}")
        md_lines.append("")
        md_lines.append("```json")
        with open(full_path, "r", encoding="utf-8") as f:
            md_lines.extend(line.rstrip("\n") for line in f)
        md_lines.append("```")
        md_lines.append("")

    # Write markdown
    with open(output_md, "w", encoding="utf-8") as md_file:
        md_file.write("\n".join(md_lines))

    # Write JSON index
    with open(output_json, "w", encoding="utf-8") as json_file:
        json.dump(json_index, json_file, indent=2, ensure_ascii=False)

    print(f"✅ Markdown written to: {output_md}")
    print(f"✅ JSON index written to: {output_json}")

if __name__ == "__main__":
    generate_terraform_md()
