import os

# Directory containing the target files
base_dir = os.path.dirname(os.path.abspath(__file__))
controllers_dir = os.path.join(base_dir, 'controllers')

# File order as specified by you
files_to_concat = [
    'main.py',
    'gui_view.py',
    'app_state.py',
    'thread_service.py',
    os.path.join('controllers', 'auth_controller.py'),
    os.path.join('controllers', 'cost_controller.py'),
    os.path.join('controllers', 'gpu_controller.py'),
    os.path.join('controllers', 'prompt_controller.py'),
]

output_path = os.path.join(base_dir, 'gui_epic1_full.py')

with open(output_path, 'w', encoding='utf-8') as outfile:
    for rel_path in files_to_concat:
        file_path = os.path.join(base_dir, rel_path) if not rel_path.startswith('controllers') else os.path.join(base_dir, rel_path)
        if os.path.exists(file_path):
            outfile.write(f"# ==== {rel_path} ====\n\n")
            with open(file_path, 'r', encoding='utf-8') as infile:
                outfile.write(infile.read())
                outfile.write('\n\n')
        else:
            outfile.write(f"# ==== {rel_path} (NOT FOUND) ====\n\n")

print(f"Packed code written to: {output_path}")
