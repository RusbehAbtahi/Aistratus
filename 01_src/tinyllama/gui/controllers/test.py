from dotenv import load_dotenv
load_dotenv()
import os
import openai

api_key = os.environ.get("OPENAI_API_KEY")
client = openai.OpenAI(api_key=api_key)
resp = client.models.list()
print(resp)

