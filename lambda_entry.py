# lambda_entry.py  — minimal ASGI wrapper
from api.routes import app          # ← your FastAPI app
from mangum import Mangum           # AWS → ASGI adapter
handler = Mangum(app)               # Lambda handler object
