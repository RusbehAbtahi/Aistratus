from fastapi import FastAPI, Depends
from .security import verify_jwt

app = FastAPI(
    title="TinyLlama Edge API",
    version="0.0.0-draft",
    description="🚧  Skeleton only—routes land in API-002+",
    docs_url="/docs", redoc_url="/redoc",
)

@app.post("/infer")
def infer_stub(dep=Depends(verify_jwt)):
    return {"status": "ok"}

# (optional: keep the placeholder endpoint for old tests)
@app.get("/__placeholder__", include_in_schema=False)
async def _placeholder():
    return {"status": "placeholder"}
