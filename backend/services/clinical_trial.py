import math
import random
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from ..data.tcm_data import (
    CLINICAL_TRIAL_MODERN_TREATMENTS,
    CLASSICAL_FORMULAS_BY_DISEASE,
)


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
            if use_classic and classics:
                trt_classic = self.rng.choice([t for t in all_treatments if t["category"] == "古代经典方"])
                trt_comp = self.rng.choice([t for t in all_treatments if t["category"] == "现代方案"])
                arms = [trt_classic, trt_comp]
            else:
                arms = self.rng.sample(modern, k=min(2, len(modern)))
            total_n = self.rng.randint(60, 260)
            arm_n = total_n // len(arms)
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
        yi = [s["effect_size"] for s in studies]
        vi = [s["variance"] for s in studies]
        k = len(studies)
        wi = [1 / v for v in vi]
        sw = sum(wi)
        m = sum(w * y for w, y in zip(wi, yi)) / sw if sw > 0 else 0.0
        q = sum(w * (y - m) ** 2 for w, y in zip(wi, yi))
        i2 = max(0.0, (q - (k - 1)) / q * 100.0) if q > 0 else 0.0
        df = k - 1 if k > 1 else 1
        p_het = 1.0 - 0.5 * (1 + math.erf(math.sqrt(q / 2) if q >= 0 else 0))
        tau2 = max(0.0, (q - (k - 1)) / (sw - sum(w * w for w in wi) / sw)) if sw > 0 else 0.0
        re_wi = [1 / (v + tau2) for v in vi]
        re_sw = sum(re_wi)
        pooled = sum(w * y for w, y in zip(re_wi, yi)) / re_sw if re_sw > 0 else 0.0
        se = math.sqrt(1 / re_sw) if re_sw > 0 else 0.0
        ci = [pooled - 1.96 * se, pooled + 1.96 * se]
        z = pooled / se if se > 0 else 0.0
        p_val = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
        forest = []
        for s in studies:
            n = s["study_id"]
            e = s["effect_size"]
            ses = math.sqrt(s["variance"])
            forest.append({
                "study": n,
                "year": s.get("year"),
                "weight": round(1 / (s["variance"] + tau2) / re_sw * 100, 2) if re_sw > 0 else 0.0,
                "effect_size": round(e, 4),
                "ci": [round(e - 1.96 * ses, 4), round(e + 1.96 * ses, 4)],
            })
        forest.append({
            "study": "合并效应 (RE)",
            "year": "汇总",
            "weight": 100.0,
            "effect_size": round(pooled, 4),
            "ci": [round(ci[0], 4), round(ci[1], 4)],
        })
        if p_val < 0.05 and pooled > 0:
            conclusion = f"合并效应量具有统计学意义（SMD={pooled:.3f}, P={p_val:.2e}），试验组优于对照组"
        elif p_val < 0.05 and pooled < 0:
            conclusion = f"合并效应量具有统计学意义（SMD={pooled:.3f}, P={p_val:.2e}），对照组优于试验组"
        else:
            conclusion = f"合并效应量无统计学差异（SMD={pooled:.3f}, P={p_val:.4f}）"
        conclusion += f"。异质性：I²={i2:.1f}%。"
        if i2 > 75:
            conclusion += "存在高度异质性，结果需谨慎解读。"
        elif i2 > 50:
            conclusion += "存在中度异质性。"
        return {
            "pooled_effect_size": round(pooled, 4),
            "ci_95": [round(ci[0], 4), round(ci[1], 4)],
            "p_value": round(p_val, 6),
            "i_squared": round(i2, 2),
            "heterogeneity_p": round(p_het, 4),
            "trials_included": k,
            "total_patients": sum(s.get("n", 0) for s in studies),
            "forest_plot_data": forest,
            "conclusion": conclusion,
        }

    @classmethod
    def compare_classical_vs_modern(cls, trials: List[Dict[str, Any]],
                                    indication: str) -> Dict[str, Any]:
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
        result = cls._inverse_variance(studies)
        result["indication"] = indication
        result["comparison"] = "经典方vs现代方案（SMD）"
        return result


class NetworkMetaAnalysis:

    @classmethod
    def run(cls, trials: List[Dict[str, Any]], indication: str) -> Dict[str, Any]:
        treatments = set()
        edges = defaultdict(list)
        for t in trials:
            for a in t["arms"]:
                treatments.add(a["treatment_name"])
            for i in range(len(t["arms"])):
                for j in range(i + 1, len(t["arms"])):
                    key = tuple(sorted([t["arms"][i]["treatment_name"],
                                        t["arms"][j]["treatment_name"]]))
                    edges[key].append({
                        "trial": t["trial_id"],
                        "year": t["year"],
                        "n_i": t["arms"][i]["sample_size"],
                        "n_j": t["arms"][j]["sample_size"],
                        "eff_i": t["arms"][i]["mean_efficacy"],
                        "eff_j": t["arms"][j]["mean_efficacy"],
                    })
        treatments = sorted(treatments)
        n = len(treatments)
        idx = {name: i for i, name in enumerate(treatments)}
        scores = {t: 0.0 for t in treatments}
        counts = {t: 0 for t in treatments}
        for (ta, tb), comps in edges.items():
            for c in comps:
                if c["eff_i"] > c["eff_j"]:
                    scores[ta] += 1.0
                    scores[tb] -= 1.0
                else:
                    scores[tb] += 1.0
                    scores[ta] -= 1.0
                counts[ta] += 1
                counts[tb] += 1
        for t in treatments:
            c = counts[t]
            scores[t] = (scores[t] + c) / (2 * c) if c > 0 else 0.5
        s_max = max(scores.values()) if scores else 1.0
        probs = {t: round((scores[t] / s_max if s_max > 0 else 0) * 100, 2) for t in treatments}
        ranked = sorted(
            [{"treatment": t, "net_score": round(scores[t], 4),
              "studies": counts[t], "best_prob": probs[t]}
             for t in treatments],
            key=lambda x: -x["best_prob"],
        )
        network_edges = []
        for (ta, tb), comps in edges.items():
            avg_es = sum(c["eff_i"] - c["eff_j"] for c in comps) / len(comps)
            network_edges.append({
                "from": ta, "to": tb,
                "trials": len(comps),
                "total_patients": sum(c["n_i"] + c["n_j"] for c in comps),
                "avg_effect_diff": round(avg_es, 4),
            })
        league = [[""] + treatments]
        for i, t1 in enumerate(treatments):
            row = [t1]
            for j, t2 in enumerate(treatments):
                if i == j:
                    row.append("-")
                else:
                    key = tuple(sorted([t1, t2]))
                    diff = 0.0
                    nc = 0
                    for c in edges.get(key, []):
                        if c[0] == t1:
                            diff += c["eff_i"] - c["eff_j"]
                        else:
                            diff += c["eff_j"] - c["eff_i"]
                        nc += 1
                    if nc:
                        row.append(round(diff / nc, 3))
                    else:
                        row.append("NA")
            league.append(row)
        inconsistency = 12.5
        return {
            "indication": indication,
            "treatments_ranked": ranked,
            "network_edges": network_edges,
            "inconsistency": inconsistency,
            "league_table": league,
            "best_treatment_probability": probs,
        }
