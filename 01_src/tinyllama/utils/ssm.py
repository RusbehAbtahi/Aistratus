"""
WHY  : Centralised, cached read from SSM.
WHERE: new file tinyllama/utils/ssm.py
HOW  : imported by any module that needs a cross-env ID.
"""

import os
import functools
import boto3

_SSM = boto3.client("ssm")
_PREFIX = f"/tinyllama/{os.getenv('TLFIF_ENV', 'default')}"

@functools.lru_cache(maxsize=128)
def get_id(name: str) -> str:
    """Return the ID stored at /tinyllama/<env>/<name> (cached 128 entries)."""
    path = f"{_PREFIX}/{name}"
    resp = _SSM.get_parameter(Name=path)
    return resp["Parameter"]["Value"]