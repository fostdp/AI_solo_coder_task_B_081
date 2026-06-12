import math
import random
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from data.tcm_data import (
    CLINICAL_TRIAL_MODERN_TREATMENTS,
    CLASSICAL_FORMULAS_BY_DISEASE,
)
from clinical_trial_integrator.meta_service import (
    StandardMetaCalculator,
    NetworkMetaCalculator,
)


class MetaAnalysisSensitivity:

    @staticmethod
    def leave_one_out(studies: List[Dict[str, Any]]) -> Dict[str, Any]:
        return StandardMetaCalculator.run_sensitivity_loo(studies)

    @staticmethod
    def low_quality_exclusion(studies: List[Dict[str, Any]],
                              quality_threshold: float = 0.5) -> Dict[str, Any]:
        return StandardMetaCalculator.run_sensitivity_low_quality(studies, quality_threshold)

    @staticmethod
    def publication_bias(studies: List[Dict[str, Any]]) -> Dict[str, Any]:
        return StandardMetaCalculator.run_publication_bias(studies)

    @staticmethod
    def subgroup_analysis(studies: List[Dict[str, Any]],
                          subgroup_key: str = "quality_tier") -> Dict[str, Any]:
        return StandardMetaCalculator.run_subgroup(studies, subgroup_key)


class QualityWeightedMetaAnalysis:

    @staticmethod
    def run(studies: List[Dict[str, Any]],
            quality_weight_exponent: float = 1.0) -> Dict[str, Any]:
        return StandardMetaCalculator.run_quality_weighted_ma(studies, quality_weight_exponent)


class ClinicalTrialSimulator:

    DESIGNS = ["随机双盲安慰剂对照", "随机双盲阳性对照", "开放标签随机对照",
               "多中心随机对照", "单中心随机对照"]
    LOCATIONS = ["北京", "上海", "广州", "成都", "南京", "武汉", "天津", "杭州", "西安"]
    YEAR_RANGE = (2005, 2024)

    TYPICAL_FORMULA_EFFICACY_BONUS = {
        "麻黄汤": 0.05, "桂枝汤": 0.04, "小柴胡汤": 0.08, "银翘散": 0.06,
        "止嗽散": 0.04, "二陈汤": 0.03, "麻杏石甘汤": 0.07, "半夏泻心汤": 0.06,
        "四君子汤": 0.05, "理中丸": 0.04, "酸枣仁汤": 0.05, "天王补心丹": 0.04,
        "天麻钩藤饮": 0.06, "镇肝熄风汤": 0.05, "六味地黄丸": 0.05,
        "金匮肾气丸": 0.04, "归脾汤": 0.06, "龙胆泻肝汤": 0.04, "default": 0.0,
    }

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def _quality_score(self, design: str, year: int) -> float:
        base = 0.6 if "双盲" in design else 0.4
        base += 0.1 if "多中心" in design else 0.0
        year_bonus = min(0.2, (year - 2000) / 150)
        return round(min(0.95, base + year_bonus + self.rng.uniform(-0.05, 0.05)), 3)

    def generate_trials(self, indication: str, n_trials: int = 8) -> List[Dict[str, Any]]:
        modern = CLINICAL_TRIAL_MODERN_TREATMENTS.get(indication, [])
        classics = CLASSICAL_FORMULAS_BY_DISEASE.get(indication, [])
        if not modern and not classics:
            return []
        all_treatments = []
        for t in modern:
            all_treatments.append({**t, "category": "现代方案"})
        for fname in classics:
            bonus = self.TYPICAL_FORMULA_EFFICACY_BONUS.get(
                fname, self.TYPICAL_FORMULA_EFFICACY_BONUS["default"])
            all_treatments.append({
                "name": fname,
                "type": "经典古方",
                "typical_efficacy": 0.68 + bonus,
                "se": 0.07,
                "ae_rate": 0.06,
                "category": "古代经典方",
            })
        trials = []
        for i in range(n_trials):
            year = self.rng.randint(*self.YEAR_RANGE)
            design = self.rng.choice(self.DESIGNS)
            use_classic = self.rng.random() < 0.55
            classic_arms = [t for t in all_treatments if t["category"] == "古代经典方"]
            modern_arms = [t for t in all_treatments if t["category"] == "现代方案"]
            if use_classic and classic_arms and modern_arms:
                arms = [self.rng.choice(classic_arms), self.rng.choice(modern_arms)]
            elif len(all_treatments) >= 2:
                arms = self.rng.sample(all_treatments, k=2)
            elif all_treatments:
                arms = [all_treatments[0]]
            else:
                continue
            total_n = self.rng.randint(60, 260)
            arm_n = total_n // max(len(arms), 1)
            trial_arms = []
            for arm in arms:
                noise = self.rng.gauss(0, arm["se"] * 0.5)
                eff = max(0.3, min(0.95, arm["typical_efficacy"] + noise))
                ae = max(0.01, min(0.4, arm["ae_rate"] + self.rng.gauss(0, 0.03)))
                trial_arms.append({
                    "treatment_name": arm["name"],
                    "treatment_type": arm.get("category", arm["type"]),
                    "sample_size": arm_n + self.rng.randint(-10, 20),
                    "mean_efficacy": round(eff, 4),
                    "std_efficacy": round(arm["se"] * 2.0, 4),
                    "adverse_event_rate": round(ae, 4),
                })
            quality = self._quality_score(design, year)
            loc = self.rng.choice(self.LOCATIONS)
            title = f"{indication}的{trial_arms[0]['treatment_name']}与" \
                    f"{trial_arms[1]['treatment_name']}对比临床研究" if len(trial_arms) >= 2 \
                else f"{trial_arms[0]['treatment_name']}治疗{indication}的临床观察"
            trials.append({
                "trial_id": f"CTR{year:04d}{i+1:04d}",
                "title": title,
                "year": year,
                "indication": indication,
                "design": design,
                "arms": trial_arms,
                "total_sample_size": sum(a["sample_size"] for a in trial_arms),
                "duration_weeks": self.rng.choice([2, 4, 8, 12, 16, 24]),
                "location": loc,
                "quality_score": quality,
            })
        trials.sort(key=lambda t: t["year"], reverse=True)
        return trials


class StandardMetaAnalysis:

    @staticmethod
    def _inverse_variance(studies: List[Dict[str, Any]]) -> Dict[str, Any]:
        return StandardMetaCalculator.run_standard_ma(studies)

    @classmethod
    def compare_classical_vs_modern(cls, trials: List[Dict[str, Any]],
                                    indication: str,
                                    use_quality_weight: bool = False,
                                    run_sensitivity: bool = False) -> Dict[str, Any]:
        studies = []
        for t in trials:
            classic_arms = [a for a in t["arms"] if a["treatment_type"] == "古代经典方"]
            modern_arms = [a for a in t["arms"] if a["treatment_type"] != "古代经典方"]
            if not classic_arms or not modern_arms:
                continue
            c = classic_arms[0]
            m = modern_arms[0]
            nc = c["sample_size"]
            nm = m["sample_size"]
            pooled_s = math.sqrt(
                ((nc - 1) * c["std_efficacy"] ** 2 + (nm - 1) * m["std_efficacy"] ** 2)
                / max(nc + nm - 2, 1))
            smd = (c["mean_efficacy"] - m["mean_efficacy"]) / pooled_s if pooled_s > 0 else 0.0
            var = 1 / nc + 1 / nm + smd ** 2 / (2 * (nc + nm))
            studies.append({
                "study_id": t["trial_id"],
                "year": t["year"],
                "effect_size": smd,
                "variance": var,
                "n": nc + nm,
                "quality": t["quality_score"],
                "classical_arm": c["treatment_name"],
                "modern_arm": m["treatment_name"],
            })
        if not studies:
            return {
                "indication": indication,
                "comparison": "经典方vs现代方案",
                "pooled_effect_size": 0.0,
                "ci_95": [0.0, 0.0],
                "p_value": 1.0,
                "i_squared": 0.0,
                "heterogeneity_p": 1.0,
                "trials_included": 0,
                "total_patients": 0,
                "forest_plot_data": [],
                "conclusion": "未找到符合条件的头对头比较研究",
            }

        if use_quality_weight:
            result = QualityWeightedMetaAnalysis.run(studies)
        else:
            result = cls._inverse_variance(studies)

        result["indication"] = indication
        result["comparison"] = "经典方vs现代方案（SMD）"

        if run_sensitivity:
            loo = MetaAnalysisSensitivity.leave_one_out(studies)
            lq_ex = MetaAnalysisSensitivity.low_quality_exclusion(studies)
            pub_bias = MetaAnalysisSensitivity.publication_bias(studies)
            subgroups = MetaAnalysisSensitivity.subgroup_analysis(studies)
            result["sensitivity_analysis"] = {
                "leave_one_out": loo,
                "low_quality_exclusion": lq_ex,
                "publication_bias": pub_bias,
                "subgroup_analysis": subgroups,
            }
            overall_robust = (
                loo.get("result_robust", False)
                and lq_ex.get("direction_consistent", False)
                and pub_bias.get("bias_level", "高") == "低"
            )
            result["overall_confidence"] = "高" if overall_robust else "中" if loo.get("result_robust") else "低"
            result["sensitivity_conclusion"] = (
                "敏感性分析提示结果稳健可信"
                if overall_robust
                else "敏感性分析发现潜在不稳健因素，需谨慎解读结论"
            )

        return result


class NetworkMetaAnalysis:

    @classmethod
    def run(cls, trials: List[Dict[str, Any]], indication: str) -> Dict[str, Any]:
        return NetworkMetaCalculator.run_nma(trials, indication)
