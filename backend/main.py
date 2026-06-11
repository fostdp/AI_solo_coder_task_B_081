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
from api.efficacy import router as efficacy_router

app = FastAPI(
    title="古代中医药方剂配伍规律挖掘与现代新药发现辅助系统",
    description="基于MongoDB、Neo4j、FP-Growth、Louvain、链路预测、NLP疗效量化、剂量效应Meta分析、不良反应挖掘、网络Meta分析的中医药智能知识系统",
    version="2.0.0"
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
app.include_router(efficacy_router)

frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
def root():
    return {
        "name": "中医药方剂配伍规律挖掘与现代新药发现辅助系统",
        "version": "2.0.0",
        "endpoints": {
            "formulas": "/formulas/",
            "herbs": "/herbs/",
            "diseases": "/diseases/",
            "graph": "/graph/",
            "mining": "/mining/",
            "discovery": "/discovery/",
            "efficacy (新增-疗效量化 & 临床证据)": "/efficacy/"
        },
        "new_features_v2": [
            "方剂疗效量化评估(NLP+序数回归)",
            "药物剂量-效应关系(限制性立方样条+Meta分析)",
            "方剂不良反应挖掘(十八反十九畏+毒性成分)",
            "现代临床对照试验集成(标准Meta+网络Meta)"
        ],
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/api/stats")
def get_stats():
    from database.mongodb import get_collection
    from data.tcm_data import (
        TOXIC_HERBS, HERB_INTERACTION_PAIRS,
        CLINICAL_TRIAL_MODERN_TREATMENTS, CLASSICAL_FORMULAS_BY_DISEASE,
    )

    formulas_col = get_collection("formulas")
    herbs_col = get_collection("herbs")
    diseases_col = get_collection("diseases")
    efficacy_col = get_collection("medical_cases")
    trials_col = get_collection("clinical_trials")

    return {
        "formulas_count": formulas_col.count_documents({}),
        "herbs_count": herbs_col.count_documents({}),
        "diseases_count": diseases_col.count_documents({}),
        "efficacy_v2": {
            "toxic_herbs_tracked": len(TOXIC_HERBS),
            "risk_pairs_known": len(HERB_INTERACTION_PAIRS),
            "indications_with_clinical_data": list(CLINICAL_TRIAL_MODERN_TREATMENTS.keys()),
            "classical_formulas_benchmarked": sum(len(v) for v in CLASSICAL_FORMULAS_BY_DISEASE.values()),
            "stored_medical_cases": efficacy_col.estimated_document_count(),
            "stored_clinical_trials": trials_col.estimated_document_count(),
        }
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    from config import get_settings
    
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
