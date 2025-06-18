# Navigate to project root
cd /c/0000/Prompt_Engineering/Projects/GTPRusbeh/Aistratus

# Activate the virtual environment
. venv_tinyllama/Scripts/activate

# Set the Python path for package imports
export PYTHONPATH=01_src

# Run the tests
pytest 01_src/tinyllama/gui/test_app.py
