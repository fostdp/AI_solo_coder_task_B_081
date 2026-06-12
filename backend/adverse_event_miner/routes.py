from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from adverse_event_miner.miner import (
    ExpertKnowledgeEngine,
    AdverseReactionExtractor,
    RiskPairDetector,
    FormulaRiskAssessor,
)

router = APIRouter(prefix="/adverse", tags=["不良反应挖掘"])

_expert_engine = ExpertKnowledgeEngine()


class TextMiningRequest(BaseModel):
    text: str


class FormulaRiskRequest(BaseModel):
    formula_name: str
    herbs: List[str]
    herb_dosages: Optional[Dict[str, float]] = None
    include_expert_inference: bool = True


class HerbsRequest(BaseModel):
    herbs: List[str]


class HerbProfileRequest(BaseModel):
    herb: str


class RiskPairsRequest(BaseModel):
    herbs: List[str]
    include_expert_inference: bool = True


@router.post("/text/extract")
async def extract_adverse_reactions(request: TextMiningRequest):
    result = AdverseReactionExtractor.extract_from_text(request.text)
    return {"extracted_reactions": result, "count": len(result)}


@router.post("/text/aggregate")
async def aggregate_adverse_reactions(request: HerbsRequest):
    result = AdverseReactionExtractor.aggregate_reactions(request.herbs)
    return result


@router.post("/risk/pairs")
async def detect_risk_pairs(request: RiskPairsRequest):
    pairs = RiskPairDetector.detect_for_formula(
        herbs=request.herbs,
        include_expert_inference=request.include_expert_inference,
    )
    return {"risk_pairs": pairs, "total": len(pairs)}


@router.post("/risk/assess")
async def assess_formula_risk(request: FormulaRiskRequest):
    result = FormulaRiskAssessor.assess(
        formula_name=request.formula_name,
        herbs=request.herbs,
        herb_dosages=request.herb_dosages,
        include_expert_inference=request.include_expert_inference,
    )
    return result


@router.post("/expert/infer-interactions")
async def infer_interactions(request: HerbsRequest):
    inferred = _expert_engine.infer_interactions(request.herbs)
    return {"inferred_interactions": inferred, "count": len(inferred)}


@router.post("/expert/expand-profile")
async def expand_toxic_profile(request: HerbProfileRequest):
    profile = _expert_engine.expand_toxic_profile(request.herb)
    return profile


@router.post("/expert/pregnancy-risk")
async def assess_pregnancy_risk(request: HerbsRequest):
    risk = _expert_engine.assess_pregnancy_risk(request.herbs)
    return risk


@router.get("/expert/families")
async def get_toxic_families():
    return {
        "toxic_families": _expert_engine.TOXIC_FAMILIES,
        "pregnancy_contraindicated": _expert_engine.PREGNANCY_CONTRAINDICATED_CATEGORIES,
        "inference_rules": _expert_engine.INTERACTION_RULES,
    }
