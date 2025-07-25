#!/usr/bin/env python3
import os
import json
import math
import tkinter as tk
from tkinter import font, ttk

# Constants
TERRAFORM_JSON = 'terraform_check.json'
PYTHON_JSON    = 'python_files.json'
TICKETS_JSON   = 'Merged_Tickets.json'
RULES_JSON     = 'RuleFiles_List.json'
TF_PREFIX      = r"terraform\10_global_backend"
MAX_PER_COL    = 25
FONT_NAME      = "Arial"
FONT_SIZE      = 12


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_tf(path):
    if path.startswith(TF_PREFIX):
        return f"~{path[len(TF_PREFIX):]}"
    return path


def generate_prompt():
    selections = []
    for idx, var in enumerate(vars_list):
        if not var.get():
            continue
        item_type, full_path = all_items[idx]
        if item_type == 'terraform':
            selections.append(f"Fetch code block: terraform_files.md :: {full_path}")
        elif item_type == 'python':
            selections.append(f"Fetch code block: python_files.md :: {full_path}")
        else:
            selections.append(f"Fetch code block: Merged_Tickets.md :: {full_path}")
    if not selections:
        result_label_tab1.config(text="No items selected in Tab 1.", fg="red")
        return

    prompt = " & ".join(selections)
    root.clipboard_clear()
    root.clipboard_append(prompt)
    result_label_tab1.config(text="Prompt copied to clipboard!", fg="green")


def generate_tab2_prompt():
    parts = []
    # Reference file (radio)
    ref = tab2_selection.get()
    if ref:
        parts.append(
            f"REFERENCE MATERIALS\n"
            + f"Read {ref} thoroughly and integrate its full content into your reasoning for this prompt. "
            + "Use it with highest attention, but also consider other relevant files if needed. "
            + f"Do not paste or summarize {ref} unless I explicitly request it."
        )
    # Rule files (checkboxes)
    for var, rule in rule_vars:
        if var.get():
            parts.append(
                f"Read the section # {rule} in Combined_Rules_and_Process.md and enforce everything beneath it as strict operational rule for this session. "
                "Follow every principle exactly as written; do not relax or ignore any part unless I explicitly say so."
            )
    if not parts:
        result_label_tab2.config(text="No selections made.", fg="red")
        return

    prompt = " & ".join(parts)
    root.clipboard_clear()
    root.clipboard_append(prompt)
    result_label_tab2.config(text="Reference & rules prompt copied!", fg="green")

# Load data
tf_paths      = load_json(TERRAFORM_JSON)
py_paths      = load_json(PYTHON_JSON)
ticket_titles = load_json(TICKETS_JSON)
rule_list     = load_json(RULES_JSON)

# Build unified lists for Tab1
all_items     = []
display_paths = []
for p in tf_paths:
    all_items.append(('terraform', p))
    display_paths.append(normalize_tf(p))
for p in py_paths:
    all_items.append(('python', p))
    display_paths.append(p)
for t in ticket_titles:
    all_items.append(('ticket', t))
    display_paths.append(t)

# --- GUI Setup ---
root = tk.Tk()
root.title("Multi-Tab File & Ticket Selector")

# Fonts
chk_font = font.Font(family=FONT_NAME, size=FONT_SIZE)
btn_font = font.Font(family=FONT_NAME, size=FONT_SIZE + 2)

# Determine cols for Tab1
num_items = len(display_paths)
cols = min(4, math.ceil(num_items / MAX_PER_COL))
window_width = 600 + (cols - 1) * 300
window_height = 600
root.geometry(f"{window_width}x{window_height}")

# Notebook and tabs
notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

# Tab 1: Existing selector
tab1 = ttk.Frame(notebook)
notebook.add(tab1, text="Files & Tickets")
# Tab 2: Reference Materials + Rules
tab2 = ttk.Frame(notebook)
notebook.add(tab2, text="References & Rules")
# Tab 3: empty placeholder
tab3 = ttk.Frame(notebook)
notebook.add(tab3, text="Tab 3")

# --- Tab1 content ---
canvas1    = tk.Canvas(tab1)
scrollbar1 = tk.Scrollbar(tab1, orient="vertical", command=canvas1.yview)
frame1     = tk.Frame(canvas1)
frame1.bind(
    "<Configure>", lambda e: canvas1.configure(scrollregion=canvas1.bbox("all"))
)
canvas1.create_window((0,0), window=frame1, anchor="nw")
canvas1.configure(yscrollcommand=scrollbar1.set)
canvas1.grid(row=0, column=0, columnspan=cols, sticky="nsew")
scrollbar1.grid(row=0, column=cols, sticky="ns")

vars_list = []
for idx, text in enumerate(display_paths):
    var = tk.BooleanVar()
    col = idx // MAX_PER_COL
    row = idx % MAX_PER_COL
    item_type, _ = all_items[idx]
    fg_color = "blue" if item_type == 'python' else "black"
    chk = tk.Checkbutton(
        frame1, text=text, variable=var, anchor="w",
        font=chk_font, fg=fg_color,
        wraplength=(window_width // cols) - 50
    )
    chk.grid(row=row, column=col, sticky="w", padx=5, pady=2)
    vars_list.append(var)

generate_btn1 = tk.Button(tab1, text="Generate", command=generate_prompt, font=btn_font)
generate_btn1.grid(row=1, column=0, columnspan=cols, pady=(10,0))
result_label_tab1 = tk.Label(tab1, text="", font=chk_font)
result_label_tab1.grid(row=2, column=0, columnspan=cols, pady=(5,0))
for c in range(cols): tab1.grid_columnconfigure(c, weight=1)
tab1.grid_rowconfigure(0, weight=1)

# --- Tab2 content ---
# Radio buttons for references
refs = [
    'Epics_TinyLlama.md',
    'Merged_Tickets.md',
    'Project_Tree.md',
    'terraform_resources.md',
    'terraform_files.md',
    'python_files.md'
]

tab2_selection = tk.StringVar()
for ref in refs:
    rb = tk.Radiobutton(tab2, text=ref, variable=tab2_selection,
                        value=ref, font=chk_font, anchor="w")
    rb.pack(anchor="w", padx=10, pady=2)

# Checkboxes for rule files (red)
rule_vars = []
for rule in rule_list:
    var = tk.BooleanVar()
    cb = tk.Checkbutton(tab2, text=rule, variable=var,
                        font=chk_font, fg="red", anchor="w")
    cb.pack(anchor="w", padx=30, pady=1)
    rule_vars.append((var, rule))

# Generate button for Tab2
generate_btn2 = tk.Button(tab2, text="Generate Reference & Rules Prompt",
                           command=generate_tab2_prompt,
                           font=btn_font)
generate_btn2.pack(pady=(10,0))
result_label_tab2 = tk.Label(tab2, text="", font=chk_font)
result_label_tab2.pack(pady=(5,0))

# Placeholder Tab3 remains empty

root.mainloop()
