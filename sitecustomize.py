# sitecustomize.py
import os
# ensure env‐vars exist so get_id won’t even try SSM
os.environ.setdefault("COGNITO_USER_POOL_ID", "eu-central-1_TEST")
os.environ.setdefault("COGNITO_CLIENT_ID", "local-test-client-id")

# stub out SSM fetch entirely
try:
    from tinyllama.utils import ssm
    ssm.get_id = lambda name: os.environ[name.upper()]
except ImportError:
    pass
