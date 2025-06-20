"""
api.routes
==========

Empty FastAPI app placeholder.  Real routes land in API-002+.
"""

from fastapi import FastAPI

app = FastAPI(
    title="TinyLlama Edge API",
    version="0.0.0-draft",
    description="🚧  Skeleton only—routes land in API-002+",
    docs_url="/docs", redoc_url="/redoc",
)

# keep file non-empty or FastAPI will raise at start-up
@app.get("/__placeholder__", include_in_schema=False)
async def _placeholder():
    return {"status": "placeholder"}
