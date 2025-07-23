import os
from unittest.mock import patch

os.environ.setdefault("COGNITO_USER_POOL_ID", "eu-central-1_TEST")
os.environ.setdefault("COGNITO_CLIENT_ID", "local-test-client-id")

patcher = patch('tinyllama.utils.ssm.get_id', lambda name: os.environ[name.upper()])
patcher.start()
