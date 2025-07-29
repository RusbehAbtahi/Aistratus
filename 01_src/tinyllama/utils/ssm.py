import os
import functools
import boto3

_SSM = boto3.client("ssm")

@functools.lru_cache(maxsize=128)
def get_id(name: str) -> str:
    """
    Return the ID stored at /tinyllama/<env>/<name> (cached per name+env).
    Prefix is read _each_ call from the current TLFIF_ENV.
    """
    env = os.getenv("TLFIF_ENV", "default")
    path = f"/tinyllama/{env}/{name}"
    resp = _SSM.get_parameter(Name=path)
    return resp["Parameter"]["Value"]
