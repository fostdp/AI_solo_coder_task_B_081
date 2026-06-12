import re
import math
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict, Counter

from data.tcm_data import TOXIC_HERBS, HERB_INTERACTION_PAIRS


class ExpertKnowledgeEngine:

    TOXIC_FAMILIES = {
        "乌头类": {
            "members": ["附子", "乌头", "川乌", "草乌", "雪上一枝蒿"],
            "shared_ingredients": ["乌头碱", "次乌头碱", "中乌头碱"],
            "toxicity_type": "心脏毒性+神经毒性",
            "base_risk": "高",
        },
        "含汞类": {
            "members": ["朱砂", "水银", "轻粉", "红粉"],
            "shared_ingredients": ["汞化合物"],
            "toxicity_type": "肝肾毒性+神经毒性",
            "base_risk": "高",
        },
        "含砷类": {
            "members": ["雄黄", "砒石", "砒霜"],
            "shared_ingredients": ["砷化合物"],
            "toxicity_type": "肝肾毒性+遗传毒性",
            "base_risk": "高",
        },
        "攻下逐瘀类": {
            "members": ["大黄", "芒硝", "甘遂", "大戟", "芫花", "巴豆", "牵牛子"],
            "shared_ingredients": ["蒽醌类/刺激性成分"],
            "toxicity_type": "胃肠道刺激+生殖毒性",
            "base_risk": "中",
        },
        "强心苷类": {
            "members": ["夹竹桃", "万年青", "罗布麻"],
            "shared_ingredients": ["强心苷"],
            "toxicity_type": "心脏毒性",
            "base_risk": "高",
        },
        "动物毒性类": {
            "members": ["斑蝥", "蟾酥", "红娘子", "青娘子"],
            "shared_issues": ["剧毒成分", "黏膜刺激"],
            "toxicity_type": "多器官毒性",
            "base_risk": "高",
        },
    }

    PREGNANCY_CONTRAINDICATED_CATEGORIES = [
        "攻下逐瘀类", "含砷类", "含汞类", "乌头类", "动物毒性类", "强心苷类",
    ]

    INTERACTION_RULES = [
        {
            "rule_id": "R001",
            "name": "同类毒性叠加",
            "description": "同一毒性家族的两味药合用，毒性协同增强",
            "condition": "same_family",
            "risk_boost": 0.25,
            "evidence_level": "B",
            "mechanism_template": "二者同属{family}，均含{ingredients}，合用可能产生毒性协同作用",
        },
        {
            "rule_id": "R002",
            "name": "十八反扩展类推",
            "description": "与已知禁忌药同科属的药物，可能存在类似禁忌",
            "condition": "analogous_to_known_pair",
            "risk_boost": 0.15,
            "evidence_level": "C",
            "mechanism_template": "基于{known_pair}的禁忌记载类推，{herb_a}与{herb_b}可能存在类似配伍禁忌",
        },
        {
            "rule_id": "R003",
            "name": "共同代谢靶点叠加",
            "description": "均经肝肾代谢的毒性药物合用，加重代谢负担",
            "condition": "both_liver_kidney_toxic",
            "risk_boost": 0.18,
            "evidence_level": "C",
            "mechanism_template": "二者均具有肝肾毒性，合用可能加重肝肾代谢负担，增加器官损伤风险",
        },
        {
            "rule_id": "R004",
            "name": "妊娠用药叠加风险",
            "description": "多味妊娠禁忌药合用，风险显著升高",
            "condition": "pregnancy_multi_contraindicated",
            "risk_boost": 0.2,
            "evidence_level": "B",
            "mechanism_template": "方中含多味妊娠禁忌药，致畸/堕胎风险显著升高，孕妇绝对禁用",
        },
    ]

    def __init__(self):
        self.herb_family_map = self._build_family_index()

    def _build_family_index(self) -> Dict[str, str]:
        idx = {}
        for family_name, info in self.TOXIC_FAMILIES.items():
            for herb in info["members"]:
                idx[herb] = family_name
        return idx

    def get_herb_family(self, herb: str) -> Optional[str]:
        return self.herb_family_map.get(herb)

    def infer_interactions(self, herbs: List[str]) -> List[Dict[str, Any]]:
        inferred = []
        known_idx = set()
        for p in HERB_INTERACTION_PAIRS:
            key = tuple(sorted([p["herb_a"], p["herb_b"]]))
            known_idx.add(key)

        for i in range(len(herbs)):
            for j in range(i + 1, len(herbs)):
                a, b = herbs[i], herbs[j]
                key = tuple(sorted([a, b]))
                if key in known_idx:
                    continue
                inferences = self._infer_pair(a, b)
                if inferences:
                    inferred.extend(inferences)
        return inferred

    def _infer_pair(self, a: str, b: str) -> List[Dict[str, Any]]:
        results = []
        fam_a = self.get_herb_family(a)
        fam_b = self.get_herb_family(b)

        if fam_a and fam_a == fam_b:
            fam_info = self.TOXIC_FAMILIES[fam_a]
            base_risk_score = 0.3 if fam_info["base_risk"] == "高" else 0.18
            score = min(1.0, base_risk_score + 0.25)
            ingredients = "、".join(fam_info.get("shared_ingredients", ["毒性成分"]))
            results.append({
                "herb_a": a,
                "herb_b": b,
                "risk_level": "高" if score > 0.5 else "中",
                "risk_score": round(score * 100, 2),
                "interaction_type": f"专家推理-{fam_info['toxicity_type']}",
                "mechanism": f"二者同属{fam_a}，均含{ingredients}，合用可能产生毒性协同作用",
                "evidence_level": "C",
                "inferred": True,
                "inference_rule": "同类毒性叠加",
                "confidence": 0.65,
                "references": [f"基于{fam_a}毒性家族推理"],
            })

        for pair in HERB_INTERACTION_PAIRS:
            known_a_fam = self.get_herb_family(pair["herb_a"])
            known_b_fam = self.get_herb_family(pair["herb_b"])
            a_fam = self.get_herb_family(a)
            b_fam = self.get_herb_family(b)
            if known_a_fam and known_b_fam and a_fam and b_fam:
                if a_fam == known_a_fam and b_fam == known_b_fam:
                    analog_score = 0.2
                    results.append({
                        "herb_a": a,
                        "herb_b": b,
                        "risk_level": "低",
                        "risk_score": round(analog_score * 100, 2),
                        "interaction_type": "专家推理-类推禁忌",
                        "mechanism": (
                            f"基于{pair['herb_a']}与{pair['herb_b']}的禁忌记载类推，"
                            f"{a}与{b}同科同属，可能存在类似配伍禁忌，需谨慎使用"
                        ),
                        "evidence_level": "D",
                        "inferred": True,
                        "inference_rule": "十八反扩展类推",
                        "confidence": 0.35,
                        "references": [f"参考禁忌：{pair['herb_a']}+{pair['herb_b']}"],
                    })
                    break

        if a in TOXIC_HERBS and b in TOXIC_HERBS:
            a_rx = TOXIC_HERBS[a].get("adverse_reactions", [])
            b_rx = TOXIC_HERBS[b].get("adverse_reactions", [])
            a_types = set(r.get("type", r.get("reaction_type", "")) for r in a_rx)
            b_types = set(r.get("type", r.get("reaction_type", "")) for r in b_rx)
            overlap = a_types & b_types
            if "肝脏毒性" in overlap or "肾脏毒性" in overlap or "肝肾" in str(overlap):
                results.append({
                    "herb_a": a,
                    "herb_b": b,
                    "risk_level": "中",
                    "risk_score": 35.0,
                    "interaction_type": "专家推理-共同代谢靶点",
                    "mechanism": "二者均具有肝肾毒性，合用可能加重肝肾代谢负担，增加器官损伤风险",
                    "evidence_level": "C",
                    "inferred": True,
                    "inference_rule": "共同代谢靶点叠加",
                    "confidence": 0.55,
                    "references": ["毒代动力学交叉推测"],
                })

        return results

    def expand_toxic_profile(self, herb: str) -> Dict[str, Any]:
        base = TOXIC_HERBS.get(herb, {})
        family = self.get_herb_family(herb)
        family_info = self.TOXIC_FAMILIES.get(family, {}) if family else {}

        expanded_reactions = list(base.get("adverse_reactions", []))
        known_types = set(
            r.get("type", r.get("reaction_type", "")) for r in expanded_reactions
        )

        if family_info.get("toxicity_type"):
            tox_type = family_info["toxicity_type"]
            if "心脏" in tox_type and "心脏毒性" not in known_types:
                expanded_reactions.append({
                    "type": "心脏毒性",
                    "severity": "严重",
                    "source": "专家推理-家族推断",
                    "inferred": True,
                })
            if "神经" in tox_type and "神经系统" not in known_types:
                expanded_reactions.append({
                    "type": "神经系统",
                    "severity": "中度",
                    "source": "专家推理-家族推断",
                    "inferred": True,
                })
            if "肝肾" in tox_type:
                if "肝脏毒性" not in known_types:
                    expanded_reactions.append({
                        "type": "肝脏毒性",
                        "severity": "严重",
                        "source": "专家推理-家族推断",
                        "inferred": True,
                    })
                if "肾脏毒性" not in known_types:
                    expanded_reactions.append({
                        "type": "肾脏毒性",
                        "severity": "严重",
                        "source": "专家推理-家族推断",
                        "inferred": True,
                    })
            if "胃肠道" in tox_type and "胃肠道反应" not in known_types:
                expanded_reactions.append({
                    "type": "胃肠道反应",
                    "severity": "轻度",
                    "source": "专家推理-家族推断",
                    "inferred": True,
                })
            if "生殖" in tox_type and "生殖毒性" not in known_types:
                expanded_reactions.append({
                    "type": "生殖毒性",
                    "severity": "严重",
                    "source": "专家推理-家族推断",
                    "inferred": True,
                })
            if "遗传" in tox_type and "遗传毒性" not in known_types:
                expanded_reactions.append({
                    "type": "遗传毒性",
                    "severity": "严重",
                    "source": "专家推理-家族推断",
                    "inferred": True,
                })

        pregnancy_risk = base.get("pregnancy_risk", "")
        if not pregnancy_risk and family and family in self.PREGNANCY_CONTRAINDICATED_CATEGORIES:
            pregnancy_risk = "禁用"

        return {
            "herb_name": herb,
            "base_known": bool(base),
            "family": family,
            "expanded_adverse_reactions": expanded_reactions,
            "pregnancy_risk": pregnancy_risk or "未知",
            "inferred_count": sum(1 for r in expanded_reactions if r.get("inferred")),
            "confidence": 0.7 if base else 0.4,
        }

    def assess_pregnancy_risk(self, herbs: List[str]) -> Dict[str, Any]:
        ci_herbs = []
        caution_herbs = []
        family_risks = []

        for h in herbs:
            profile = TOXIC_HERBS.get(h)
            if profile:
                pr = profile.get("pregnancy_risk", "")
                if pr in ("禁用", "忌用"):
                    ci_herbs.append(h)
                elif pr == "慎用":
                    caution_herbs.append(h)
            fam = self.get_herb_family(h)
            if fam and fam in self.PREGNANCY_CONTRAINDICATED_CATEGORIES:
                if h not in ci_herbs and h not in caution_herbs:
                    family_risks.append(h)

        overall = "安全"
        if ci_herbs:
            overall = "禁用"
        elif family_risks:
            overall = "忌用（推理）"
        elif caution_herbs:
            overall = "慎用"

        return {
            "overall_risk": overall,
            "contraindicated_herbs": ci_herbs,
            "caution_herbs": caution_herbs,
            "inferred_risk_herbs": family_risks,
            "inferred_count": len(family_risks),
            "warning": (
                "孕妇绝对禁用，可能导致流产、致畸或严重妊娠并发症"
                if overall in ("禁用", "忌用（推理）")
                else "孕妇需在医师指导下谨慎使用"
                if overall == "慎用"
                else "无明确妊娠禁忌记载"
            ),
        }


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
                    reaction_entry = {
                        "herb": h,
                        "reaction_type": ar.get("type", ar.get("reaction_type", "未知")),
                        "severity": ar.get("severity", "轻度"),
                        **ar,
                    }
                    all_reactions.append(reaction_entry)
                    severity_counts[reaction_entry["severity"]] += 1
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
    def detect_for_formula(cls, herbs: List[str],
                           include_expert_inference: bool = True) -> List[Dict[str, Any]]:
        idx = cls.build_pair_index()
        risks = []
        herb_set = set(herbs)
        for i in range(len(herbs)):
            for j in range(i + 1, len(herbs)):
                key = cls._normalize_pair(herbs[i], herbs[j])
                if key in idx:
                    risks.append({**idx[key], "inferred": False})
        toxic_overlap = [h for h in herbs if h in TOXIC_HERBS]
        known_keys = set()
        for r in risks:
            known_keys.add(cls._normalize_pair(r["herb_a"], r["herb_b"]))
        for i in range(len(toxic_overlap)):
            for j in range(i + 1, len(toxic_overlap)):
                a, b = toxic_overlap[i], toxic_overlap[j]
                key = cls._normalize_pair(a, b)
                if key in known_keys:
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
                    "inferred": False,
                    "references": ["毒性成分交叉分析"],
                })
                known_keys.add(key)

        if include_expert_inference:
            expert = ExpertKnowledgeEngine()
            inferred = expert.infer_interactions(herbs)
            for inf in inferred:
                key = cls._normalize_pair(inf["herb_a"], inf["herb_b"])
                if key not in known_keys:
                    risks.append(inf)
                    known_keys.add(key)

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
               herb_dosages: Optional[Dict[str, float]] = None,
               include_expert_inference: bool = True) -> Dict[str, Any]:
        risks = RiskPairDetector.detect_for_formula(
            herbs, include_expert_inference=include_expert_inference
        )
        expert = ExpertKnowledgeEngine() if include_expert_inference else None

        individual = {}
        expanded_profiles = {}
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
            if expert:
                exp = expert.expand_toxic_profile(h)
                if exp["inferred_count"] > 0 or exp.get("family"):
                    expanded_profiles[h] = exp
            if profile and herb_dosages and h in herb_dosages:
                dose = herb_dosages[h]
                max_safe = profile.get("max_safe_dose_g")
                if max_safe and dose > max_safe:
                    dose_warnings.append(
                        f"{h}处方剂量{dose}g超过安全上限{max_safe}g（超{(dose/max_safe-1)*100:.1f}%）")

        inferred_risks = [r for r in risks if r.get("inferred")]
        known_risks = [r for r in risks if not r.get("inferred")]
        inferred_count = len(inferred_risks)

        if known_risks:
            max_pair_risk = max(r["risk_score"] for r in known_risks) / 100.0
        else:
            max_pair_risk = 0.0
        inferred_bonus = min(0.15, inferred_count * 0.08)
        toxic_ratio = sum(1 for h in herbs if h in TOXIC_HERBS) / max(len(herbs), 1)
        toxic_count = sum(1 for h in herbs if h in TOXIC_HERBS)
        toxic_bonus = min(0.3, toxic_count * 0.12)
        over_dose_factor = len(dose_warnings) * 0.15
        overall_score = min(
            1.0,
            0.3 * max_pair_risk + 0.3 * toxic_ratio + 0.12 * toxic_bonus
            + 0.13 * inferred_bonus + 0.15 * over_dose_factor
        )
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

        pregnancy_risk = None
        if expert:
            pregnancy_risk = expert.assess_pregnancy_risk(herbs)

        warnings = list(dose_warnings)
        for r in known_risks:
            if r["risk_level"] in ("高", "极高"):
                warnings.append(
                    f"存在{r['interaction_type']}风险：{r['herb_a']}与{r['herb_b']}（风险等级{r['risk_level']}）")
        if inferred_count > 0:
            warnings.append(
                f"专家推理发现 {inferred_count} 项潜在风险，需进一步验证")
        for h, p in individual.items():
            if p.get("pregnancy_risk") in ("禁用", "忌用"):
                warnings.append(f"{h}：孕妇{p['pregnancy_risk']}")
            if "孕妇" in p.get("contraindications", []):
                warnings.append(f"{h}：孕妇禁忌")
        if pregnancy_risk and pregnancy_risk["inferred_count"] > 0:
            warnings.append(
                f"基于家族推理，{', '.join(pregnancy_risk['inferred_risk_herbs'])} 可能存在妊娠风险")

        guidance = []
        if overall_score > 0.1:
            guidance.append(cls.SAFE_GUIDANCE_TEMPLATES[0])
            guidance.append(cls.SAFE_GUIDANCE_TEMPLATES[1])
        if individual:
            guidance.append(cls.SAFE_GUIDANCE_TEMPLATES[2])
            guidance.append(cls.SAFE_GUIDANCE_TEMPLATES[3])
        if any(p.get("pregnancy_risk") for p in individual.values()) \
                or (pregnancy_risk and pregnancy_risk["overall_risk"] != "安全"):
            guidance.append(cls.SAFE_GUIDANCE_TEMPLATES[4])
        if len(herbs) >= 10:
            guidance.append(cls.SAFE_GUIDANCE_TEMPLATES[5])
        if overall_score >= 0.5:
            guidance.append(cls.SAFE_GUIDANCE_TEMPLATES[7])
        if inferred_count > 0:
            guidance.append("专家推理风险需结合临床实际，必要时咨询中医师确认")

        return {
            "formula_name": formula_name,
            "overall_risk_level": level,
            "overall_risk_score": round(overall_score * 100, 2),
            "risk_pairs": risks,
            "known_risk_pairs": known_risks,
            "inferred_risk_pairs": inferred_risks,
            "inferred_count": inferred_count,
            "individual_risks": individual,
            "expanded_toxic_profiles": expanded_profiles,
            "pregnancy_risk": pregnancy_risk,
            "warnings": warnings,
            "safe_use_guidance": guidance,
            "has_expert_inference": include_expert_inference,
        }
