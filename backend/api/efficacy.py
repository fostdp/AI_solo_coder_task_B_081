from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Dict, Any

from database.mongodb import get_collection
from database.neo4j_db import run_query

from services.efficacy_scorer import (
    MedicalCaseGenerator,
    EfficacyAggregator,
    TCMSentimentAnalyzer,
    OrdinalRegressionScorer,
)
from services.dose_response import DoseEffectAnalyzer
from services.adverse_reaction import (
    AdverseReactionExtractor,
    FormulaRiskAssessor,
    RiskPairDetector,
)
from services.clinical_trial import (
    ClinicalTrialSimulator,
    StandardMetaAnalysis,
    NetworkMetaAnalysis,
)

router = APIRouter(prefix="/efficacy", tags=["疗效量化与临床证据"])


@router.post("/analyze-text")
def analyze_efficacy_text(
    text: str = Body(..., embed=True, description="古代医案疗效描述文本")
):
    sentiment = TCMSentimentAnalyzer.compute_sentiment(text)
    days = TCMSentimentAnalyzer.extract_days(text)
    grade, score = OrdinalRegressionScorer.predict_grade(sentiment, days)
    grade_labels = OrdinalRegressionScorer.GRADE_LABELS
    return {
        "raw_text": text,
        "sentiment_score": round(sentiment, 4),
        "days_to_effect": days,
        "efficacy_grade": grade,
        "efficacy_grade_label": grade_labels[grade] if grade < len(grade_labels) else "未知",
        "efficacy_score_0_100": score,
    }


@router.get("/formula/{formula_name}")
def get_formula_efficacy(
    formula_name: str,
    num_cases: int = Query(default=20, ge=5, le=200, description="生成医案数量")
):
    formulas_col = get_collection("formulas")
    formula = formulas_col.find_one({"name": formula_name})
    if not formula:
        raise HTTPException(status_code=404, detail=f"方剂 {formula_name} 未找到")
    dynasty = formula.get("dynasty", "宋代")
    indications = formula.get("indications", [])
    gen = MedicalCaseGenerator(seed=hash(formula_name) % 10000)
    cases = gen.generate_cases_for_formula(
        formula_name, dynasty, indications, n=num_cases
    )
    agg = EfficacyAggregator.aggregate(cases)
    return agg


@router.get("/formulas/ranked")
def get_formulas_by_efficacy(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    dynasty: Optional[str] = Query(default=None, description="按朝代过滤"),
    min_total_cases: int = Query(default=8, ge=3)
):
    formulas_col = get_collection("formulas")
    query = {}
    if dynasty:
        query["dynasty"] = dynasty
    cursor = formulas_col.find(query).skip(skip).limit(limit * 3)
    results = []
    for f in cursor:
        gen = MedicalCaseGenerator(seed=hash(f["name"]) % 10000)
        cases = gen.generate_cases_for_formula(
            f["name"], f.get("dynasty", "宋代"),
            f.get("indications", []), n=min_total_cases
        )
        agg = EfficacyAggregator.aggregate(cases)
        results.append({
            "_id": str(f.get("_id", "")),
            "name": f["name"],
            "dynasty": f.get("dynasty"),
            "indications": f.get("indications", [])[:3],
            "herb_count": len(f.get("herbs", [])),
            "avg_efficacy_score": agg["avg_efficacy_score"],
            "efficacy_grade_distribution": agg["efficacy_grade_distribution"],
            "total_cases": agg["total_cases"],
            "avg_days_to_effect": agg["avg_days_to_effect"],
            "confidence_interval": agg["confidence_interval"],
        })
    results.sort(key=lambda x: -x["avg_efficacy_score"])
    return {
        "total": len(results),
        "skip": skip,
        "limit": limit,
        "formulas": results[:limit],
    }


@router.get("/dose-response/{herb_name}")
def get_dose_response_curve(
    herb_name: str,
    formula_name: Optional[str] = Query(default=None),
    indication: Optional[str] = Query(default=None),
):
    herbs_col = get_collection("herbs")
    herb = herbs_col.find_one({"name": herb_name})
    if not herb:
        raise HTTPException(status_code=404, detail=f"中药 {herb_name} 未找到")
    analyzer = DoseEffectAnalyzer(seed=hash(herb_name) % 10000)
    obs = analyzer.simulate_observations(herb_name, n_per_bin=10, bins=8)
    curve = analyzer.fit_curve(obs)
    curve["formula_name"] = formula_name
    curve["indication"] = indication
    safe_dose = None
    from data.tcm_data import TOXIC_HERBS
    if herb_name in TOXIC_HERBS:
        safe_dose = TOXIC_HERBS[herb_name].get("max_safe_dose_g")
        curve["max_safe_dose_g"] = safe_dose
        if safe_dose and curve["optimal_dose_range"][1] > safe_dose:
            curve["optimal_dose_range"][1] = safe_dose
            curve["warnings"] = [f"最优剂量上限超过安全剂量，已截断为 {safe_dose}g"]
    return curve


@router.get("/dose-response/meta/{herb_name}")
def dose_meta_analysis(
    herb_name: str,
    num_studies: int = Query(default=12, ge=3, le=60),
):
    analyzer = DoseEffectAnalyzer(seed=hash(herb_name) % 10000)
    studies = []
    for i in range(num_studies):
        rng_i = analyzer.rng
        low = rng_i.uniform(0.5, 2.0)
        high = rng_i.uniform(4.0, 12.0)
        d_mid = (low + high) / 2
        es = rng_i.uniform(0.2, 0.8)
        var = rng_i.uniform(0.005, 0.05)
        studies.append({
            "study_id": f"STUDY-{i+1:03d}",
            "year": rng_i.randint(1995, 2024),
            "dose_range_g": [round(low, 2), round(high, 2)],
            "midpoint_dose": round(d_mid, 2),
            "effect_size": round(es, 4),
            "variance": round(var, 6),
            "n_patients": rng_i.randint(30, 220),
        })
    result = analyzer.dose_meta_analysis(studies)
    result["herb_name"] = herb_name
    result["input_studies"] = studies
    return result


@router.get("/adverse/herb/{herb_name}")
def get_herb_adverse_profile(herb_name: str):
    from data.tcm_data import TOXIC_HERBS
    if herb_name not in TOXIC_HERBS:
        return {
            "herb_name": herb_name,
            "toxic_flag": False,
            "message": "无记录毒性成分，属于常规安全用药范围",
            "contraindications": [],
            "adverse_reactions": [],
        }
    profile = TOXIC_HERBS[herb_name]
    return {
        "herb_name": herb_name,
        "toxic_flag": True,
        "ld50_mgkg": profile.get("ld50_mgkg"),
        "max_safe_dose_g": profile.get("max_safe_dose_g"),
        "pregnancy_risk": profile.get("pregnancy_risk"),
        "contraindications": profile.get("contraindications", []),
        "toxic_ingredients": profile.get("toxic_ingredients", []),
        "adverse_reactions": profile.get("adverse_reactions", []),
    }


@router.get("/adverse/risk-pairs")
def list_all_risk_pairs(
    risk_level: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    index = RiskPairDetector.build_pair_index()
    pairs = list(index.values())
    if risk_level:
        pairs = [p for p in pairs if p["risk_level"] == risk_level]
    pairs.sort(key=lambda p: -p["risk_score"])
    return {
        "total": len(pairs),
        "risk_levels": list(set(p["risk_level"] for p in pairs)),
        "interaction_types": list(set(p["interaction_type"] for p in pairs)),
        "pairs": pairs[:limit],
    }


@router.post("/adverse/assess-formula")
def assess_formula_risk(
    formula_name: str = Body(..., embed=True),
    herbs: List[str] = Body(..., embed=True, description="方剂组成药物名列表"),
    herb_dosages: Optional[Dict[str, float]] = Body(default=None, embed=True, description="药物名: 剂量(g)"),
):
    if not herbs:
        raise HTTPException(status_code=400, detail="herbs 列表不能为空")
    result = FormulaRiskAssessor.assess(formula_name, herbs, herb_dosages)
    return result


@router.post("/adverse/extract-from-text")
def extract_adverse_from_text(
    text: str = Body(..., embed=True, description="古代医案或本草文献文本"),
    herbs_context: Optional[List[str]] = Body(default=None, embed=True, description="上下文相关药物名列表"),
):
    from services.adverse_reaction import AdverseReactionExtractor
    reactions = AdverseReactionExtractor.extract_from_text(text)
    herb_reactions = {}
    if herbs_context:
        herb_reactions = AdverseReactionExtractor.aggregate_reactions(herbs_context)
    severity_counts = {}
    for r in reactions:
        s = r["severity"]
        severity_counts[s] = severity_counts.get(s, 0) + 1
    return {
        "input_text_length": len(text),
        "reactions_found": len(reactions),
        "severity_distribution": severity_counts,
        "extracted_reactions": reactions,
        "herb_context_reactions": herb_reactions if herbs_context else None,
        "risk_summary": _generate_risk_summary(reactions, herbs_context),
    }


def _generate_risk_summary(reactions, herbs_context=None):
    if not reactions:
        return "未从文本中检测到不良反应描述"
    severe = sum(1 for r in reactions if r["severity"] == "严重")
    moderate = sum(1 for r in reactions if r["severity"] == "中度")
    mild = sum(1 for r in reactions if r["severity"] == "轻度")
    parts = []
    if severe:
        parts.append(f"严重反应{severe}项")
    if moderate:
        parts.append(f"中度反应{moderate}项")
    if mild:
        parts.append(f"轻度反应{mild}项")
    types = list(set(r["reaction_type"] for r in reactions))
    summary = f"检出不良反应{len(reactions)}项：" + "、".join(parts)
    summary += f"；涉及类型：{'、'.join(types)}"
    if herbs_context:
        toxic = [h for h in herbs_context if h in __import__("services.adverse_reaction", fromlist=["AdverseReactionExtractor"]).__module__]
        from data.tcm_data import TOXIC_HERBS
        toxic_in_ctx = [h for h in herbs_context if h in TOXIC_HERBS]
        if toxic_in_ctx:
            summary += f"；上下文含毒性中药：{'、'.join(toxic_in_ctx)}"
    return summary


@router.get("/adverse/network-annotations")
def get_network_risk_annotations(
    min_risk_level: str = Query(default="中", description="低/中/高/极高"),
    limit: int = Query(default=100, ge=1, le=1000),
):
    level_map = {"低": 0.2, "中": 0.45, "高": 0.75, "极高": 1.0}
    threshold = level_map.get(min_risk_level, 0.45)
    index = RiskPairDetector.build_pair_index()
    pairs = [p for p in index.values() if p["risk_score"] / 100.0 >= threshold]
    pairs.sort(key=lambda p: -p["risk_score"])
    color_map = {"极高": "#ff0000", "高": "#ff4444", "中": "#ff9800", "低": "#ffc107"}
    edges = []
    for p in pairs[:limit]:
        edges.append({
            "source": p["herb_a"],
            "target": p["herb_b"],
            "label": p["interaction_type"],
            "risk_level": p["risk_level"],
            "risk_score": p["risk_score"],
            "stroke": color_map.get(p["risk_level"], "#ff9800"),
            "dash_array": "8,4",
            "weight": 3.0 + p["risk_score"] / 25.0,
        })
    return {
        "query_threshold": min_risk_level,
        "total_risk_edges": len(pairs),
        "returned_edges": len(edges),
        "risk_edges": edges,
        "color_map": color_map,
    }


@router.get("/clinical/trials")
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


@router.get("/clinical/meta-analysis")
def run_meta_analysis(
    indication: str = Query(..., description="适应症"),
    num_trials: int = Query(default=10, ge=3, le=50),
):
    sim = ClinicalTrialSimulator(seed=hash(indication) % 10000)
    trials = sim.generate_trials(indication, n_trials=num_trials)
    result = StandardMetaAnalysis.compare_classical_vs_modern(trials, indication)
    result["raw_trials_count"] = len(trials)
    return result


@router.get("/clinical/network-meta")
def run_network_meta_analysis(
    indication: str = Query(..., description="适应症"),
    num_trials: int = Query(default=15, ge=5, le=80),
):
    sim = ClinicalTrialSimulator(seed=hash(indication) % 10000)
    trials = sim.generate_trials(indication, n_trials=num_trials)
    result = NetworkMetaAnalysis.run(trials, indication)
    result["trials_count"] = len(trials)
    return result


@router.get("/summary/indication/{indication}")
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


@router.get("/formulas/scores-batch")
def get_formulas_efficacy_scores(
    names: str = Query(..., description="逗号分隔的方剂名"),
    num_cases: int = Query(default=12, ge=5, le=50),
):
    formulas_col = get_collection("formulas")
    name_list = [n.strip() for n in names.split(",") if n.strip()]
    results = {}
    for name in name_list:
        formula = formulas_col.find_one({"name": name})
        if not formula:
            results[name] = {"efficacy_score": None, "grade_distribution": {}, "days_to_effect": None}
            continue
        gen = MedicalCaseGenerator(seed=hash(name) % 10000)
        cases = gen.generate_cases_for_formula(
            name, formula.get("dynasty", "宋代"),
            formula.get("indications", []), n=num_cases
        )
        agg = EfficacyAggregator.aggregate(cases)
        results[name] = {
            "efficacy_score": agg["avg_efficacy_score"],
            "grade_distribution": agg["efficacy_grade_distribution"],
            "days_to_effect": agg["avg_days_to_effect"],
            "confidence_interval": agg["confidence_interval"],
            "total_cases": agg["total_cases"],
        }
    return results


@router.get("/clinical/formula-evidence-batch")
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


@router.get("/formula/{formula_name}/quick-score")
def get_formula_quick_score(formula_name: str):
    formulas_col = get_collection("formulas")
    formula = formulas_col.find_one({"name": formula_name})
    if not formula:
        return {"formula_name": formula_name, "efficacy_score": None, "risk_level": None}
    gen = MedicalCaseGenerator(seed=hash(formula_name) % 10000)
    cases = gen.generate_cases_for_formula(
        formula_name, formula.get("dynasty", "宋代"),
        formula.get("indications", []), n=10
    )
    agg = EfficacyAggregator.aggregate(cases)
    herbs = []
    if isinstance(formula.get("herbs"), list) and formula["herbs"]:
        if isinstance(formula["herbs"][0], dict):
            herbs = [h.get("name", "") for h in formula["herbs"]]
        else:
            herbs = formula["herbs"]
    risk = FormulaRiskAssessor.assess(formula_name, herbs)
    from data.tcm_data import CLASSICAL_FORMULAS_BY_DISEASE
    clinical_indications = []
    for ind, fnames in CLASSICAL_FORMULAS_BY_DISEASE.items():
        if formula_name in fnames:
            clinical_indications.append(ind)
    return {
        "formula_name": formula_name,
        "efficacy_score": agg["avg_efficacy_score"],
        "efficacy_grade_distribution": agg["efficacy_grade_distribution"],
        "avg_days_to_effect": agg["avg_days_to_effect"],
        "confidence_interval": agg["confidence_interval"],
        "total_cases": agg["total_cases"],
        "risk_level": risk["overall_risk_level"],
        "risk_score": risk["overall_risk_score"],
        "risk_pairs_count": len(risk["risk_pairs"]),
        "warnings": risk["warnings"],
        "safe_use_guidance": risk["safe_use_guidance"],
        "clinical_indications": clinical_indications,
        "has_clinical_evidence": len(clinical_indications) > 0,
    }


@router.get("/herb/{herb_name}/profile")
def get_herb_full_profile(herb_name: str):
    herbs_col = get_collection("herbs")
    herb = herbs_col.find_one({"name": herb_name})
    if not herb:
        raise HTTPException(status_code=404, detail=f"中药 {herb_name} 未找到")
    from data.tcm_data import TOXIC_HERBS
    profile = {
        "name": herb_name,
        "category": herb.get("category"),
        "nature": herb.get("nature"),
        "flavor": herb.get("flavor", []),
        "meridians": herb.get("meridians", []),
        "is_toxic": herb_name in TOXIC_HERBS,
    }
    if herb_name in TOXIC_HERBS:
        tp = TOXIC_HERBS[herb_name]
        profile["toxicity"] = {
            "toxic_ingredients": tp.get("toxic_ingredients", []),
            "ld50_mgkg": tp.get("ld50_mgkg"),
            "max_safe_dose_g": tp.get("max_safe_dose_g"),
            "pregnancy_risk": tp.get("pregnancy_risk"),
            "contraindications": tp.get("contraindications", []),
            "adverse_reactions": tp.get("adverse_reactions", []),
        }
    analyzer = DoseEffectAnalyzer(seed=hash(herb_name) % 10000)
    obs = analyzer.simulate_observations(herb_name, n_per_bin=8, bins=7)
    curve = analyzer.fit_curve(obs)
    profile["dose_response"] = {
        "optimal_dose_range": curve["optimal_dose_range"],
        "r_squared": curve["r_squared"],
        "model_type": curve["model_type"],
    }
    if herb_name in TOXIC_HERBS:
        profile["dose_response"]["max_safe_dose_g"] = TOXIC_HERBS[herb_name].get("max_safe_dose_g")
    return profile


@router.get("/dose-response/cross-formula/{herb_name}")
def cross_formula_dose_comparison(herb_name: str):
    formulas_col = get_collection("formulas")
    formulas_with_herb = []
    for f in formulas_col.find({"herbs.name": herb_name}).limit(30):
        herbs_list = f.get("herbs", [])
        dose_for_herb = None
        for h in herbs_list:
            if isinstance(h, dict) and h.get("name") == herb_name:
                raw = h.get("dosage", "")
                try:
                    dose_for_herb = float("".join(c for c in str(raw) if c.isdigit() or c == "."))
                except (ValueError, TypeError):
                    pass
                break
        formulas_with_herb.append({
            "formula_name": f["name"],
            "dynasty": f.get("dynasty"),
            "indications": f.get("indications", [])[:3],
            "herb_dose_g": dose_for_herb,
            "herb_count": len(herbs_list),
        })

    analyzer = DoseEffectAnalyzer(seed=hash(herb_name) % 10000)
    obs = analyzer.simulate_observations(herb_name, n_per_bin=8, bins=7)
    curve = analyzer.fit_curve(obs)
    optimal = curve["optimal_dose_range"]

    doses = [fd["herb_dose_g"] for fd in formulas_with_herb if fd["herb_dose_g"] is not None]
    dose_stats = {}
    if doses:
        dose_stats = {
            "min": round(min(doses), 2),
            "max": round(max(doses), 2),
            "mean": round(sum(doses) / len(doses), 2),
            "median": round(sorted(doses)[len(doses) // 2], 2),
            "count": len(doses),
        }

    within = [fd for fd in formulas_with_herb
              if fd["herb_dose_g"] is not None
              and optimal[0] <= fd["herb_dose_g"] <= optimal[1]]
    above = [fd for fd in formulas_with_herb
             if fd["herb_dose_g"] is not None and fd["herb_dose_g"] > optimal[1]]
    below = [fd for fd in formulas_with_herb
             if fd["herb_dose_g"] is not None and fd["herb_dose_g"] < optimal[0]]

    return {
        "herb_name": herb_name,
        "optimal_dose_range": optimal,
        "r_squared": curve["r_squared"],
        "total_formulas_found": len(formulas_with_herb),
        "formulas_with_dose_data": len(doses),
        "dose_statistics": dose_stats,
        "within_optimal": {"count": len(within), "formulas": within[:10]},
        "above_optimal": {"count": len(above), "formulas": above[:10]},
        "below_optimal": {"count": len(below), "formulas": below[:10]},
    }
