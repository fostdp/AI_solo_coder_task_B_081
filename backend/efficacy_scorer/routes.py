from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from efficacy_scorer.scorer import (
    TCMSentimentAnalyzer,
    OrdinalRegressionScorer,
    HumanAnnotationManager,
    MedicalCaseGenerator,
    EfficacyAggregator,
    SentimentUncertaintyEstimator,
)

router = APIRouter(prefix="/efficacy", tags=["疗效量化评估"])

_annotation_manager = HumanAnnotationManager()
_case_generator = MedicalCaseGenerator()


class EvaluateRequest(BaseModel):
    text: str
    days: Optional[int] = None


class BatchEvaluateRequest(BaseModel):
    cases: List[Dict[str, Any]]


class AnnotationSubmitRequest(BaseModel):
    case_id: str
    text: str
    auto_grade: int
    auto_score: float
    uncertainty: str
    reason: str = ""


class AnnotationCompleteRequest(BaseModel):
    case_id: str
    human_grade: int
    human_score: float
    annotator: str = ""
    notes: str = ""


class GenerateCasesRequest(BaseModel):
    formula_name: str
    dynasty: str = "default"
    symptoms: List[str] = []
    n: int = 12


@router.post("/analyze")
async def analyze_sentiment(request: EvaluateRequest):
    result = TCMSentimentAnalyzer.analyze_with_uncertainty(request.text)
    return result


@router.post("/grade")
async def predict_grade(request: EvaluateRequest):
    sentiment = TCMSentimentAnalyzer.compute_sentiment(request.text)
    uncertainty = TCMSentimentAnalyzer.analyze_with_uncertainty(request.text)
    result = OrdinalRegressionScorer.predict_with_uncertainty(
        sentiment, request.days, uncertainty["overall_confidence"]
    )
    return result


@router.post("/evaluate")
async def full_evaluate(request: EvaluateRequest):
    sentiment_result = TCMSentimentAnalyzer.analyze_with_uncertainty(request.text)
    grade_result = OrdinalRegressionScorer.predict_with_uncertainty(
        sentiment_result["sentiment_score"],
        request.days,
        sentiment_result["overall_confidence"],
    )
    return {
        "sentiment": sentiment_result,
        "grade": grade_result,
    }


@router.post("/annotation/submit")
async def submit_annotation(request: AnnotationSubmitRequest):
    item = _annotation_manager.submit_for_review(
        case_id=request.case_id,
        text=request.text,
        auto_grade=request.auto_grade,
        auto_score=request.auto_score,
        uncertainty=request.uncertainty,
        reason=request.reason,
    )
    return {"status": "success", "item": item}


@router.post("/annotation/complete")
async def complete_annotation(request: AnnotationCompleteRequest):
    record = _annotation_manager.annotate(
        case_id=request.case_id,
        human_grade=request.human_grade,
        human_score=request.human_score,
        annotator=request.annotator,
        notes=request.notes,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"status": "success", "record": record}


@router.get("/annotation/stats")
async def get_annotation_stats():
    return _annotation_manager.get_annotation_stats()


@router.get("/annotation/pending")
async def get_pending_count():
    return {"pending_count": _annotation_manager.get_pending_count()}


@router.post("/cases/generate")
async def generate_cases(request: GenerateCasesRequest):
    cases = _case_generator.generate_cases_for_formula(
        formula_name=request.formula_name,
        dynasty=request.dynasty,
        symptoms=request.symptoms,
        n=request.n,
    )
    return {"cases": cases}


@router.post("/cases/aggregate")
async def aggregate_cases(request: BatchEvaluateRequest):
    result = EfficacyAggregator.aggregate(request.cases)
    return result
