import re
import math
import random
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter

from data.tcm_data import (
    EFFICACY_DESCRIPTIONS,
    MEDICAL_CASE_TEMPLATES,
    SYNDROME_NAMES,
)


class SentimentUncertaintyEstimator:

    @staticmethod
    def keyword_entropy(matched_keywords: List[Tuple[str, float, str]]) -> float:
        if not matched_keywords:
            return 1.0
        pos_sum = sum(abs(w) for _, w, t in matched_keywords if t == "pos")
        neg_sum = sum(abs(w) for _, w, t in matched_keywords if t == "neg")
        total = pos_sum + neg_sum
        if total == 0:
            return 1.0
        p_pos = pos_sum / total
        p_neg = neg_sum / total
        entropy = 0.0
        if p_pos > 0:
            entropy -= p_pos * math.log2(p_pos)
        if p_neg > 0:
            entropy -= p_neg * math.log2(p_neg)
        return entropy

    @staticmethod
    def confidence_from_matches(n_matches: int, text_length: int) -> float:
        if n_matches == 0:
            return 0.0
        density = min(1.0, n_matches / max(text_length / 3, 1))
        match_conf = 1.0 - math.exp(-n_matches / 2.0)
        return 0.6 * match_conf + 0.4 * density

    @staticmethod
    def overall_uncertainty(matched_keywords: List[Tuple[str, float, str]],
                               text_length: int) -> Dict[str, Any]:
        n = len(matched_keywords)
        if n == 0:
            return {
                "entropy": 1.0,
                "sparsity_penalty": 1.0,
                "weight_variance": 0.0,
                "ambiguity_level": "高",
                "confidence": 0.0,
                "needs_review": True,
            }

        entropy = SentimentUncertaintyEstimator.keyword_entropy(matched_keywords)
        density_conf = SentimentUncertaintyEstimator.confidence_from_matches(n, text_length)

        weight_variance = 0.0
        if n > 1:
            weights = [abs(w) for _, w, _ in matched_keywords]
            mean_w = sum(weights) / n
            variance = sum((w - mean_w) ** 2 for w in weights) / n
            weight_variance = min(1.0, math.sqrt(variance))

        sparsity_penalty = 1.0 - density_conf
        ambiguity = 0.4 * entropy + 0.35 * sparsity_penalty + 0.25 * weight_variance

        overall_conf = max(0.0, 1.0 - ambiguity)

        level = "高"
        if overall_conf > 0.7:
            level = "低"
        elif overall_conf > 0.45:
            level = "中"

        return {
            "entropy": round(entropy, 4),
            "sparsity_penalty": round(sparsity_penalty, 4),
            "weight_variance": round(weight_variance, 4),
            "ambiguity_level": level,
            "confidence": round(overall_conf, 4),
            "needs_review": overall_conf < 0.5 or n <= 1,
        }


class TCMSentimentAnalyzer:

    POSITIVE_KEYWORDS = {
        "愈": 0.9, "瘥": 0.85, "安": 0.8, "除": 0.85, "已": 0.75,
        "立": 0.3, "即": 0.2, "神": 0.4, "良": 0.35, "桴鼓": 0.8,
        "减": 0.5, "轻": 0.45, "平": 0.55, "霍然": 0.85, "应手": 0.8,
        "见效": 0.55, "好转": 0.45, "起色": 0.4, "收功": 0.65,
        "投之即效": 0.85, "效如": 0.9, "立起": 0.85, "不爽": 0.3,
        "爽": 0.25, "颇效": 0.7, "甚效": 0.8, "大效": 0.85,
        "痊愈": 0.92, "康复": 0.85, "根治": 0.88, "全消": 0.90,
        "悉除": 0.88, "顿愈": 0.92, "立效": 0.85, "奇效": 0.90,
        "速效": 0.80, "显效": 0.75, "佳效": 0.72, "奏效": 0.70,
        "消退": 0.60, "消失": 0.70, "缓解": 0.55, "安宁": 0.60,
        "通利": 0.55, "和调": 0.50, "复常": 0.75, "安和": 0.65,
        "诸恙悉平": 0.85, "病去八九": 0.75, "渐入坦途": 0.65,
        "药到病除": 0.90, "覆杯即安": 0.92, "一剂知": 0.80,
        "有效": 0.55, "极效": 0.85, "渐平": 0.35,
    }

    NEGATIVE_KEYWORDS = {
        "不效": -0.8, "无效": -0.9, "未见": -0.7, "依旧": -0.6,
        "反增": -0.8, "不对证": -0.85, "无功": -0.75, "停用": -0.5,
        "不佳": -0.5, "时好时坏": -0.3, "缓慢": -0.2, "平平": -0.3,
        "反剧": -0.9, "加剧": -0.85, "恶化": -0.95,
        "不验": -0.80, "罔效": -0.85, "少效": -0.50, "微效": -0.30,
        "反复": -0.40, "缠绵": -0.45, "迁延": -0.40, "难愈": -0.60,
        "加重": -0.80, "不适": -0.35, "副作用": -0.50, "过敏": -0.55,
        "未减": -0.65, "无寸效": -0.90, "病进": -0.85, "邪陷": -0.80,
    }

    NEGATION_PREFIXES = ["不", "未", "无", "非", "勿", "莫", "难"]

    INTENSIFIERS = {
        "大": 1.3, "甚": 1.3, "极": 1.4, "至": 1.2, "殊": 1.2,
        "颇": 1.15, "极奇": 1.5, "万": 1.5, "十分": 1.3,
    }

    TIME_PATTERNS = [
        (r"一剂而", 1), (r"一剂知", 1), (r"覆杯", 0.5), (r"立", 0.1),
        (r"一日", 1), (r"三日", 3), (r"五剂", 5), (r"五日", 5),
        (r"七日", 7), (r"旬日", 10), (r"半月", 15), (r"两周", 14),
        (r"月余", 30), (r"经年", 365), (r"二剂", 2), (r"三剂", 3),
        (r"四剂", 4), (r"六剂", 6), (r"十剂", 10), (r"廿剂", 20),
        (r"二日", 2), (r"四日", 4), (r"六日", 6), (r"八日", 8),
        (r"十日", 10), (r"数日", 5), (r"数周", 21), (r"数月", 90),
        (r"即[日刻时]", 0.5), (r"旋即", 0.2), (r"须臾", 0.1),
        (r"俄顷", 0.15), (r"少顷", 0.2), (r"食顷", 0.5),
    ]

    @classmethod
    def compute_sentiment(cls, text: str) -> float:
        score = 0.0
        matched = 0
        matched_positions = set()

        all_keywords = []
        for kw, w in cls.POSITIVE_KEYWORDS.items():
            all_keywords.append((kw, w, "pos"))
        for kw, w in cls.NEGATIVE_KEYWORDS.items():
            all_keywords.append((kw, w, "neg"))

        all_keywords.sort(key=lambda x: -len(x[0]))

        for kw, w, ktype in all_keywords:
            if kw not in text:
                continue
            idx = text.find(kw)
            positions = set(range(idx, idx + len(kw)))
            if positions & matched_positions:
                continue
            matched_positions |= positions

            if ktype == "pos":
                modifier = 1.0
                for intensifier, mult in cls.INTENSIFIERS.items():
                    if intensifier + kw in text:
                        modifier = mult
                        break
                for neg in cls.NEGATION_PREFIXES:
                    idx_p = text.find(kw)
                    if idx_p > 0 and text[idx_p - 1] == neg:
                        modifier = -0.8
                        break
                score += w * modifier
            else:
                score += w
            matched += 1

        if matched == 0:
            return 0.0
        return max(-1.0, min(1.0, score / max(matched, 1) * 1.2))

    @classmethod
    def analyze_with_uncertainty(cls, text: str) -> Dict[str, Any]:
        matched_keywords: List[Tuple[str, float, str]] = []
        matched_positions = set()
        score = 0.0
        matched_count = 0

        all_keywords = []
        for kw, w in cls.POSITIVE_KEYWORDS.items():
            all_keywords.append((kw, w, "pos"))
        for kw, w in cls.NEGATIVE_KEYWORDS.items():
            all_keywords.append((kw, w, "neg"))
        all_keywords.sort(key=lambda x: -len(x[0]))

        for kw, w, ktype in all_keywords:
            if kw not in text:
                continue
            idx = text.find(kw)
            positions = set(range(idx, idx + len(kw)))
            if positions & matched_positions:
                continue
            matched_positions |= positions

            effective_w = w
            if ktype == "pos":
                modifier = 1.0
                for intensifier, mult in cls.INTENSIFIERS.items():
                    if intensifier + kw in text:
                        modifier = mult
                        break
                for neg in cls.NEGATION_PREFIXES:
                    idx_p = text.find(kw)
                    if idx_p > 0 and text[idx_p - 1] == neg:
                        modifier = -0.8
                        break
                effective_w = w * modifier
                score += effective_w
            else:
                score += w
            matched_count += 1
            matched_keywords.append((kw, effective_w, ktype))

        sentiment = 0.0
        if matched_count > 0:
            sentiment = max(-1.0, min(1.0, score / max(matched_count, 1) * 1.2))

        uncertainty = SentimentUncertaintyEstimator.overall_uncertainty(
            matched_keywords, len(text)
        )

        return {
            "sentiment_score": round(sentiment, 4),
            "matched_keywords": [
                {"keyword": kw, "weight": round(w, 4), "type": t}
                for kw, w, t in matched_keywords
            ],
            "match_count": matched_count,
            "entropy": uncertainty["entropy"],
            "sparsity_penalty": uncertainty["sparsity_penalty"],
            "weight_variance": uncertainty["weight_variance"],
            "ambiguity_level": uncertainty["ambiguity_level"],
            "match_confidence": round(
                SentimentUncertaintyEstimator.confidence_from_matches(
                    matched_count, len(text)
                ), 4
            ),
            "overall_confidence": uncertainty["confidence"],
            "needs_human_review": uncertainty["needs_review"],
        }

    @classmethod
    def extract_days(cls, text: str) -> Optional[int]:
        for pat, d in cls.TIME_PATTERNS:
            if re.search(pat, text):
                return d
        return None


class OrdinalRegressionScorer:

    GRADE_THRESHOLDS = [-0.3, 0.2, 0.55, 0.80]
    GRADE_LABELS = ["无效", "一般", "良好", "优秀", "神效"]

    @classmethod
    def predict_grade(cls, sentiment: float, days: Optional[int]) -> Tuple[int, float]:
        base_score = sentiment
        if days is not None:
            time_weight = max(0.0, 1.0 - math.log1p(days) / 4.5)
            base_score = sentiment * 0.65 + (0.35 if sentiment > 0 else -0.35) * time_weight
        else:
            base_score = sentiment * 0.75
        grade = 0
        for i, t in enumerate(cls.GRADE_THRESHOLDS):
            if base_score > t:
                grade = i + 1
        normalized = max(0.0, min(100.0, (base_score + 1.0) * 50.0))
        return grade, round(normalized, 2)

    @classmethod
    def predict_with_uncertainty(cls, sentiment: float, days: Optional[int],
                                 sentiment_confidence: float = 1.0) -> Dict[str, Any]:
        grade, score = cls.predict_grade(sentiment, days)
        base_score = (score / 100.0) * 2.0 - 1.0

        grade_probs = []
        for g in range(5):
            if g == 0:
                lower = -1.0
                upper = cls.GRADE_THRESHOLDS[0]
            elif g < 4:
                lower = cls.GRADE_THRESHOLDS[g - 1]
                upper = cls.GRADE_THRESHOLDS[g]
            else:
                lower = cls.GRADE_THRESHOLDS[3]
                upper = 1.0
            mid = (lower + upper) / 2
            width = upper - lower
            dist = abs(base_score - mid)
            prob = max(0.01, 1.0 - dist / width) * sentiment_confidence
            grade_probs.append(prob)

        total = sum(grade_probs)
        if total > 0:
            grade_probs = [p / total for p in grade_probs]

        top2 = sorted(range(5), key=lambda g: -grade_probs[g])[:2]
        margin = grade_probs[top2[0]] - grade_probs[top2[1]]

        uncertainty_score = 0.4 * (1.0 - margin) + 0.6 * (1.0 - sentiment_confidence)

        uncertainty = "高"
        if uncertainty_score < 0.25:
            uncertainty = "低"
        elif uncertainty_score < 0.45:
            uncertainty = "中"

        return {
            "grade": grade,
            "grade_label": cls.GRADE_LABELS[grade],
            "score": score,
            "base_score": round(base_score, 4),
            "grade_probabilities": [
                {"grade": i, "label": cls.GRADE_LABELS[i], "probability": round(p, 4)}
                for i, p in enumerate(grade_probs)
            ],
            "top2_grades": [cls.GRADE_LABELS[g] for g in top2],
            "confidence_margin": round(margin, 4),
            "uncertainty_level": uncertainty,
            "needs_human_review": uncertainty == "高" or sentiment_confidence < 0.5,
        }


class HumanAnnotationManager:

    def __init__(self):
        self.annotations: Dict[str, Dict[str, Any]] = {}
        self.review_queue: List[Dict[str, Any]] = []

    def submit_for_review(self, case_id: str, text: str,
                          auto_grade: int, auto_score: float,
                          uncertainty: str, reason: str = "") -> Dict[str, Any]:
        item = {
            "case_id": case_id,
            "text": text,
            "auto_grade": auto_grade,
            "auto_score": auto_score,
            "uncertainty": uncertainty,
            "reason": reason,
            "status": "pending",
            "submitted_at": __import__("time").time(),
        }
        self.review_queue.append(item)
        return item

    def annotate(self, case_id: str, human_grade: int, human_score: float,
                 annotator: str = "", notes: str = "") -> Optional[Dict[str, Any]]:
        if case_id not in self.annotations:
            self.annotations[case_id] = {"history": []}
        record = {
            "case_id": case_id,
            "human_grade": human_grade,
            "human_score": human_score,
            "annotator": annotator,
            "notes": notes,
            "timestamp": __import__("time").time(),
        }
        self.annotations[case_id]["history"].append(record)
        self.annotations[case_id]["latest"] = record
        for item in self.review_queue:
            if item["case_id"] == case_id:
                item["status"] = "reviewed"
        return record

    def get_pending_count(self) -> int:
        return sum(1 for item in self.review_queue if item["status"] == "pending")

    def get_annotation_stats(self) -> Dict[str, Any]:
        if not self.annotations:
            return {"total": 0, "pending": self.get_pending_count()}
        grades = [a["latest"]["human_grade"] for a in self.annotations.values()
                  if a.get("latest")]
        return {
            "total_annotated": len(self.annotations),
            "pending_review": self.get_pending_count(),
            "grade_distribution": dict(Counter(grades)),
            "avg_human_score": round(
                sum(a["latest"]["human_score"] for a in self.annotations.values()
                    if a.get("latest")) / len(self.annotations), 2
            ) if self.annotations else 0.0,
        }


class MedicalCaseGenerator:

    GENDERS = ["男", "女"]
    OUTCOME_PROBS = {
        "汉代":  {"excellent": 0.30, "good": 0.45, "moderate": 0.18, "poor": 0.07},
        "唐代":  {"excellent": 0.25, "good": 0.45, "moderate": 0.20, "poor": 0.10},
        "宋代":  {"excellent": 0.22, "good": 0.45, "moderate": 0.23, "poor": 0.10},
        "金元":  {"excellent": 0.28, "good": 0.43, "moderate": 0.19, "poor": 0.10},
        "明代":  {"excellent": 0.24, "good": 0.45, "moderate": 0.22, "poor": 0.09},
        "清代":  {"excellent": 0.23, "good": 0.45, "moderate": 0.22, "poor": 0.10},
        "default": {"excellent": 0.25, "good": 0.45, "moderate": 0.20, "poor": 0.10},
    }

    DYNASTIES = list(OUTCOME_PROBS.keys())

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def generate_case(self, formula_name: str, dynasty: str,
                      symptoms: List[str]) -> Dict[str, Any]:
        probs = self.OUTCOME_PROBS.get(dynasty, self.OUTCOME_PROBS["default"])
        r = self.rng.random()
        cum = 0.0
        grade_key = "good"
        for k, p in probs.items():
            cum += p
            if r <= cum:
                grade_key = k
                break
        desc_list = EFFICACY_DESCRIPTIONS[grade_key]
        raw_desc = self.rng.choice(desc_list)
        gender = self.rng.choice(self.GENDERS)
        age = self.rng.randint(12, 78)
        syndrome = self.rng.choice(SYNDROME_NAMES)
        symptom_str = self.rng.choice(symptoms) if symptoms else "不适"
        template = self.rng.choice(MEDICAL_CASE_TEMPLATES)
        case_text = template.format(
            gender=gender, age=age, symptom=symptom_str,
            syndrome=syndrome, formula=formula_name, outcome=raw_desc,
            dynasty=dynasty or "古代",
        )
        sentiment = TCMSentimentAnalyzer.compute_sentiment(raw_desc)
        days = TCMSentimentAnalyzer.extract_days(raw_desc)
        if days is None:
            if grade_key == "excellent":
                days = self.rng.randint(1, 3)
            elif grade_key == "good":
                days = self.rng.randint(3, 10)
            elif grade_key == "moderate":
                days = self.rng.randint(10, 30)
            else:
                days = self.rng.randint(20, 60)
        grade, score = OrdinalRegressionScorer.predict_grade(sentiment, days)
        dosage_regimens = ["日一剂，水煎服，早晚分服",
                           "共为细末，每服6g，日两次",
                           "蜜丸如梧桐子大，每服30丸",
                           "水煎取汁300ml，温服"]
        return {
            "formula_name": formula_name,
            "medical_case": case_text,
            "raw_description": raw_desc,
            "sentiment_score": round(sentiment, 4),
            "efficacy_grade": grade,
            "days_to_effect": days,
            "dosage_regimen": self.rng.choice(dosage_regimens),
            "patient_age": age,
            "patient_gender": gender,
        }

    def generate_cases_for_formula(self, formula_name: str, dynasty: str,
                                   symptoms: List[str],
                                   n: int = 12) -> List[Dict[str, Any]]:
        return [self.generate_case(formula_name, dynasty, symptoms)
                for _ in range(n)]


class EfficacyAggregator:

    @staticmethod
    def aggregate(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not cases:
            return {
                "formula_name": "",
                "avg_efficacy_score": 0.0,
                "efficacy_grade_distribution": {},
                "total_cases": 0,
                "avg_days_to_effect": 0.0,
                "confidence_interval": [0.0, 0.0],
            }
        scores = [c["efficacy_grade"] * 25 + (c["sentiment_score"] + 1) * 12.5
                  for c in cases]
        grades = Counter(c["efficacy_grade"] for c in cases)
        days_list = [c["days_to_effect"] for c in cases if c.get("days_to_effect")]
        n = len(scores)
        mean = sum(scores) / n
        var = sum((s - mean) ** 2 for s in scores) / max(n - 1, 1)
        se = math.sqrt(var / n) if n > 1 else 0.0
        z = 1.96
        ci = [max(0.0, mean - z * se), min(100.0, mean + z * se)]
        return {
            "formula_name": cases[0]["formula_name"],
            "avg_efficacy_score": round(mean, 2),
            "efficacy_grade_distribution": dict(grades),
            "total_cases": n,
            "avg_days_to_effect": round(sum(days_list) / len(days_list), 2)
                if days_list else 0.0,
            "case_records": cases,
            "confidence_interval": [round(ci[0], 2), round(ci[1], 2)],
        }
