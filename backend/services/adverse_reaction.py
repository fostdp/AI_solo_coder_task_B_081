import re
import math
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict, Counter

from ..data.tcm_data import TOXIC_HERBS, HERB_INTERACTION_PAIRS


class AdverseReactionExtractor:

    REACTION_PATTERNS = [
        (r"(恶心|呕吐|吐逆|呕逆)", "胃肠道反应", "轻度"),
        (r"(腹痛|腹胀|泄泻|下利|便溏)", "胃肠道反应", "轻度"),
        (r"(口舌麻木|四肢麻木|麻木)", "神经系统", "中度"),
        (r"(头晕|眩晕|头眩|昏冒)", "神经系统", "轻度"),
        (r"(心悸|心慌|怔忡|心律失常)", "心脏毒性", "中度"),
        (r"(胸闷|胸痛|气短|气促)", "呼吸系统", "中度"),
        (r"(皮疹|瘙痒|红斑|风团|紫癜)", "过敏反应", "轻度"),
        (r"(水肿|浮肿|肿胀)", "水钠潴留", "中度"),
        (r"(黄疸|肝损|肝酶|ALT|AST)", "肝脏毒性", "严重"),
        (r"(血尿|蛋白尿|肌酐|肾损)", "肾脏毒性", "严重"),
        (r"(惊厥|抽搐|癫痫|角弓反张)", "中枢神经毒性", "严重"),
        (r"(昏迷|晕厥|休克|虚脱)", "全身严重反应", "严重"),
        (r"(白细胞|血小板|骨髓|贫血)", "骨髓抑制", "严重"),
        (r"(致畸|致癌|致突变)", "遗传毒性", "严重"),
        (r"(死胎|流产|堕胎|妊娠禁用)", "生殖毒性", "严重"),
    ]

    SEVERITY_WEIGHTS = {"轻度": 1.0, "中度": 2.5, "严重": 5.0}

    @classmethod
    def extract_from_text(cls, text: str) -> List[Dict[str, Any]]:
        found = []
        for pat, rtype, sev in cls.REACTION_PATTERNS:
            m = re.search(pat, text)
            if m:
                found.append({
                    "reaction_type": rtype,
                    "severity": sev,
                    "matched_term": m.group(1),
                    "position": m.start(),
                })
        return found

    @classmethod
    def aggregate_reactions(cls, herbs: List[str]) -> Dict[str, Any]:
        all_reactions = []
        severity_counts = Counter()
        for h in herbs:
            profile = TOXIC_HERBS.get(h)
            if profile:
                for ar in profile.get("adverse_reactions", []):
                    all_reactions.append({
                        "herb": h,
                        **ar,
                    })
                    severity_counts[ar.get("severity", "轻度")] += 1
        by_type = defaultdict(list)
        for r in all_reactions:
            by_type[r["reaction_type"]].append(r)
        return {
            "total_reactions": len(all_reactions),
            "severity_distribution": dict(severity_counts),
            "by_reaction_type": dict(by_type),
            "all_reactions": all_reactions,
        }


class RiskPairDetector:

    RISK_SCORE_MAP = {
        "极高": 1.0,
        "高": 0.75,
        "中": 0.45,
        "低": 0.2,
        "极低": 0.05,
    }

    EVIDENCE_WEIGHT = {"A": 1.0, "B": 0.8, "C": 0.5, "D": 0.3}

    @staticmethod
    def _normalize_pair(a: str, b: str) -> Tuple[str, str]:
        return tuple(sorted([a, b]))

    @classmethod
    def build_pair_index(cls) -> Dict[Tuple[str, str], Dict[str, Any]]:
        idx = {}
        for p in HERB_INTERACTION_PAIRS:
            key = cls._normalize_pair(p["herb_a"], p["herb_b"])
            base_score = cls.RISK_SCORE_MAP.get(p["risk_level"], 0.3)
            ev_w = cls.EVIDENCE_WEIGHT.get(p["evidence_level"], 0.3)
            idx[key] = {
                **p,
                "risk_score": round(base_score * ev_w * 100, 2),
            }
        return idx

    @classmethod
    def detect_for_formula(cls, herbs: List[str]) -> List[Dict[str, Any]]:
        idx = cls.build_pair_index()
        risks = []
        herb_set = set(herbs)
        for i in range(len(herbs)):
            for j in range(i + 1, len(herbs)):
                key = cls._normalize_pair(herbs[i], herbs[j])
                if key in idx:
                    risks.append(idx[key])
        toxic_overlap = [h for h in herbs if h in TOXIC_HERBS]
        for i in range(len(toxic_overlap)):
            for j in range(i + 1, len(toxic_overlap)):
                a, b = toxic_overlap[i], toxic_overlap[j]
                key = cls._normalize_pair(a, b)
                if key in idx:
                    continue
                pa = TOXIC_HERBS[a]
                pb = TOXIC_HERBS[b]
                combined_risk = 0.25
                try:
                    l_ratio_a = min(1.0, 10.0 / (pa.get("ld50_mgkg") or 100.0))
                    l_ratio_b = min(1.0, 10.0 / (pb.get("ld50_mgkg") or 100.0))
                    combined_risk = 0.2 + 0.6 * max(l_ratio_a, l_ratio_b)
                except Exception:
                    pass
                risks.append({
                    "herb_a": a, "herb_b": b,
                    "risk_level": "高" if combined_risk > 0.5 else "中",
                    "risk_score": round(combined_risk * 100, 2),
                    "interaction_type": "毒性叠加风险",
                    "mechanism": f"双方均含毒性成分（{pa['toxic_ingredients'][0]}与{pb['toxic_ingredients'][0]}），合用可能加重肝肾代谢负担",
                    "evidence_level": "D",
                    "references": ["毒性成分交叉分析"],
                })
        risks.sort(key=lambda x: -x["risk_score"])
        return risks


class FormulaRiskAssessor:

    SAFE_GUIDANCE_TEMPLATES = [
        "严格按照《药典》规定剂量使用，不宜超量",
        "建议从小剂量开始，逐步递增，中病即止",
        "不宜久服，症状缓解即停用",
        "用药期间监测肝肾功能及心电图",
        "孕妇、哺乳期妇女禁用",
        "儿童、老年体弱者需在医师指导下减量使用",
        "不得与酒同服，避免加重毒性成分吸收",
        "若出现口舌麻木、恶心等不适，应立即停药就医",
    ]

    @classmethod
    def assess(cls, formula_name: str,
               herbs: List[str],
               herb_dosages: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        risks = RiskPairDetector.detect_for_formula(herbs)
        individual = {}
        dose_warnings = []
        for h in herbs:
            profile = TOXIC_HERBS.get(h)
            if profile:
                individual[h] = {
                    "herb_name": h,
                    "contraindications": profile.get("contraindications", []),
                    "toxic_ingredients": profile.get("toxic_ingredients", []),
                    "adverse_reactions": profile.get("adverse_reactions", []),
                    "ld50_mgkg": profile.get("ld50_mgkg"),
                    "max_safe_dose_g": profile.get("max_safe_dose_g"),
                    "pregnancy_risk": profile.get("pregnancy_risk"),
                }
                if herb_dosages and h in herb_dosages:
                    dose = herb_dosages[h]
                    max_safe = profile.get("max_safe_dose_g")
                    if max_safe and dose > max_safe:
                        dose_warnings.append(
                            f"{h}处方剂量{dose}g超过安全上限{max_safe}g（超{(dose/max_safe-1)*100:.1f}%）")
        if risks:
            max_pair_risk = max(r["risk_score"] for r in risks) / 100.0
        else:
            max_pair_risk = 0.0
        toxic_ratio = sum(1 for h in herbs if h in TOXIC_HERBS) / max(len(herbs), 1)
        over_dose_factor = len(dose_warnings) * 0.15
        overall_score = min(1.0, 0.4 * max_pair_risk + 0.4 * toxic_ratio + 0.2 * over_dose_factor)
        if overall_score >= 0.7:
            level = "极高"
        elif overall_score >= 0.5:
            level = "高"
        elif overall_score >= 0.25:
            level = "中"
        elif overall_score >= 0.1:
            level = "低"
        else:
            level = "安全"
        warnings = list(dose_warnings)
        for r in risks:
            if r["risk_level"] in ("高", "极高"):
                warnings.append(
                    f"存在{r['interaction_type']}风险：{r['herb_a']}与{r['herb_b']}（风险等级{r['risk_level']}）")
        for h, p in individual.items():
            if p.get("pregnancy_risk") in ("禁用", "忌用"):
                warnings.append(f"{h}：孕妇{p['pregnancy_risk']}")
            if "孕妇" in p.get("contraindications", []):
                warnings.append(f"{h}：孕妇禁忌")
        guidance = []
        if overall_score > 0.1:
            guidance.append(cls.SAFE_GUIDANCE_TEMPLATES[0])
            guidance.append(cls.SAFE_GUIDANCE_TEMPLATES[1])
        if individual:
            guidance.append(cls.SAFE_GUIDANCE_TEMPLATES[2])
            guidance.append(cls.SAFE_GUIDANCE_TEMPLATES[3])
        if any(p.get("pregnancy_risk") for p in individual.values()):
            guidance.append(cls.SAFE_GUIDANCE_TEMPLATES[4])
        if len(herbs) >= 10:
            guidance.append(cls.SAFE_GUIDANCE_TEMPLATES[5])
        if overall_score >= 0.5:
            guidance.append(cls.SAFE_GUIDANCE_TEMPLATES[7])
        return {
            "formula_name": formula_name,
            "overall_risk_level": level,
            "overall_risk_score": round(overall_score * 100, 2),
            "risk_pairs": risks,
            "individual_risks": individual,
            "warnings": warnings,
            "safe_use_guidance": guidance,
        }
