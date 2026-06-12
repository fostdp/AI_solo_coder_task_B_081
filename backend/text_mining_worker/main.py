from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.config import get_settings

app = FastAPI(
    title="文本挖掘Worker服务",
    description="独立文本挖掘微服务 - 不良反应提取、疗效情感分析、异步任务处理",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from text_mining_worker.routes import router as text_mining_router
app.include_router(text_mining_router)


@app.get("/")
async def root():
    return {
        "service": "text_mining_worker",
        "version": "2.0.0",
        "status": "running",
        "endpoints": [
            "/text-mining/adverse/extract",
            "/text-mining/adverse/batch-extract",
            "/text-mining/adverse/aggregate",
            "/text-mining/efficacy/analyze",
            "/text-mining/efficacy/batch-analyze",
            "/text-mining/efficacy/sentiment",
            "/text-mining/task/submit",
            "/text-mining/task/{task_id}",
            "/text-mining/task/status",
            "/text-mining/patterns",
        ],
    }


@app.get("/health")
def health():
    return {"status": "healthy", "service": "text_mining_worker"}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("text_mining_worker.main:app", host=settings.api_host, port=settings.text_mining_worker_port, reload=True)
