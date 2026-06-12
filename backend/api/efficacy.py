import warnings
from fastapi import APIRouter

warnings.warn(
    "api.efficacy is deprecated. Use independent module routes via gateway instead: "
    "efficacy_scorer, dose_response_modeler, adverse_event_miner, clinical_trial_integrator",
    DeprecationWarning,
    stacklevel=2,
)

router = APIRouter(prefix="/efficacy", tags=["疗效量化与临床证据(旧版-已弃用)"])


@router.get("/deprecation-notice")
def deprecation_notice():
    return {
        "status": "deprecated",
        "message": "此旧版API已弃用，请使用微服务网关路由",
        "new_routes": {
            "疗效量化评估": "/efficacy/scorer/* (efficacy_scorer服务)",
            "剂量效应分析": "/efficacy/dose-response/* (dose_response_modeler服务)",
            "不良反应挖掘": "/efficacy/adverse-events/* (adverse_event_miner服务)",
            "临床证据集成": "/efficacy/clinical/* (clinical_trial_integrator服务)",
            "文本挖掘": "/text-mining/* (text_mining_worker服务)",
            "Meta分析": "/meta-analysis/* (meta_analysis_service服务)",
        },
    }
