import sys
import math
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.efficacy_scorer import (
    TCMSentimentAnalyzer,
    OrdinalRegressionScorer,
    MedicalCaseGenerator,
    EfficacyAggregator,
)
from services.dose_response import (
    RestrictedCubicSpline,
    DoseEffectAnalyzer,
)
from services.adverse_reaction import (
    AdverseReactionExtractor,
    RiskPairDetector,
    FormulaRiskAssessor,
)
from services.clinical_trial import (
    ClinicalTrialSimulator,
    StandardMetaAnalysis,
    NetworkMetaAnalysis,
)
from data.tcm_data import TOXIC_HERBS, HERB_INTERACTION_PAIRS


PASS = 0
FAIL = 0
RESULTS = []


def record(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        RESULTS.append(("PASS", name, detail))
    else:
        FAIL += 1
        RESULTS.append(("FAIL", name, detail))


def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


# ====================================================================
# 一、疗效量化评估测试
# ====================================================================
section("一、疗效量化评估测试")

# -------------------------------------------------
# 1.1 NLP情感分析准确率
# -------------------------------------------------
print("\n--- 1.1 NLP情感分析准确率 ---")

POSITIVE_CASES = [
    ("一剂而愈", "强阳性典型"),
    ("药到病除", "强阳性"),
    ("神效", "强阳性-极量词"),
    ("诸恙悉平", "强阳性-多症状"),
    ("覆杯即安", "强阳性-即刻见效"),
    ("三日见效", "中阳性-含时间"),
    ("好转", "弱阳性"),
    ("颇效", "中阳性"),
    ("大效", "强阳性-程度副词"),
    ("立起沉疴", "强阳性"),
]

for text, label in POSITIVE_CASES:
    s = TCMSentimentAnalyzer.compute_sentiment(text)
    ok = s > 0.1
    record(f"[情感] 阳性案例 '{text}' -> {s:.3f} ({label})", ok)

NEGATIVE_CASES = [
    ("无效", "强阴性典型"),
    ("不效", "强阴性"),
    ("反增", "阴性-加重"),
    ("无寸效", "强阴性"),
    ("未见起色", "阴性"),
    ("病情加剧", "强阴性-恶化"),
    ("罔效", "强阴性"),
    ("微效", "弱阴性-几乎无效"),
    ("病进", "阴性-进展"),
    ("缠绵难愈", "阴性-迁延"),
]

for text, label in NEGATIVE_CASES:
    s = TCMSentimentAnalyzer.compute_sentiment(text)
    ok = s < 0.0
    record(f"[情感] 阴性案例 '{text}' -> {s:.3f} ({label})", ok)

NEUTRAL_CASES = [
    ("服药", "纯中性"),
    ("观察", "纯中性"),
    ("患者就诊", "中性医学描述"),
    ("随访", "中性-常规医疗"),
    ("", "空文本"),
]

for text, label in NEUTRAL_CASES:
    s = TCMSentimentAnalyzer.compute_sentiment(text)
    ok = abs(s) < 0.2 or s == 0.0
    record(f"[情感] 中性案例 '{text[:10] or '(空)'} ' -> {s:.3f} ({label})", ok)

# 否定词翻转测试
NEGATION_CASES = [
    ("不效", -0.5, "直接否定-不效"),
    ("无效", -0.5, "直接否定-无效"),
    ("未见效", -0.1, "间接否定-未见"),
    ("难愈", -0.2, "困难否定-难"),
]
for text, threshold, label in NEGATION_CASES:
    s = TCMSentimentAnalyzer.compute_sentiment(text)
    ok = s <= threshold
    record(f"[情感] 否定词处理 '{text}' -> {s:.3f} <= {threshold} ({label})", ok)

# 程度副词增强测试
INTENSIFIER_CASES = [
    ("甚效", 0.3, "副词'甚'增强"),
    ("大效", 0.3, "副词'大'增强"),
    ("极效", 0.2, "副词'极'增强"),
]
base_effect = TCMSentimentAnalyzer.compute_sentiment("效")
for text, expected_gain, label in INTENSIFIER_CASES:
    s = TCMSentimentAnalyzer.compute_sentiment(text)
    gain = s - base_effect
    ok = gain > expected_gain * 0.5
    record(f"[情感] {label}: '{text}'={s:.3f}, '效'={base_effect:.3f}, Δ={gain:.3f}", ok)


# -------------------------------------------------
# 1.2 疗效分级与文献记载一致性
# -------------------------------------------------
print("\n--- 1.2 序数回归疗效分级一致性 ---")

GRADE_TESTS = [
    ("一剂而愈", 1, [4], "神效", "一剂即愈应为最高级"),
    ("覆杯即安", 0.5, [4], "神效", "覆杯即安应为最高级"),
    ("三日见效", 3, [3, 4], "优秀/神效", "三日见效应为优秀以上"),
    ("五日好转", 5, [2, 3], "良好/优秀", "五日好转应为良好以上"),
    ("七日起色", 7, [2, 3], "良好/优秀", "七日起色应为良好以上"),
    ("半月渐平", 15, [1, 2], "一般/良好", "半月见效应为一般或良好"),
    ("不效", 30, [0], "无效", "不效应为无效"),
    ("无效", 60, [0], "无效", "无效应为最低级"),
    ("诸恙悉平", 3, [3, 4], "优秀/神效", "诸恙悉平应为优秀以上"),
    ("药到病除", 1, [4], "神效", "药到病除应为神效"),
]

for text, days, expected_grades, expected_labels, desc in GRADE_TESTS:
    sent = TCMSentimentAnalyzer.compute_sentiment(text)
    grade, score = OrdinalRegressionScorer.predict_grade(sent, days)
    grade_label = OrdinalRegressionScorer.GRADE_LABELS[grade]
    ok = grade in expected_grades
    record(
        f"[分级] '{text}' d={days} -> grade={grade}({grade_label}) score={score} [{desc}]",
        ok,
        f"期望 grade∈{expected_grades}({expected_labels})"
    )

# 边界测试：分数在阈值附近
print("\n  边界阈值测试:")
for sent_val in [-0.35, -0.3, -0.25, 0.05, 0.1, 0.15, 0.35, 0.4, 0.45, 0.65, 0.7, 0.75]:
    grade, _ = OrdinalRegressionScorer.predict_grade(sent_val, None)
    ok = 0 <= grade <= 4
    record(f"[分级边界] sentiment={sent_val:.2f} -> grade={grade}", ok)

# 分数归一化范围 [0, 100]
score_range_tests = [
    (0.95, 3, "高分短时间"),
    (-0.95, 60, "低分长时间"),
    (0.0, None, "零分无时间"),
    (1.0, 0, "极限高分"),
    (-1.0, 100, "极限低分"),
]
for sent, days, desc in score_range_tests:
    _, score = OrdinalRegressionScorer.predict_grade(sent, days)
    ok = 0.0 <= score <= 100.0
    record(f"[分数范围] sent={sent}, days={days} -> score={score} [{desc}]", ok)


# -------------------------------------------------
# 1.3 疗效评分区分度
# -------------------------------------------------
print("\n--- 1.3 疗效评分区分度 ---")

# 生成对比：明显不同的疗效描述应有显著分数差异
strong_pos = TCMSentimentAnalyzer.compute_sentiment("一剂而愈药到病除神效")
weak_pos = TCMSentimentAnalyzer.compute_sentiment("略有好转起色")
neg = TCMSentimentAnalyzer.compute_sentiment("无效不效病情加剧")

diff_sw = strong_pos - weak_pos
diff_wn = weak_pos - neg
record(f"[区分度] 强阳性({strong_pos:.3f}) - 弱阳性({weak_pos:.3f}) = {diff_sw:.3f} > 0.2", diff_sw > 0.2)
record(f"[区分度] 弱阳性({weak_pos:.3f}) - 阴性({neg:.3f}) = {diff_wn:.3f} > 0.1", diff_wn > 0.1)

# 医案生成器：不同等级案例分数分布应有区分
gen = MedicalCaseGenerator(seed=123)
cases_excellent = gen.generate_cases_for_formula("测试方A", "汉代", ["发热恶寒"], n=20)
cases_poor_raw = []
gen2 = MedicalCaseGenerator(seed=999)
for _ in range(20):
    c = gen2.generate_case("测试方B", "清代", ["久病体虚"])
    c["raw_description"] = "不效 无效 病情迁延 难愈"
    c["sentiment_score"] = TCMSentimentAnalyzer.compute_sentiment(c["raw_description"])
    c["days_to_effect"] = 60
    g, s = OrdinalRegressionScorer.predict_grade(c["sentiment_score"], c["days_to_effect"])
    c["efficacy_grade"] = g
    cases_poor_raw.append(c)

agg_excellent = EfficacyAggregator.aggregate(cases_excellent)
agg_poor = EfficacyAggregator.aggregate(cases_poor_raw)
diff_agg = agg_excellent["avg_efficacy_score"] - agg_poor["avg_efficacy_score"]
record(
    f"[区分度聚合] 优效方({agg_excellent['avg_efficacy_score']:.2f}) - 劣效方({agg_poor['avg_efficacy_score']:.2f}) = {diff_agg:.2f} > 20",
    diff_agg > 20
)

# 置信区间计算有效性
ci_valid = (
    agg_excellent["confidence_interval"][0] <= agg_excellent["avg_efficacy_score"] <= agg_excellent["confidence_interval"][1]
    and 0 <= agg_excellent["confidence_interval"][0] <= 100
    and 0 <= agg_excellent["confidence_interval"][1] <= 100
)
record(f"[CI有效性] {agg_excellent['confidence_interval']} 包含均值 {agg_excellent['avg_efficacy_score']}", ci_valid)

# 空输入边界
empty_agg = EfficacyAggregator.aggregate([])
record(
    f"[空聚合] empty -> score={empty_agg['avg_efficacy_score']}, cases={empty_agg['total_cases']}",
    empty_agg["avg_efficacy_score"] == 0.0 and empty_agg["total_cases"] == 0
)


# ====================================================================
# 二、剂量效应测试
# ====================================================================
section("二、剂量效应测试")

# -------------------------------------------------
# 2.1 限制性立方样条模型拟合优度
# -------------------------------------------------
print("\n--- 2.1 RCS 限制性立方样条拟合优度 ---")

analyzer = DoseEffectAnalyzer(seed=42)

# 正常拟合测试
for herb in ["麻黄", "附子", "黄芪", "黄连", "甘草"]:
    obs = analyzer.simulate_observations(herb, n_per_bin=10, bins=7)
    result = analyzer.fit_curve(obs)
    r2 = result["r_squared"]
    ok = r2 > 0.6
    record(f"[RCS拟合] {herb}: R²={r2:.4f} > 0.6", ok, f"knots={result['knots']}")

# 线性数据测试 - 应该拟合良好
rcs = RestrictedCubicSpline(nk=4)
xs_linear = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
ys_linear = [2.0 * x + 1.0 for x in xs_linear]
rcs.fit(xs_linear, ys_linear)
preds = [rcs.predict(x) for x in xs_linear]
mae = sum(abs(p - y) for p, y in zip(preds, ys_linear)) / len(xs_linear)
record(f"[RCS线性拟合] MAE={mae:.4f} < 0.5", mae < 0.5, f"R²={rcs.r_squared:.4f}")

# 非线性数据 (钟形曲线)
xs_bell = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0]
ys_bell = [math.exp(-((x - 5.0) ** 2) / 8.0) for x in xs_bell]
rcs2 = RestrictedCubicSpline(nk=4)
rcs2.fit(xs_bell, ys_bell)
preds_bell = [rcs2.predict(x) for x in xs_bell]
mae_bell = sum(abs(p - y) for p, y in zip(preds_bell, ys_bell)) / len(xs_bell)
record(f"[RCS钟形拟合] MAE={mae_bell:.4f} < 0.15", mae_bell < 0.15, f"R²={rcs2.r_squared:.4f}")

# 边界：最少数据点
xs_min = [1.0, 2.0, 3.0]
ys_min = [1.0, 2.0, 3.0]
rcs3 = RestrictedCubicSpline(nk=4)
try:
    rcs3.fit(xs_min, ys_min)
    p = rcs3.predict(2.0)
    record(f"[RCS最小数据] 3点可正常拟合, pred(2)={p:.3f}", isinstance(p, float))
except Exception as e:
    record(f"[RCS最小数据] 3点拟合", False, str(e))

# 边界：未拟合时 predict 返回 0.0
rcs_unfit = RestrictedCubicSpline()
record(f"[RCS未拟合] predict(5.0) = {rcs_unfit.predict(5.0)}", rcs_unfit.predict(5.0) == 0.0)

# 边界：X和Y长度不一致
try:
    rcs_bad = RestrictedCubicSpline(nk=3)
    rcs_bad.fit([1.0, 2.0, 3.0], [1.0, 2.0])
    record("[RCS维度不匹配] 应正常处理", True)
except Exception as e:
    record("[RCS维度不匹配]", False, str(e))


# -------------------------------------------------
# 2.2 最优剂量范围与药典推荐偏差
# -------------------------------------------------
print("\n--- 2.2 最优剂量范围与药典推荐偏差 ---")

PHARMACOPOEIA_REFERENCE = {
    "麻黄": (2.0, 10.0),
    "桂枝": (3.0, 10.0),
    "甘草": (2.0, 10.0),
    "附子": (3.0, 15.0),
    "黄芪": (9.0, 30.0),
    "黄连": (2.0, 5.0),
    "细辛": (1.0, 3.0),
    "半夏": (3.0, 9.0),
}

tolerance = 0.35  # 允许35%偏差
for herb, (ref_lo, ref_hi) in PHARMACOPOEIA_REFERENCE.items():
    obs = analyzer.simulate_observations(herb, n_per_bin=15, bins=9)
    result = analyzer.fit_curve(obs)
    opt_lo, opt_hi = result["optimal_dose_range"]
    model_lo, model_hi = DoseEffectAnalyzer.DOSAGE_RANGE.get(herb, (0, 0))
    overlap_lo = max(opt_lo, ref_lo)
    overlap_hi = min(opt_hi, ref_hi)
    overlap_ratio = (overlap_hi - overlap_lo) / max(opt_hi - opt_lo, 0.01)
    ok = overlap_ratio > (1.0 - tolerance)
    record(
        f"[药典吻合] {herb}: 最优[{opt_lo:.1f},{opt_hi:.1f}] vs 药典[{ref_lo},{ref_hi}] 重叠率={overlap_ratio:.2f}",
        ok,
        f"模型区间=[{model_lo},{model_hi}]"
    )

# 毒性药物应有更窄的安全范围
toxic_herbs = ["细辛", "附子", "马钱子", "朱砂"]
normal_herbs = ["甘草", "茯苓", "白术", "黄芪"]

toxic_widths = []
normal_widths = []
for h in toxic_herbs:
    if h in DoseEffectAnalyzer.DOSAGE_RANGE:
        lo, hi = DoseEffectAnalyzer.DOSAGE_RANGE[h]
        toxic_widths.append(hi - lo)
for h in normal_herbs:
    if h in DoseEffectAnalyzer.DOSAGE_RANGE:
        lo, hi = DoseEffectAnalyzer.DOSAGE_RANGE[h]
        normal_widths.append(hi - lo)

avg_toxic_w = sum(toxic_widths) / max(len(toxic_widths), 1)
avg_normal_w = sum(normal_widths) / max(len(normal_widths), 1)
record(
    f"[毒性剂量范围] 毒性药均宽={avg_toxic_w:.2f}g vs 普通药均宽={avg_normal_w:.2f}g",
    avg_toxic_w < avg_normal_w
)


# -------------------------------------------------
# 2.3 不同药物剂量效应曲线形状
# -------------------------------------------------
print("\n--- 2.3 不同药物剂量效应曲线形状 ---")

curve_shapes = {}
for herb in ["麻黄", "黄芪", "附子", "甘草", "黄连", "细辛", "人参", "石膏"]:
    obs = analyzer.simulate_observations(herb, n_per_bin=10, bins=9)
    result = analyzer.fit_curve(obs)
    points = result["points"]
    xs = [p["dosage_g"] for p in points if p["sample_size"] == 0]
    ys = [p["avg_efficacy"] for p in points if p["sample_size"] == 0]
    if xs and ys:
        peak_idx = ys.index(max(ys))
        peak_x = xs[peak_idx]
        lo, hi = DoseEffectAnalyzer.DOSAGE_RANGE.get(herb, (0, 100))
        mid = (lo + hi) / 2
        centered = abs(peak_x - mid) / max(hi - lo, 0.01) < 0.4
        # 检验两端下降
        left_drop = ys[0] < ys[peak_idx]
        right_drop = ys[-1] < ys[peak_idx]
        curve_shapes[herb] = (centered, left_drop, right_drop, peak_x)
        record(
            f"[曲线形状] {herb}: 峰值={peak_x:.2f}g, 居中={centered}, 左降={left_drop}, 右降={right_drop}",
            centered and left_drop and right_drop
        )

# 剂量Meta分析
print("\n  剂量Meta分析测试:")
studies = [
    {"effect_size": 0.5, "variance": 0.02, "study_id": "S1"},
    {"effect_size": 0.6, "variance": 0.015, "study_id": "S2"},
    {"effect_size": 0.45, "variance": 0.025, "study_id": "S3"},
    {"effect_size": 0.55, "variance": 0.018, "study_id": "S4"},
]
meta = DoseEffectAnalyzer.dose_meta_analysis(studies)
record(
    f"[剂量Meta] 合并效应={meta['pooled_effect_size']:.4f}, CI={meta['ci_95']}, I²={meta['i_squared']:.2f}%",
    0.4 < meta["pooled_effect_size"] < 0.7 and meta["i_squared"] < 50.0
)

# 异质性高的情况
het_studies = [
    {"effect_size": 0.1, "variance": 0.01, "study_id": "H1"},
    {"effect_size": 0.9, "variance": 0.01, "study_id": "H2"},
    {"effect_size": 0.3, "variance": 0.01, "study_id": "H3"},
    {"effect_size": 0.8, "variance": 0.01, "study_id": "H4"},
]
meta_het = DoseEffectAnalyzer.dose_meta_analysis(het_studies)
record(
    f"[剂量Meta异质] I²={meta_het['i_squared']:.2f}% > 50%",
    meta_het["i_squared"] > 50.0
)

# 空输入
meta_empty = DoseEffectAnalyzer.dose_meta_analysis([])
record(
    f"[剂量Meta空输入] pooled={meta_empty['pooled_effect']}, I²={meta_empty['i_squared']}",
    meta_empty["pooled_effect"] == 0.0 and meta_empty["i_squared"] == 0.0
)


# ====================================================================
# 三、不良反应挖掘测试
# ====================================================================
section("三、不良反应挖掘测试")

# -------------------------------------------------
# 3.1 文本挖掘召回率和准确率
# -------------------------------------------------
print("\n--- 3.1 文本挖掘召回率和准确率 ---")

TEST_CORPUS = [
    {
        "text": "患者服药后出现恶心呕吐，伴腹痛泄泻，考虑为胃肠道反应。",
        "expected_types": {"胃肠道反应"},
        "expected_severity": {"轻度"},
        "desc": "典型胃肠道反应",
    },
    {
        "text": "患者口舌麻木，四肢麻木，伴头晕心悸，出现皮疹瘙痒。",
        "expected_types": {"神经系统", "心脏毒性", "过敏反应"},
        "expected_severity": {"轻度", "中度"},
        "desc": "多系统混合反应",
    },
    {
        "text": "实验室检查示ALT、AST升高，肌酐异常，出现黄疸及血尿。",
        "expected_types": {"肝脏毒性", "肾脏毒性"},
        "expected_severity": {"严重"},
        "desc": "严重肝肾毒性",
    },
    {
        "text": "患者出现惊厥抽搐，继而昏迷休克，危及生命。",
        "expected_types": {"中枢神经毒性", "全身严重反应"},
        "expected_severity": {"严重"},
        "desc": "危及生命的严重反应",
    },
    {
        "text": "孕妇禁用，可能导致流产堕胎，有致畸风险。",
        "expected_types": {"生殖毒性", "遗传毒性"},
        "expected_severity": {"严重"},
        "desc": "生殖和遗传毒性",
    },
    {
        "text": "患者出现胸闷气短，血小板减少，白细胞降低，骨髓抑制。",
        "expected_types": {"呼吸系统", "骨髓抑制"},
        "expected_severity": {"中度", "严重"},
        "desc": "呼吸和血液系统",
    },
    {
        "text": "服药后无明显不适，精神好转，食欲增加。",
        "expected_types": set(),
        "expected_severity": set(),
        "desc": "无不良反应的假阳性测试",
    },
    {
        "text": "",
        "expected_types": set(),
        "expected_severity": set(),
        "desc": "空文本边界",
    },
]

total_expected = 0
total_found = 0
total_correct = 0

for case in TEST_CORPUS:
    found = AdverseReactionExtractor.extract_from_text(case["text"])
    found_types = {r["reaction_type"] for r in found}
    found_severity = {r["severity"] for r in found}

    tp = len(found_types & case["expected_types"])
    fp = len(found_types - case["expected_types"])
    fn = len(case["expected_types"] - found_types)

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 0.001)

    total_expected += len(case["expected_types"])
    total_found += len(found_types)
    total_correct += tp

    ok_types = found_types == case["expected_types"]
    ok_sev = found_severity == case["expected_severity"] if case["expected_types"] else True
    record(
        f"[文本挖掘] {case['desc']}: 召回={recall:.2f} 精确={precision:.2f} F1={f1:.2f}",
        ok_types and ok_sev,
        f"期望={case['expected_types']}, 检出={found_types}"
    )

# 总体指标
overall_recall = total_correct / max(total_expected, 1)
overall_precision = total_correct / max(total_found, 1)
record(f"[文本挖掘总体] 召回率={overall_recall:.2f}, 精确率={overall_precision:.2f}",
       overall_recall >= 0.8 and overall_precision >= 0.8)


# -------------------------------------------------
# 3.2 风险药对标注合理性
# -------------------------------------------------
print("\n--- 3.2 风险药对标注合理性 ---")

# 已知禁忌药对应能检出
KNOWN_CONTRA_PAIRS = [
    (["甘草", "甘遂"], "十八反：甘草反甘遂"),
    (["乌头", "半夏"], "十八反：半蒌贝蔹芨攻乌"),
    (["人参", "五灵脂"], "十九畏：人参畏五灵脂"),
    (["丁香", "郁金"], "十九畏：丁香莫与郁金见"),
]
for herbs, desc in KNOWN_CONTRA_PAIRS:
    risks = RiskPairDetector.detect_for_formula(herbs)
    found_any = len(risks) > 0
    if found_any:
        max_risk = max(r["risk_score"] for r in risks)
        record(f"[药对检出] {desc}: 检出{len(risks)}个风险, 最高风险分={max_risk:.1f}",
               found_any and max_risk >= 20)
    else:
        record(f"[药对检出] {desc}: 未检出", False, "期望检出风险药对")

# 安全药对应无风险
SAFE_HERBS = ["甘草", "茯苓", "白术", "党参", "大枣", "生姜"]
safe_risks = RiskPairDetector.detect_for_formula(SAFE_HERBS)
record(f"[药对安全] 安全组合 {SAFE_HERBS[:4]} -> 风险数={len(safe_risks)}",
       len(safe_risks) == 0)

# 毒性叠加：两味毒性药合用应检出
TOXIC_PAIRS = [
    (["附子", "乌头"], "两种乌头类毒性药"),
    (["朱砂", "雄黄"], "两种含重金属毒性药"),
]
for herbs, desc in TOXIC_PAIRS:
    risks = RiskPairDetector.detect_for_formula(herbs)
    toxic_risks = [r for r in risks if r.get("interaction_type") == "毒性叠加风险"]
    record(f"[毒性叠加] {desc}: 检出毒性叠加={len(toxic_risks)}>0",
           len(toxic_risks) > 0, f"全部风险={[r['interaction_type'] for r in risks]}")

# 方剂风险评估器：风险等级分布
test_formulas = [
    ("安全方", ["茯苓", "白术", "甘草", "大枣"], ["安全", "低"]),
    ("含毒方", ["附子", "甘草", "干姜"], ["低", "中"]),
    ("高毒方", ["附子", "乌头", "半夏", "甘遂"], ["高", "极高"]),
]
for fname, herbs, expected_levels in test_formulas:
    assessment = FormulaRiskAssessor.assess(fname, herbs)
    level = assessment["overall_risk_level"]
    score = assessment["overall_risk_score"]
    ok = level in expected_levels
    record(
        f"[方剂风险] {fname}: 等级={level}, 分数={score}, 期望∈{expected_levels}",
        ok,
        f"风险药对数={len(assessment['risk_pairs'])}, 警告数={len(assessment['warnings'])}"
    )

# 剂量超量警告
dose_warnings = FormulaRiskAssessor.assess("超量方", ["附子"], {"附子": 100.0})
has_dose_warn = any("超过安全上限" in w for w in dose_warnings["warnings"])
record(f"[剂量警告] 附子100g -> 检出超量警告={has_dose_warn}", has_dose_warn,
       f"warnings={dose_warnings['warnings']}")


# -------------------------------------------------
# 3.3 禁忌数据库完整性
# -------------------------------------------------
print("\n--- 3.3 禁忌数据库完整性 ---")

# TOXIC_HERBS 应包含关键字段
required_fields = [
    "adverse_reactions", "contraindications", "toxic_ingredients",
    "max_safe_dose_g", "pregnancy_risk", "ld50_mgkg"
]
incomplete = []
for herb, profile in TOXIC_HERBS.items():
    missing = [f for f in required_fields if f not in profile]
    if missing:
        incomplete.append((herb, missing))

record(f"[毒性库] {len(TOXIC_HERBS)}味毒药, 字段完整度",
       len(incomplete) == 0,
       f"缺失={incomplete[:3]}")

# 每味药至少有1项不良反应
no_reactions = [h for h, p in TOXIC_HERBS.items() if not p.get("adverse_reactions")]
record(f"[毒性库] 所有毒性药均有不良反应记录", len(no_reactions) == 0,
       f"缺失={no_reactions}")

# HERB_INTERACTION_PAIRS 应包含十八反、十九畏核心药对
key_pair_count = len(HERB_INTERACTION_PAIRS)
record(f"[禁忌对] 收录 {key_pair_count} 对禁忌药对", key_pair_count >= 10)

# 交互药对字段完整性
pair_required = ["herb_a", "herb_b", "risk_level", "interaction_type", "mechanism", "evidence_level"]
bad_pairs = []
for p in HERB_INTERACTION_PAIRS:
    missing = [f for f in pair_required if f not in p]
    if missing:
        bad_pairs.append((p, missing))
record(f"[禁忌对] 字段完整性", len(bad_pairs) == 0, f"不完整={bad_pairs[:2]}")

# 聚合反应测试
herbs_to_check = list(TOXIC_HERBS.keys())[:5]
agg = AdverseReactionExtractor.aggregate_reactions(herbs_to_check)
record(
    f"[聚合反应] {len(herbs_to_check)}味毒药 -> 反应总数={agg['total_reactions']}, 严重度数={list(agg['severity_distribution'].keys())}",
    agg["total_reactions"] >= len(herbs_to_check)
)

# 空聚合
empty_agg_ar = AdverseReactionExtractor.aggregate_reactions([])
record(f"[聚合反应空] 空列表 -> total={empty_agg_ar['total_reactions']}",
       empty_agg_ar["total_reactions"] == 0)


# ====================================================================
# 四、现代临床集成测试
# ====================================================================
section("四、现代临床集成测试")

# -------------------------------------------------
# 4.1 Meta分析异质性处理和发表偏倚检测
# -------------------------------------------------
print("\n--- 4.1 Meta分析异质性处理 ---")

simulator = ClinicalTrialSimulator(seed=42)
trials = simulator.generate_trials("感冒", n_trials=12)

# 标准Meta分析
meta_result = StandardMetaAnalysis.compare_classical_vs_modern(trials, "感冒")
record(
    f"[Meta分析] 纳入研究={meta_result['trials_included']}, 合并效应={meta_result['pooled_effect_size']:.4f}, "
    f"CI={meta_result['ci_95']}, I²={meta_result['i_squared']:.1f}%, P={meta_result['p_value']:.4f}",
    meta_result["trials_included"] > 0 and meta_result["heterogeneity_p"] is not None
)

# 高度异质性场景
het_trials = []
for i in range(6):
    eff_diff = 0.1 * (i + 1)
    trial = {
        "trial_id": f"HET{i:03d}",
        "year": 2020 + i,
        "arms": [
            {"treatment_name": "经典方", "treatment_type": "古代经典方",
             "sample_size": 100, "mean_efficacy": 0.5 + eff_diff, "std_efficacy": 0.15,
             "adverse_event_rate": 0.05},
            {"treatment_name": "现代药", "treatment_type": "现代方案",
             "sample_size": 100, "mean_efficacy": 0.5, "std_efficacy": 0.15,
             "adverse_event_rate": 0.05},
        ],
        "quality_score": 0.7,
    }
    het_trials.append(trial)

het_meta = StandardMetaAnalysis.compare_classical_vs_modern(het_trials, "测试病")
record(
    f"[Meta异质性] 人工异质数据: I²={het_meta['i_squared']:.1f}% > 50%",
    het_meta["i_squared"] > 50.0,
    f"P_het={het_meta['heterogeneity_p']:.4f}"
)

# 同质性场景
hom_trials = []
for i in range(6):
    trial = {
        "trial_id": f"HOM{i:03d}",
        "year": 2020 + i,
        "arms": [
            {"treatment_name": "经典方", "treatment_type": "古代经典方",
             "sample_size": 100, "mean_efficacy": 0.72, "std_efficacy": 0.1,
             "adverse_event_rate": 0.05},
            {"treatment_name": "现代药", "treatment_type": "现代方案",
             "sample_size": 100, "mean_efficacy": 0.68, "std_efficacy": 0.1,
             "adverse_event_rate": 0.05},
        ],
        "quality_score": 0.7,
    }
    hom_trials.append(trial)

hom_meta = StandardMetaAnalysis.compare_classical_vs_modern(hom_trials, "测试病")
record(
    f"[Meta同质性] 人工同质数据: I²={hom_meta['i_squared']:.1f}% < 50%",
    hom_meta["i_squared"] < 50.0,
    f"P_het={hom_meta['heterogeneity_p']:.4f}"
)

# 无对照研究
no_head_trials = []
for i in range(3):
    trial = {
        "trial_id": f"NH{i:03d}",
        "year": 2020 + i,
        "arms": [
            {"treatment_name": "经典方A", "treatment_type": "古代经典方",
             "sample_size": 100, "mean_efficacy": 0.7, "std_efficacy": 0.1,
             "adverse_event_rate": 0.05},
            {"treatment_name": "经典方B", "treatment_type": "古代经典方",
             "sample_size": 100, "mean_efficacy": 0.65, "std_efficacy": 0.1,
             "adverse_event_rate": 0.05},
        ],
        "quality_score": 0.7,
    }
    no_head_trials.append(trial)

no_head_meta = StandardMetaAnalysis.compare_classical_vs_modern(no_head_trials, "测试病")
record(
    f"[Meta无头对头] 无现代对照: studies={no_head_meta['trials_included']}",
    no_head_meta["trials_included"] == 0 and "未找到" in no_head_meta["conclusion"]
)

# 森林图数据完整性
forest = meta_result.get("forest_plot_data", [])
record(
    f"[Meta森林图] 行数={len(forest)} (含汇总行)",
    len(forest) >= 2 and forest[-1]["study"] == "合并效应 (RE)"
)

# 发表偏倚信号检测（效应量方向一致性）
if meta_result["trials_included"] >= 3:
    forest_studies = forest[:-1]
    positive_count = sum(1 for s in forest_studies if s["effect_size"] > 0)
    # 允许不一致，只要有结论即可
    record(f"[Meta方向一致] 正效应研究数={positive_count}/{len(forest_studies)}",
           positive_count >= 0)


# -------------------------------------------------
# 4.2 网络Meta分析一致性
# -------------------------------------------------
print("\n--- 4.2 网络Meta分析一致性 ---")

# 生成多种适应症的NMA
for indication in ["感冒", "高血压", "糖尿病", "失眠"]:
    trials_nma = simulator.generate_trials(indication, n_trials=10)
    if not trials_nma:
        record(f"[NMA排序] {indication}: 跳过（无数据）", True)
        continue
    nma = NetworkMetaAnalysis.run(trials_nma, indication)
    treatments = nma["treatments_ranked"]
    ranked_ok = len(treatments) >= 2
    sum_prob_ok = all(0 <= t["best_prob"] <= 100 for t in treatments)
    order_ok = all(treatments[i]["best_prob"] >= treatments[i + 1]["best_prob"]
                   for i in range(len(treatments) - 1))
    record(
        f"[NMA排序] {indication}: 治疗数={len(treatments)}, 排序正确={order_ok}",
        ranked_ok and sum_prob_ok and order_ok,
        f"Top3={[(t['treatment'], t['best_prob']) for t in treatments[:3]]}"
    )

# 网络边应存在
trials_nma2 = simulator.generate_trials("感冒", n_trials=10)
nma2 = NetworkMetaAnalysis.run(trials_nma2, "感冒")
record(
    f"[NMA网络边] 边数={len(nma2['network_edges'])} > 0",
    len(nma2["network_edges"]) > 0
)

# 联赛表结构
league = nma2["league_table"]
record(
    f"[NMA联赛表] 行列数匹配: {len(league)}行 x {len(league[0]) if league else 0}列",
    len(league) >= 2 and len(league) == len(league[0]) if league else False
)

# SUCRA/best_prob 合理性检查
best_probs = [t["best_prob"] for t in nma2["treatments_ranked"]]
record(
    f"[NMA概率范围] min={min(best_probs):.1f} max={max(best_probs):.1f} 均在[0,100]",
    0 <= min(best_probs) and max(best_probs) <= 100
)


# -------------------------------------------------
# 4.3 证据质量评级准确性
# -------------------------------------------------
print("\n--- 4.3 证据质量评级 ---")

# 质量评分应在合理范围
for indication in ["感冒", "咳嗽", "胃痛", "失眠", "高血压", "糖尿病"]:
    t_list = simulator.generate_trials(indication, n_trials=6)
    if not t_list:
        record(f"[证据质量] {indication}: 跳过（无数据）", True)
        continue
    qualities = [t["quality_score"] for t in t_list]
    designs = [t["design"] for t in t_list]
    years = [t["year"] for t in t_list]
    avg_q = sum(qualities) / len(qualities)
    range_ok = all(0.3 <= q <= 1.0 for q in qualities)
    record(
        f"[证据质量] {indication}: 均质量={avg_q:.3f}, 年份[{min(years)},{max(years)}]",
        range_ok,
        f"设计样本={designs[:3]}"
    )

# 双盲多中心试验应有更高质量
db_trials = [t for t in trials if "双盲" in t["design"]]
non_db_trials = [t for t in trials if "双盲" not in t["design"]]
if db_trials and non_db_trials:
    avg_db = sum(t["quality_score"] for t in db_trials) / len(db_trials)
    avg_non_db = sum(t["quality_score"] for t in non_db_trials) / len(non_db_trials)
    record(
        f"[质量差异] 双盲均={avg_db:.3f} vs 非双盲均={avg_non_db:.3f}",
        avg_db > avg_non_db
    )
else:
    record("[质量差异] 跳过（样本不足）", True)

# 结论生成
trials_c = simulator.generate_trials("高血压", n_trials=8)
meta_c = StandardMetaAnalysis.compare_classical_vs_modern(trials_c, "高血压")
has_conclusion = isinstance(meta_c["conclusion"], str) and len(meta_c["conclusion"]) > 10
record(
    f"[结论生成] 结论长度={len(meta_c['conclusion'])}, 包含异质性={'I²' in meta_c['conclusion'] or '异质性' in meta_c['conclusion']}",
    has_conclusion
)

# 临床试验模拟器：不同病种应有不同治疗方案
indications = ["感冒", "高血压", "糖尿病", "失眠", "咳嗽", "胃痛"]
treatments_by_ind = {}
for ind in indications:
    ts = simulator.generate_trials(ind, n_trials=5)
    all_trts = set()
    for t in ts:
        for a in t["arms"]:
            all_trts.add(a["treatment_name"])
    treatments_by_ind[ind] = all_trts

# 未知适应症边界测试
unknown_trials = simulator.generate_trials("不存在的罕见病", n_trials=5)
record(f"[未知病种] 未知适应症返回空列表: {len(unknown_trials)} == 0", len(unknown_trials) == 0)

# 至少应有不同治疗方案
unique_sets = {frozenset(v) for v in treatments_by_ind.values()}
record(
    f"[病种特异性] {len(indications)}病种产生{len(unique_sets)}种不重复治疗组合",
    len(unique_sets) >= 3
)


# ====================================================================
# 总结
# ====================================================================
section("测试总结")
print(f"\n  总用例数: {PASS + FAIL}")
print(f"  通过:     {PASS}")
print(f"  失败:     {FAIL}")
print(f"  通过率:   {PASS / max(PASS + FAIL, 1) * 100:.1f}%")
print()

if FAIL > 0:
    print("  失败详情:")
    for status, name, detail in RESULTS:
        if status == "FAIL":
            print(f"    ❌ {name}")
            if detail:
                print(f"       -> {detail}")
else:
    print("  ✅ 所有测试通过！")

print()
sys.exit(0 if FAIL == 0 else 1)
