```bash
# 1) clone & enter repo
git clone https://github.com/TinyLlama/Aistratus.git && cd Aistratus

# 2) activate portable toolchain (adds ./04_scripts/no_priv/tools to PATH)
source 04_scripts/no_priv/bootstrap_nopriv.sh

# 3) create & activate Python venv *NOW* (before installing awscli)
python -m venv ~/.venvs/tl && source ~/.venvs/tl/bin/activate

# 4) install project deps
pip install --upgrade pip
pip install -r requirements.txt -r dev-requirements.txt

# 5) install AWS CLI into the venv (no admin, pip-based)
bash 04_scripts/no_priv/get_awscli.sh

# 6) verify toolchain
aws --version
terraform.exe -version

# 7) run tests
pytest -q

# 8) optional local Lambda package build
make lambda-package
