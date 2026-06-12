from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.config import get_settings

app = FastAPI(
    title="Meta分析计算服务",
    description="独立Meta分析计算微服务 - 标准Meta分析、网络Meta分析、敏感性分析",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from meta_analysis_service.routes import router as meta_router
app.include_router(meta_router)


@app.get("/")
async def root():
    return {
        "service": "meta_analysis_service",
        "version": "2.0.0",
        "status": "running",
        "endpoints": [
            "/meta/standard",
            "/meta/network",
            "/meta/sensitivity",
        ],
    }


@app.get("/health")
def health():
    return {"status": "healthy", "service": "meta_analysis_service"}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("meta_analysis_service.main:app", host=settings.api_host, port=settings.meta_analysis_service_port, reload=True)
