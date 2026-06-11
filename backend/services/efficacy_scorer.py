import re
import math
import random
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter

from ..data.tcm_data import (
    EFFICACY_DESCRIPTIONS,
    MEDICAL_CASE_TEMPLATES,
    SYNDROME_NAMES,
)


class TCMSentimentAnalyzer:

    POSITIVE_KEYWORDS = {
        "愈": 0.9, "瘥": 0.85, "安": 0.8, "除": 0.85, "已": 0.75,
        "立": 0.3, "即": 0.2, "神": 0.4, "良": 0.35, "桴鼓": 0.8,
        "减": 0.5, "轻": 0.45, "平": 0.55, "霍然": 0.85, "应手": 0.8,
        "见效": 0.6, "好转": 0.55, "起色": 0.5, "收功": 0.7,
        "投之即效": 0.85, "效如": 0.9, "立起": 0.85, "不爽": 0.3,
        "爽": 0.25, "颇效": 0.7, "甚效": 0.8, "大效": 0.85,
        "痊愈": 0.92, "康复": 0.85, "根治": 0.88, "全消": 0.90,
        "悉除": 0.88, "顿愈": 0.92, "立效": 0.85, "奇效": 0.90,
        "速效": 0.80, "显效": 0.75, "佳效": 0.72, "奏效": 0.70,
        "消退": 0.60, "消失": 0.70, "缓解": 0.55, "安宁": 0.60,
        "通利": 0.55, "和调": 0.50, "复常": 0.75, "安和": 0.65,
        "诸恙悉平": 0.85, "病去八九": 0.75, "渐入坦途": 0.65,
        "药到病除": 0.90, "覆杯即安": 0.92, "一剂知": 0.80,
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
        for kw, w in cls.POSITIVE_KEYWORDS.items():
            if kw in text:
                modifier = 1.0
                for intensifier, mult in cls.INTENSIFIERS.items():
                    if intensifier + kw in text:
                        modifier = mult
                        break
                for neg in cls.NEGATION_PREFIXES:
                    idx = text.find(kw)
                    if idx > 0 and text[idx - 1] == neg:
                        modifier = -0.8
                        break
                score += w * modifier
                matched += 1
        for kw, w in cls.NEGATIVE_KEYWORDS.items():
            if kw in text:
                score += w
                matched += 1
        if matched == 0:
            return 0.0
        return max(-1.0, min(1.0, score / max(matched, 1) * 1.2))

    @classmethod
    def extract_days(cls, text: str) -> Optional[int]:
        for pat, d in cls.TIME_PATTERNS:
            if re.search(pat, text):
                return d
        return None


class OrdinalRegressionScorer:

    GRADE_THRESHOLDS = [-0.3, 0.1, 0.4, 0.7]
    GRADE_LABELS = ["无效", "一般", "良好", "优秀", "神效"]

    @classmethod
    def predict_grade(cls, sentiment: float, days: Optional[int]) -> Tuple[int, float]:
        base_score = sentiment
        if days is not None:
            time_weight = max(0.0, 1.0 - math.log1p(days) / 6.0)
            base_score = sentiment * 0.55 + (0.45 if sentiment > 0 else -0.45) * time_weight
        else:
            base_score = sentiment * 0.7
        grade = 0
        for i, t in enumerate(cls.GRADE_THRESHOLDS):
            if base_score > t:
                grade = i + 1
        normalized = max(0.0, min(100.0, (base_score + 1.0) * 50.0))
        return grade, round(normalized, 2)


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
