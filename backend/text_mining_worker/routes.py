from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from text_mining_worker.processor import (
    AdverseEventTextMiner,
    EfficacyTextAnalyzer,
    TextMiningWorker,
)

router = APIRouter(prefix="/text-mining", tags=["文本挖掘Worker"])

_mining_worker = TextMiningWorker(num_workers=2)
_mining_worker.start()

_adverse_miner = AdverseEventTextMiner()
_efficacy_analyzer = EfficacyTextAnalyzer()


class TextRequest(BaseModel):
    text: str


class BatchTextRequest(BaseModel):
    texts: List[str]


class MiningTaskRequest(BaseModel):
    task_type: str
    text: str = ""
    texts: Optional[List[str]] = None
    context: Optional[Dict[str, Any]] = None


@router.post("/adverse/extract")
async def extract_adverse_reactions(request: TextRequest):
    result = _adverse_miner.extract_from_text(request.text)
    return {"extracted_reactions": result, "count": len(result)}


@router.post("/adverse/batch-extract")
async def batch_extract_adverse(request: BatchTextRequest):
    results = _adverse_miner.batch_extract(request.texts)
    return {"batch_results": results, "total": len(results)}


@router.post("/adverse/aggregate")
async def aggregate_adverse_reactions(request: BatchTextRequest):
    all_reactions = []
    for text in request.texts:
        extracted = _adverse_miner.extract_from_text(text)
        all_reactions.extend(extracted)
    result = _adverse_miner.aggregate_reactions(all_reactions)
    return result


@router.post("/efficacy/analyze")
async def analyze_efficacy(request: TextRequest):
    result = _efficacy_analyzer.analyze_with_uncertainty(request.text)
    return result


@router.post("/efficacy/batch-analyze")
async def batch_analyze_efficacy(request: BatchTextRequest):
    results = _efficacy_analyzer.batch_analyze(request.texts)
    return {"batch_results": results, "total": len(results)}


@router.post("/efficacy/sentiment")
async def compute_sentiment(request: TextRequest):
    sentiment = _efficacy_analyzer.compute_sentiment(request.text)
    days = _efficacy_analyzer.extract_days(request.text)
    return {"sentiment_score": round(sentiment, 4), "days_to_effect": days}


@router.post("/task/submit")
async def submit_mining_task(request: MiningTaskRequest, background_tasks: BackgroundTasks):
    valid_task_types = ["adverse_extract", "efficacy_analyze", "batch_adverse", "batch_efficacy"]
    if request.task_type not in valid_task_types:
        raise HTTPException(status_code=400, detail=f"无效的任务类型。有效类型: {valid_task_types}")

    context = request.context or {}
    if request.texts:
        context["texts"] = request.texts

    task_id = _mining_worker.submit_task(
        task_type=request.task_type,
        text=request.text,
        context=context,
    )
    return {"task_id": task_id, "status": "submitted"}


@router.get("/task/{task_id}")
async def get_mining_task_result(task_id: str):
    task = _mining_worker.get_result(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "status": task.status,
        "result": task.result,
        "error": task.error,
        "created_at": task.created_at,
        "completed_at": task.completed_at,
    }


@router.get("/task/status")
async def get_worker_status():
    return _mining_worker.get_queue_status()


@router.post("/task/cleanup")
async def cleanup_old_tasks(max_age_seconds: int = 3600):
    removed = _mining_worker.cleanup_old_results(max_age_seconds)
    return {"removed_count": removed, "max_age_seconds": max_age_seconds}


@router.get("/patterns")
async def get_mining_patterns():
    return {
        "adverse_reaction_patterns": [
            {"pattern": p[0] if isinstance(p[0], str) else p[0].pattern, "reaction_type": p[1], "severity": p[2]}
            for p in _adverse_miner.REACTION_PATTERNS
        ],
        "positive_keywords": list(_efficacy_analyzer.POSITIVE_KEYWORDS.keys()),
        "negative_keywords": list(_efficacy_analyzer.NEGATIVE_KEYWORDS.keys()),
        "intensifiers": list(_efficacy_analyzer.INTENSIFIERS.keys()),
        "negation_prefixes": _efficacy_analyzer.NEGATION_PREFIXES,
    }
