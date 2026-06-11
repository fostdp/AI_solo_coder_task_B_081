from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.config import get_settings

app = FastAPI(title="Pattern Miner Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

from pattern_miner.routes import router as mining_router
app.include_router(mining_router)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "pattern_miner"}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("pattern_miner.main:app", host=settings.api_host, port=settings.pattern_miner_port, reload=True)
