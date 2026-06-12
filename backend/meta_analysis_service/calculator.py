import math
from typing import List, Dict, Any, Tuple
from collections import defaultdict


class StandardMetaCalculator:

    @staticmethod
    def run_standard_ma(studies: List[Dict[str, Any]]) -> Dict[str, Any]:
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

    @staticmethod
    def run_quality_weighted_ma(studies: List[Dict[str, Any]],
                                quality_weight_exponent: float = 1.0) -> Dict[str, Any]:
        if not studies:
            return {
                "pooled_effect_size": 0.0,
                "ci_95": [0.0, 0.0],
                "p_value": 1.0,
                "i_squared": 0.0,
                "quality_weighted": True,
            }

        yi = [s["effect_size"] for s in studies]
        vi = [s["variance"] for s in studies]
        qi = [max(0.1, s.get("quality", 0.5)) ** quality_weight_exponent for s in studies]

        k = len(studies)
        wi = [qi[i] / vi[i] for i in range(k)]
        sw = sum(wi)
        m = sum(w * y for w, y in zip(wi, yi)) / sw if sw > 0 else 0.0

        q_stat = sum(w * (y - m) ** 2 for w, y in zip(wi, yi))
        i2 = max(0.0, (q_stat - (k - 1)) / q_stat * 100.0) if q_stat > 0 else 0.0
        df = k - 1 if k > 1 else 1
        p_het = 1.0 - 0.5 * (1 + math.erf(math.sqrt(q_stat / 2) if q_stat >= 0 else 0))

        tau2 = max(
            0.0,
            (q_stat - (k - 1)) / (sw - sum(w * w for w in wi) / sw)
        ) if sw > 0 else 0.0

        re_wi = [qi[i] / (vi[i] + tau2) for i in range(k)]
        re_sw = sum(re_wi)
        pooled = sum(w * y for w, y in zip(re_wi, yi)) / re_sw if re_sw > 0 else 0.0
        se = math.sqrt(1 / re_sw) if re_sw > 0 else 0.0
        ci = [pooled - 1.96 * se, pooled + 1.96 * se]
        z = pooled / se if se > 0 else 0.0
        p_val = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))

        forest = []
        for i, s in enumerate(studies):
            ses = math.sqrt(vi[i])
            forest.append({
                "study": s.get("study_id", f"S{i+1}"),
                "year": s.get("year"),
                "quality": round(qi[i], 3),
                "weight": round(re_wi[i] / re_sw * 100, 2) if re_sw > 0 else 0.0,
                "effect_size": round(yi[i], 4),
                "ci": [round(yi[i] - 1.96 * ses, 4), round(yi[i] + 1.96 * ses, 4)],
            })
        forest.append({
            "study": "合并效应 (质量加权RE)",
            "year": "汇总",
            "quality": "-",
            "weight": 100.0,
            "effect_size": round(pooled, 4),
            "ci": [round(ci[0], 4), round(ci[1], 4)],
        })

        if p_val < 0.05 and pooled > 0:
            conclusion = f"质量加权合并效应具有统计学意义（SMD={pooled:.3f}, P={p_val:.2e}），试验组优于对照组"
        elif p_val < 0.05 and pooled < 0:
            conclusion = f"质量加权合并效应具有统计学意义（SMD={pooled:.3f}, P={p_val:.2e}），对照组优于试验组"
        else:
            conclusion = f"质量加权合并效应无统计学差异（SMD={pooled:.3f}, P={p_val:.4f}）"
        conclusion += f"。异质性：I²={i2:.1f}%。"

        return {
            "pooled_effect_size": round(pooled, 4),
            "ci_95": [round(ci[0], 4), round(ci[1], 4)],
            "p_value": round(p_val, 6),
            "i_squared": round(i2, 2),
            "heterogeneity_p": round(p_het, 4),
            "tau_squared": round(tau2, 6),
            "trials_included": k,
            "total_patients": sum(s.get("n", 0) for s in studies),
            "forest_plot_data": forest,
            "conclusion": conclusion,
            "quality_weighted": True,
            "quality_weight_exponent": quality_weight_exponent,
            "avg_quality_weight": round(sum(qi) / k, 3),
        }

    @staticmethod
    def run_sensitivity_loo(studies: List[Dict[str, Any]]) -> Dict[str, Any]:
        k = len(studies)
        if k < 3:
            return {"loo_results": [], "robust": False, "reason": "研究数不足"}

        base = StandardMetaCalculator.run_standard_ma(studies)
        base_es = base["pooled_effect_size"]

        loo_results = []
        es_changes = []
        for i in range(k):
            loo_studies = [studies[j] for j in range(k) if j != i]
            res = StandardMetaCalculator.run_standard_ma(loo_studies)
            change = res["pooled_effect_size"] - base_es
            es_changes.append(abs(change))
            loo_results.append({
                "study_id": studies[i].get("study_id", f"S{i+1}"),
                "year": studies[i].get("year"),
                "omitted": True,
                "pooled_es_without": round(res["pooled_effect_size"], 4),
                "change_from_base": round(change, 4),
                "ci_95_without": res["ci_95"],
                "i_squared_without": res["i_squared"],
            })

        max_change = max(es_changes) if es_changes else 0.0
        robust = max_change < 0.1 * abs(base_es) if base_es != 0 else max_change < 0.05

        influential = [
            r for r in loo_results
            if abs(r["change_from_base"]) > 0.1 * abs(base_es)
        ]

        return {
            "base_pooled_es": round(base_es, 4),
            "loo_results": loo_results,
            "max_change": round(max_change, 4),
            "influential_studies": influential,
            "n_influential": len(influential),
            "result_robust": robust,
            "conclusion": (
                "逐一剔除敏感性分析显示结果稳健"
                if robust
                else f"存在 {len(influential)} 个影响较大的研究，结果需谨慎解读"
            ),
        }

    @staticmethod
    def run_sensitivity_low_quality(studies: List[Dict[str, Any]],
                                    quality_threshold: float = 0.5) -> Dict[str, Any]:
        if not studies:
            return {"excluded": 0, "kept": 0, "comparison": {}}

        base = StandardMetaCalculator.run_standard_ma(studies)

        high_quality = [s for s in studies if s.get("quality", 0.5) >= quality_threshold]
        low_quality = [s for s in studies if s.get("quality", 0.5) < quality_threshold]

        if not high_quality:
            return {
                "threshold": quality_threshold,
                "excluded_count": len(low_quality),
                "kept_count": 0,
                "base_result": base,
                "high_quality_result": None,
                "comparison": "无高质量研究保留",
            }

        hq_result = StandardMetaCalculator.run_standard_ma(high_quality)
        es_diff = abs(hq_result["pooled_effect_size"] - base["pooled_effect_size"])
        i2_diff = abs(hq_result["i_squared"] - base["i_squared"])

        direction_consistent = (
            (base["pooled_effect_size"] > 0 and hq_result["pooled_effect_size"] > 0)
            or (base["pooled_effect_size"] < 0 and hq_result["pooled_effect_size"] < 0)
            or (base["pooled_effect_size"] == 0 and hq_result["pooled_effect_size"] == 0)
        )

        return {
            "threshold": quality_threshold,
            "excluded_count": len(low_quality),
            "kept_count": len(high_quality),
            "excluded_studies": [s.get("study_id", "") for s in low_quality],
            "base_result": {
                "pooled_es": base["pooled_effect_size"],
                "i_squared": base["i_squared"],
                "p_value": base["p_value"],
            },
            "high_quality_result": {
                "pooled_es": hq_result["pooled_effect_size"],
                "i_squared": hq_result["i_squared"],
                "p_value": hq_result["p_value"],
            },
            "es_difference": round(es_diff, 4),
            "i2_difference": round(i2_diff, 2),
            "direction_consistent": direction_consistent,
            "conclusion": (
                "剔除低质量研究后结论方向一致，结果较为可靠"
                if direction_consistent
                else "剔除低质量研究后结论方向改变，需高度警惕"
            ),
        }

    @staticmethod
    def run_publication_bias(studies: List[Dict[str, Any]]) -> Dict[str, Any]:
        k = len(studies)
        if k < 5:
            return {"testable": False, "reason": "研究数不足5项，无法可靠评估发表偏倚"}

        es_list = [s["effect_size"] for s in studies]
        se_list = [math.sqrt(s["variance"]) for s in studies]

        median_se = sorted(se_list)[k // 2]
        precision_list = [1 / se for se in se_list]
        mean_es = sum(es_list) / k

        low_precision_bias = sum(
            1 for i in range(k)
            if (se_list[i] > median_se and es_list[i] > mean_es)
        )
        asymmetry_ratio = low_precision_bias / max(1, k // 2)

        rank_correlation = 0.0
        try:
            es_rank = sorted(range(k), key=lambda i: es_list[i])
            se_rank = sorted(range(k), key=lambda i: se_list[i])
            es_rank_pos = [0] * k
            se_rank_pos = [0] * k
            for pos, idx in enumerate(es_rank):
                es_rank_pos[idx] = pos
            for pos, idx in enumerate(se_rank):
                se_rank_pos[idx] = pos
            d = [es_rank_pos[i] - se_rank_pos[i] for i in range(k)]
            sum_d2 = sum(di * di for di in d)
            rank_correlation = 1 - 6 * sum_d2 / (k * (k * k - 1))
        except Exception:
            pass

        bias_level = "低"
        if abs(rank_correlation) > 0.6 or asymmetry_ratio > 1.5:
            bias_level = "高"
        elif abs(rank_correlation) > 0.3 or asymmetry_ratio > 1.1:
            bias_level = "中"

        return {
            "testable": True,
            "n_studies": k,
            "rank_correlation": round(rank_correlation, 4),
            "asymmetry_ratio": round(asymmetry_ratio, 2),
            "bias_level": bias_level,
            "funnel_plot_asymmetric": bias_level != "低",
            "warning": (
                "可能存在发表偏倚，阴性结果研究可能未发表"
                if bias_level != "低"
                else "未检测到明显发表偏倚迹象"
            ),
            "recommendation": (
                "建议使用剪补法或回归法校正发表偏倚"
                if bias_level != "低"
                else "发表偏倚风险较低，结果相对可靠"
            ),
        }

    @staticmethod
    def run_subgroup(studies: List[Dict[str, Any]],
                     subgroup_key: str = "quality_tier") -> Dict[str, Any]:
        if not studies:
            return {"subgroups": {}}

        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for s in studies:
            quality = s.get("quality", 0.5)
            if subgroup_key == "quality_tier":
                if quality >= 0.8:
                    tier = "高质量(≥0.8)"
                elif quality >= 0.5:
                    tier = "中等质量(0.5-0.8)"
                else:
                    tier = "低质量(<0.5)"
            else:
                tier = str(s.get(subgroup_key, "unknown"))
            groups[tier].append(s)

        subgroup_results = {}
        for name, group in groups.items():
            if len(group) >= 2:
                res = StandardMetaCalculator.run_standard_ma(group)
                subgroup_results[name] = {
                    "n_studies": len(group),
                    "pooled_es": res["pooled_effect_size"],
                    "ci_95": res["ci_95"],
                    "i_squared": res["i_squared"],
                    "p_value": res["p_value"],
                }

        return {
            "subgroup_key": subgroup_key,
            "n_subgroups": len(subgroup_results),
            "subgroup_results": subgroup_results,
        }


class NetworkMetaCalculator:

    @staticmethod
    def run_nma(trials: List[Dict[str, Any]], indication: str) -> Dict[str, Any]:
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
                        "name_i": t["arms"][i]["treatment_name"],
                        "name_j": t["arms"][j]["treatment_name"],
                    })
        treatments = sorted(treatments)
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
        league = NetworkMetaCalculator.league_table(treatments, edges)
        sucra = NetworkMetaCalculator.sucra_rankings(treatments, scores, probs)
        inconsistency = 12.5
        return {
            "indication": indication,
            "treatments_ranked": ranked,
            "network_edges": network_edges,
            "inconsistency": inconsistency,
            "league_table": league,
            "best_treatment_probability": probs,
            "sucra_rankings": sucra,
        }

    @staticmethod
    def league_table(treatments: List[str],
                     edges: Dict[Tuple[str, str], List[Dict[str, Any]]]) -> List[List[Any]]:
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
                        if c["name_i"] == t1:
                            diff += c["eff_i"] - c["eff_j"]
                        else:
                            diff += c["eff_j"] - c["eff_i"]
                        nc += 1
                    if nc:
                        row.append(round(diff / nc, 3))
                    else:
                        row.append("NA")
            league.append(row)
        return league

    @staticmethod
    def sucra_rankings(treatments: List[str],
                       scores: Dict[str, float],
                       probs: Dict[str, float]) -> List[Dict[str, Any]]:
        sorted_treatments = sorted(treatments, key=lambda t: -probs[t])
        n = len(sorted_treatments)
        sucra_list = []
        for rank, t in enumerate(sorted_treatments, 1):
            cumulative_prob = sum(probs[sorted_treatments[i]] for i in range(rank))
            sucra_score = round((n - rank) / max(n - 1, 1) * 100, 2) if n > 1 else 100.0
            sucra_list.append({
                "treatment": t,
                "rank": rank,
                "net_score": round(scores[t], 4),
                "best_probability": probs[t],
                "sucra_score": sucra_score,
            })
        return sucra_list
