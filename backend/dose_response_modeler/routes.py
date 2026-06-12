from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Dict, Any

from database.mongodb import get_collection

from dose_response_modeler.modeler import DoseEffectAnalyzer

router = APIRouter(prefix="", tags=["剂量效应分析"])


@router.get("/efficacy/dose-response/{herb_name}")
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


@router.get("/efficacy/dose-response/meta/{herb_name}")
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


@router.get("/efficacy/dose-response/cross-formula/{herb_name}")
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


@router.get("/efficacy/herb/{herb_name}/profile")
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
