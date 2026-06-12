from fastapi import APIRouter, Query, Body
from typing import List, Optional, Dict, Any

from database.mongodb import get_collection
from efficacy_scorer.scorer import (
    MedicalCaseGenerator,
    EfficacyAggregator,
)
from adverse_event_miner.miner import FormulaRiskAssessor
from clinical_trial_integrator.integrator import (
    ClinicalTrialSimulator,
    StandardMetaAnalysis,
    NetworkMetaAnalysis,
)
from meta_analysis_service.calculator import (
    StandardMetaCalculator,
    NetworkMetaCalculator,
)

router = APIRouter(prefix="", tags=["临床试验集成与Meta分析"])


@router.get("/efficacy/clinical/trials")
def get_clinical_trials(
    indication: str = Query(..., description="适应症: 感冒/咳嗽/胃痛/失眠/高血压/糖尿病"),
    num_trials: int = Query(default=10, ge=3, le=50),
):
    sim = ClinicalTrialSimulator(seed=hash(indication) % 10000)
    trials = sim.generate_trials(indication, n_trials=num_trials)
    from data.tcm_data import CLINICAL_TRIAL_MODERN_TREATMENTS, CLASSICAL_FORMULAS_BY_DISEASE
    return {
        "indication": indication,
        "trials_count": len(trials),
        "modern_treatments_available": [t["name"] for t in CLINICAL_TRIAL_MODERN_TREATMENTS.get(indication, [])],
        "classical_formulas_available": CLASSICAL_FORMULAS_BY_DISEASE.get(indication, []),
        "trials": trials,
    }


@router.get("/efficacy/clinical/meta-analysis")
def run_meta_analysis(
    indication: str = Query(..., description="适应症"),
    num_trials: int = Query(default=10, ge=3, le=50),
):
    sim = ClinicalTrialSimulator(seed=hash(indication) % 10000)
    trials = sim.generate_trials(indication, n_trials=num_trials)
    result = StandardMetaAnalysis.compare_classical_vs_modern(trials, indication)
    result["raw_trials_count"] = len(trials)
    return result


@router.get("/efficacy/clinical/network-meta")
def run_network_meta_analysis(
    indication: str = Query(..., description="适应症"),
    num_trials: int = Query(default=15, ge=5, le=80),
):
    sim = ClinicalTrialSimulator(seed=hash(indication) % 10000)
    trials = sim.generate_trials(indication, n_trials=num_trials)
    result = NetworkMetaAnalysis.run(trials, indication)
    result["trials_count"] = len(trials)
    return result


@router.get("/efficacy/clinical/formula-evidence-batch")
def batch_clinical_evidence(
    names: str = Query(..., description="逗号分隔的方剂名"),
):
    from data.tcm_data import CLASSICAL_FORMULAS_BY_DISEASE
    name_list = [n.strip() for n in names.split(",") if n.strip()]
    formula_to_indications = {}
    for ind, fnames in CLASSICAL_FORMULAS_BY_DISEASE.items():
        for fn in fnames:
            if fn not in formula_to_indications:
                formula_to_indications[fn] = []
            formula_to_indications[fn].append(ind)
    results = {}
    for name in name_list:
        indications = formula_to_indications.get(name, [])
        results[name] = {
            "has_evidence": len(indications) > 0,
            "clinical_indications": indications,
            "evidence_level": "有RCT证据" if indications else "暂无",
        }
    return {"evidence": results}


@router.get("/efficacy/summary/indication/{indication}")
def indication_full_summary(indication: str):
    sim = ClinicalTrialSimulator(seed=hash(indication) % 10000)
    trials = sim.generate_trials(indication, n_trials=12)
    meta = StandardMetaAnalysis.compare_classical_vs_modern(trials, indication)
    nma = NetworkMetaAnalysis.run(trials, indication)
    formulas_col = get_collection("formulas")
    top_formulas = []
    for f in formulas_col.find({"indications": indication}).limit(10):
        gen = MedicalCaseGenerator(seed=hash(f["name"]) % 10000)
        cases = gen.generate_cases_for_formula(
            f["name"], f.get("dynasty", "宋代"),
            f.get("indications", []), n=10
        )
        agg = EfficacyAggregator.aggregate(cases)
        herbs = [h["name"] if isinstance(h, dict) else h for h in f.get("herbs", [])]
        if isinstance(f.get("herbs"), list) and f["herbs"] and isinstance(f["herbs"][0], dict):
            herbs = [h.get("name", "") for h in f["herbs"]]
        risk = FormulaRiskAssessor.assess(f["name"], herbs)
        top_formulas.append({
            "name": f["name"],
            "dynasty": f.get("dynasty"),
            "avg_efficacy_score": agg["avg_efficacy_score"],
            "avg_days_to_effect": agg["avg_days_to_effect"],
            "risk_level": risk["overall_risk_level"],
            "risk_score": risk["overall_risk_score"],
            "warning_count": len(risk["warnings"]),
        })
    top_formulas.sort(key=lambda x: (x["avg_efficacy_score"] - x["risk_score"] / 5), reverse=True)
    return {
        "indication": indication,
        "trials_summary": {
            "total": len(trials),
            "years_range": [min(t["year"] for t in trials), max(t["year"] for t in trials)],
            "total_patients": sum(t["total_sample_size"] for t in trials),
        },
        "meta_analysis": meta,
        "network_meta": nma,
        "top_formulas_by_value": top_formulas[:8],
    }


@router.post("/clinical/meta/calculator/standard")
def meta_calculator_standard(
    studies: List[Dict[str, Any]] = Body(..., description="研究列表，每项含 effect_size, variance, study_id"),
    use_quality_weight: bool = Body(default=False, description="是否使用质量加权"),
    quality_weight_exponent: float = Body(default=1.0, description="质量权重指数"),
):
    if not studies:
        return {"error": "研究列表不能为空"}
    if use_quality_weight:
        result = StandardMetaCalculator.run_quality_weighted_ma(studies, quality_weight_exponent)
    else:
        result = StandardMetaCalculator.run_standard_ma(studies)
    return result


@router.post("/clinical/meta/calculator/network")
def meta_calculator_network(
    trials: List[Dict[str, Any]] = Body(..., description="临床试验列表，每项含 arms[].treatment_name, arms[].mean_efficacy"),
    indication: str = Body(default="", description="适应症名称"),
):
    if not trials:
        return {"error": "试验列表不能为空"}
    result = NetworkMetaCalculator.run_nma(trials, indication)
    return result


@router.post("/clinical/meta/calculator/sensitivity")
def meta_calculator_sensitivity(
    studies: List[Dict[str, Any]] = Body(..., description="研究列表"),
    method: str = Body(default="loo", description="敏感性分析方法: loo(逐一剔除)/low_quality(低质量剔除)/publication_bias(发表偏倚)/subgroup(亚组)"),
    quality_threshold: float = Body(default=0.5, description="低质量阈值（用于 low_quality 方法）"),
    subgroup_key: str = Body(default="quality_tier", description="亚组分组键（用于 subgroup 方法）"),
):
    if not studies:
        return {"error": "研究列表不能为空"}
    if method == "loo":
        result = StandardMetaCalculator.run_sensitivity_loo(studies)
    elif method == "low_quality":
        result = StandardMetaCalculator.run_sensitivity_low_quality(studies, quality_threshold)
    elif method == "publication_bias":
        result = StandardMetaCalculator.run_publication_bias(studies)
    elif method == "subgroup":
        result = StandardMetaCalculator.run_subgroup(studies, subgroup_key)
    else:
        return {"error": f"未知的敏感性分析方法: {method}，请选择 loo/low_quality/publication_bias/subgroup"}
    return {"method": method, "result": result}
