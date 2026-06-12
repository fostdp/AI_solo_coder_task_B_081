from fastapi import APIRouter, Body
from typing import List, Dict, Any

from meta_analysis_service.calculator import (
    StandardMetaCalculator,
    NetworkMetaCalculator,
)

router = APIRouter(prefix="/meta", tags=["Meta分析计算服务"])


@router.post("/standard")
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


@router.post("/network")
def meta_calculator_network(
    trials: List[Dict[str, Any]] = Body(..., description="临床试验列表，每项含 arms[].treatment_name, arms[].mean_efficacy"),
    indication: str = Body(default="", description="适应症名称"),
):
    if not trials:
        return {"error": "试验列表不能为空"}
    result = NetworkMetaCalculator.run_nma(trials, indication)
    return result


@router.post("/sensitivity")
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
