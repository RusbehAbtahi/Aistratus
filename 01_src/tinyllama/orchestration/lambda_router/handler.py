import json               # Standard library: parse JSON strings into Python objects and vice versa
import os                 # Standard library: interact with environment variables and file system
import boto3              # AWS SDK for Python: create clients to call AWS services (e.g., S3, Secrets Manager)
import uuid               # Standard library: generate universally unique identifiers (UUIDs)

# Create an S3 client using boto3; this will be used to put objects into an S3 bucket
s3 = boto3.client("s3")

# Create a Secrets Manager client; this will be used to retrieve stored secrets (e.g., API keys)
sm = boto3.client("secretsmanager")

# Read the name of the S3 bucket from an environment variable named DATA_BUCKET
# Lambda functions can reference environment variables defined in the function configuration
bucket = os.environ["DATA_BUCKET"]

# Define the secret identifier in AWS Secrets Manager;
# this is the name under which the OpenAI API key is stored
secret_id = "tinyllama/openai"

def handler(event, context):
    """
    Lambda entry point.
    - `event`: contains request data, in this case an HTTP POST payload.
    - `context`: runtime information (unused here).
    """

    # Extract the HTTP request body (a JSON string) from the `event` dictionary.
    # `event.get("body", "{}")` attempts to read "body"; if missing, defaults to "{}".
    body = json.loads(event.get("body", "{}"))

    # From the parsed JSON, retrieve the value associated with the "prompt" key.
    # If "prompt" is not provided, default to an empty string.
    prompt = body.get("prompt", "")

    # If "prompt" is empty or missing, return an HTTP 400 error response.
    # The structure follows API Gateway's Lambda proxy integration format:
    #   statusCode: HTTP status code
    #   body: response payload (string)
    if not prompt:
        return {
            "statusCode": 400,
            "body": "Missing prompt"
        }

    # Generate a unique key for the new S3 object.
    # uuid.uuid4() produces a random UUID, and we prefix with "inputs/" and suffix ".txt".
    # The result might look like "inputs/123e4567-e89b-12d3-a456-426614174000.txt"
    key = f"inputs/{uuid.uuid4()}.txt"

    # Upload the prompt text to S3 under the bucket and key.
    # - Bucket: the S3 bucket name from environment variables
    # - Key: the unique path we just generated
    # - Body: the raw bytes of the prompt text (encoded from Python string)
    s3.put_object(Bucket=bucket, Key=key, Body=prompt.encode())

    # Retrieve the secret value from AWS Secrets Manager.
    # This is a basic check to ensure the Lambda role has permission to read the secret.
    # If access is denied or the secret does not exist, this call will raise an exception.
    sm.get_secret_value(SecretId=secret_id)

    # Return a successful HTTP 200 response.
    # The body contains a JSON object indicating which S3 key was used.
    # We convert the Python dict {"saved": key} back into a JSON string.
    return {
        "statusCode": 200,
        "body": json.dumps({"saved": key})
    }
