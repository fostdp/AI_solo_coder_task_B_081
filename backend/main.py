import warnings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from api.formulas import router as formulas_router
from api.herbs import router as herbs_router
from api.diseases import router as diseases_router
from api.graph import router as graph_router
from api.mining import router as mining_router
from api.discovery import router as discovery_router

app = FastAPI(
    title="古代中医药方剂配伍规律挖掘与现代新药发现辅助系统（旧版单体入口-已弃用）",
    description="此单体入口已弃用。请使用微服务网关(gateway.py)启动系统。各功能模块已拆分为独立微服务。",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(formulas_router)
app.include_router(herbs_router)
app.include_router(diseases_router)
app.include_router(graph_router)
app.include_router(mining_router)
app.include_router(discovery_router)

frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
def root():
    return {
        "name": "中医药方剂配伍规律挖掘与现代新药发现辅助系统",
        "version": "2.0.0",
        "status": "DEPRECATED - 请使用微服务网关 gateway.py",
        "endpoints": {
            "formulas": "/formulas/",
            "herbs": "/herbs/",
            "diseases": "/diseases/",
            "graph": "/graph/",
            "mining": "/mining/",
            "discovery": "/discovery/",
        },
        "v2_modules_migrated": {
            "疗效量化评估": "efficacy_scorer (port 8005)",
            "剂量效应分析": "dose_response_modeler (port 8006)",
            "不良反应挖掘": "adverse_event_miner (port 8007)",
            "临床证据集成": "clinical_trial_integrator (port 8008)",
            "Meta分析计算": "meta_analysis_service (port 8009)",
            "文本挖掘Worker": "text_mining_worker (port 8010)",
        },
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "note": "此单体入口已弃用"}


if __name__ == "__main__":
    warnings.warn("直接启动main.py已弃用，请使用 gateway.py 启动微服务架构", DeprecationWarning)
    import uvicorn
    from config import get_settings

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
