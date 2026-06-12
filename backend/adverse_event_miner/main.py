from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.config import get_settings

from adverse_event_miner.routes import router as adverse_router

app = FastAPI(
    title="不良反应挖掘服务",
    description="中医方剂不良反应挖掘与风险评估独立微服务",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(adverse_router)


@app.get("/")
async def root():
    return {
        "service": "adverse_event_miner",
        "version": "2.0.0",
        "status": "running",
        "endpoints": [
            "/adverse/text/extract",
            "/adverse/text/aggregate",
            "/adverse/risk/pairs",
            "/adverse/risk/assess",
            "/adverse/expert/infer-interactions",
            "/adverse/expert/expand-profile",
            "/adverse/expert/pregnancy-risk",
            "/adverse/expert/families",
        ],
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "adverse_event_miner"}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("adverse_event_miner.main:app", host=settings.api_host, port=settings.adverse_event_miner_port, reload=True)
