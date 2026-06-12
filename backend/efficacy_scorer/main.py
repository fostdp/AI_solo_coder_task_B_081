from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.config import get_settings

from efficacy_scorer.routes import router as efficacy_router

app = FastAPI(
    title="疗效量化评估服务",
    description="中医方剂疗效量化评估独立微服务",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(efficacy_router)


@app.get("/")
async def root():
    return {
        "service": "efficacy_scorer",
        "version": "2.0.0",
        "status": "running",
        "endpoints": [
            "/efficacy/analyze",
            "/efficacy/grade",
            "/efficacy/evaluate",
            "/efficacy/annotation/submit",
            "/efficacy/annotation/complete",
            "/efficacy/annotation/stats",
            "/efficacy/annotation/pending",
            "/efficacy/cases/generate",
            "/efficacy/cases/aggregate",
        ],
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "efficacy_scorer"}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("efficacy_scorer.main:app", host=settings.api_host, port=settings.efficacy_scorer_port, reload=True)
