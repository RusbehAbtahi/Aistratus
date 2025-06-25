from fastapi import FastAPI, Depends
from .security import verify_jwt

app = FastAPI(
    title="TinyLlama Edge API",
    version="0.0.0-draft",
    description="🚧  Skeleton only—routes land in API-002+",
    docs_url="/docs", redoc_url="/redoc",
)

@app.get("/ping")
async def ping():
    return {"status": "ok"}

@app.post("/infer")
def infer_stub(dep=Depends(verify_jwt)):
    return {"status": "ok"}
