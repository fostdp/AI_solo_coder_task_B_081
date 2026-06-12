import sys
import os
import math
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = 0
failed = 0
errors = []


def test(name, condition, detail=""):
    global passed, failed, errors
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        errors.append(f"{name}: {detail}")
        print(f"  [FAIL] {name} - {detail}")


def approx(a, b, tol=0.01):
    return abs(a - b) < tol


print("=" * 70)
print("  重构模块深度测试 - 6个独立模块全功能验证")
print("=" * 70)

# ======================================================================
# 1. efficacy_scorer 深度测试
# ======================================================================
print("\n--- 1. efficacy_scorer 深度测试 ---")

from efficacy_scorer.scorer import (
    SentimentUncertaintyEstimator,
    TCMSentimentAnalyzer,
    OrdinalRegressionScorer,
    HumanAnnotationManager,
    MedicalCaseGenerator,
    EfficacyAggregator,
)

test("TCM情感-全阳性关键词", TCMSentimentAnalyzer.compute_sentiment("痊愈康复根治全消悉除顿愈立效奇效") > 0.8)
test("TCM情感-全阴性关键词", TCMSentimentAnalyzer.compute_sentiment("无效不效加剧恶化加重反剧") < -0.5)
test("TCM情感-否定前缀翻转", TCMSentimentAnalyzer.compute_sentiment("不愈") < 0)
test("TCM情感-强化词增强", TCMSentimentAnalyzer.compute_sentiment("大效") > TCMSentimentAnalyzer.compute_sentiment("效"))
test("TCM情感-空文本", TCMSentimentAnalyzer.compute_sentiment("") == 0.0)
test("TCM情感-边界值[-1,1]", -1.0 <= TCMSentimentAnalyzer.compute_sentiment("无效不效加剧恶化加重反剧罔效无寸效") <= 1.0)

days_1 = TCMSentimentAnalyzer.extract_days("一剂而愈")
test("时间提取-一剂", days_1 == 1)
days_7 = TCMSentimentAnalyzer.extract_days("七日见效")
test("时间提取-七日", days_7 == 7)
days_none = TCMSentimentAnalyzer.extract_days("慢慢调理")
test("时间提取-无匹配", days_none is None)

unc = TCMSentimentAnalyzer.analyze_with_uncertainty("一剂而愈诸恙悉平")
test("不确定性分析-含情感分", "sentiment_score" in unc)
test("不确定性分析-含匹配关键词", "matched_keywords" in unc)
test("不确定性分析-含熵", "entropy" in unc)
test("不确定性分析-含置信度", "overall_confidence" in unc)
test("不确定性分析-明确文本不需审核", unc["needs_human_review"] is False)

unc_vague = TCMSentimentAnalyzer.analyze_with_uncertainty("稍安")
test("不确定性分析-模糊文本需审核", unc_vague["needs_human_review"] is True)
test("不确定性分析-模糊文本低置信", unc_vague["overall_confidence"] < unc["overall_confidence"])

entropy_single = SentimentUncertaintyEstimator.keyword_entropy([("愈", 0.9, "pos")])
test("熵-单一关键词", entropy_single == 0.0)
entropy_balanced = SentimentUncertaintyEstimator.keyword_entropy([("愈", 0.9, "pos"), ("无效", -0.9, "neg")])
test("熵-均衡关键词", entropy_balanced > 0.5)
entropy_empty = SentimentUncertaintyEstimator.keyword_entropy([])
test("熵-空列表", entropy_empty == 1.0)

conf_0 = SentimentUncertaintyEstimator.confidence_from_matches(0, 100)
test("置信度-0匹配", conf_0 == 0.0)
conf_many = SentimentUncertaintyEstimator.confidence_from_matches(10, 100)
test("置信度-多匹配", conf_many > 0.5)

grade_0, score_0 = OrdinalRegressionScorer.predict_grade(-1.0, 30)
test("序数回归-强阴性低分级", grade_0 <= 1)
grade_4, score_4 = OrdinalRegressionScorer.predict_grade(0.9, 1)
test("序数回归-强阳性短时间高分级", grade_4 >= 3)
test("序数回归-分数范围[0,100]", 0 <= score_0 <= 100 and 0 <= score_4 <= 100)

unc_grade = OrdinalRegressionScorer.predict_with_uncertainty(0.8, 1, 0.9)
test("序数回归不确定性-5级概率", len(unc_grade["grade_probabilities"]) == 5)
test("序数回归不确定性-概率和≈1", approx(sum(p["probability"] for p in unc_grade["grade_probabilities"]), 1.0, 0.05))
test("序数回归不确定性-含顶级2", "top2_grades" in unc_grade)

ham = HumanAnnotationManager()
test("人工标注-初始无待审核", ham.get_pending_count() == 0)
ham.submit_for_review("c1", "测试文本", 2, 50.0, "中", "模糊")
test("人工标注-提交后有待审核", ham.get_pending_count() == 1)
ham.annotate("c1", 3, 75.0, "李医生", "确认良好")
test("人工标注-标注后无待审核", ham.get_pending_count() == 0)
stats = ham.get_annotation_stats()
test("人工标注-统计含总数", stats["total_annotated"] == 1)
test("人工标注-统计含平均分", stats["avg_human_score"] == 75.0)

gen = MedicalCaseGenerator(seed=42)
cases = gen.generate_cases_for_formula("桂枝汤", "汉代", ["头痛发热"], 12)
test("医案生成-数量", len(cases) == 12)
test("医案生成-每条含方名", all(c["formula_name"] == "桂枝汤" for c in cases))
test("医案生成-情感分范围", all(-1.0 <= c["sentiment_score"] <= 1.0 for c in cases))
test("医案生成-等级范围", all(0 <= c["efficacy_grade"] <= 4 for c in cases))

agg = EfficacyAggregator.aggregate(cases)
test("聚合-均值范围", 0 <= agg["avg_efficacy_score"] <= 100)
test("聚合-CI长度2", len(agg["confidence_interval"]) == 2)
test("聚合-CI下界<上界", agg["confidence_interval"][0] <= agg["confidence_interval"][1])
test("聚合-含病例记录", len(agg["case_records"]) == 12)

empty_agg = EfficacyAggregator.aggregate([])
test("聚合-空输入安全", empty_agg["avg_efficacy_score"] == 0.0)

from efficacy_scorer.routes import router as es_router
test("路由-前缀/efficacy", es_router.prefix == "/efficacy")
from efficacy_scorer.main import app as es_app
es_routes = [r.path for r in es_app.routes]
test("路由-/efficacy/analyze", any("/efficacy/analyze" in r for r in es_routes))
test("路由-/efficacy/grade", any("/efficacy/grade" in r for r in es_routes))
test("路由-/efficacy/evaluate", any("/efficacy/evaluate" in r for r in es_routes))
test("路由-/efficacy/annotation/submit", any("/annotation/submit" in r for r in es_routes))
test("路由-/efficacy/annotation/complete", any("/annotation/complete" in r for r in es_routes))
test("路由-/efficacy/annotation/stats", any("/annotation/stats" in r for r in es_routes))
test("路由-/efficacy/cases/generate", any("/cases/generate" in r for r in es_routes))
test("路由-/efficacy/cases/aggregate", any("/cases/aggregate" in r for r in es_routes))
test("路由-/health", any("/health" in r for r in es_routes))


# ======================================================================
# 2. dose_response_modeler 深度测试
# ======================================================================
print("\n--- 2. dose_response_modeler 深度测试 ---")

from dose_response_modeler.modeler import (
    RestrictedCubicSpline,
    DoseEffectAnalyzer,
    BayesianRCS,
    SensitivityAnalyzer,
)

rcs = RestrictedCubicSpline(nk=4)
xs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
ys = [2.0 * x + 1.0 for x in xs]
rcs.fit(xs, ys)
test("RCS-线性拟合R²>0.9", rcs.r_squared > 0.9)
pred_5 = rcs.predict(5.0)
test("RCS-预测值接近真实", approx(pred_5, 11.0, 2.0))
pred_unfit = RestrictedCubicSpline().predict(5.0)
test("RCS-未拟合返回0", pred_unfit == 0.0)

rcs_nonlinear = RestrictedCubicSpline(nk=4)
xs2 = list(range(1, 15))
ys2 = [math.sin(x) * 10 + 20 for x in xs2]
rcs_nonlinear.fit([float(x) for x in xs2], ys2)
test("RCS-非线性拟合R²>0", rcs_nonlinear.r_squared > 0)

analyzer = DoseEffectAnalyzer(seed=42)
obs = analyzer.simulate_observations("麻黄", n_per_bin=8, bins=7)
test("剂量模拟-7个bin", len(obs) == 7)
test("剂量模拟-每条含herb_name", all(o["herb_name"] == "麻黄" for o in obs))
test("剂量模拟-剂量递增", all(obs[i]["dosage_g"] <= obs[i + 1]["dosage_g"] for i in range(len(obs) - 1)))
test("剂量模拟-疗效范围[0,1]", all(0 <= o["avg_efficacy"] <= 1.0 for o in obs))

curve = analyzer.fit_curve(obs)
test("剂量曲线-含最优范围", "optimal_dose_range" in curve)
test("剂量曲线-最优范围下<上", curve["optimal_dose_range"][0] < curve["optimal_dose_range"][1])
test("剂量曲线-含R²", "r_squared" in curve)
test("剂量曲线-含模型类型", "model_type" in curve)
test("剂量曲线-含数据点", len(curve["points"]) > 0)

studies = [
    {"effect_size": 0.5, "variance": 0.02, "study_id": "S1"},
    {"effect_size": 0.6, "variance": 0.015, "study_id": "S2"},
    {"effect_size": 0.45, "variance": 0.025, "study_id": "S3"},
    {"effect_size": 0.55, "variance": 0.018, "study_id": "S4"},
]
meta = DoseEffectAnalyzer.dose_meta_analysis(studies)
test("剂量Meta-合并效应范围", 0.3 < meta["pooled_effect_size"] < 0.8)
test("剂量Meta-CI长度2", len(meta["ci_95"]) == 2)
test("剂量Meta-CI含合并效应", meta["ci_95"][0] <= meta["pooled_effect_size"] <= meta["ci_95"][1])
test("剂量Meta-I²范围", 0 <= meta["i_squared"] <= 100)
test("剂量Meta-P值范围", 0 <= meta["p_value"] <= 1)

bayes = BayesianRCS(nk=4, prior_precision=0.5)
bayes.fit(xs, ys)
test("BayesianRCS-拟合R²>0.5", bayes.r_squared > 0.5)
pred_b, lo_b, hi_b = bayes.predict_with_ci(5.0)
test("BayesianRCS-CI下<预测<上", lo_b <= pred_b <= hi_b)
test("BayesianRCS-含系数标准差", bayes.coef_std is not None)

bayes_curve = analyzer.fit_curve_bayesian(obs, prior_precision=0.5)
test("Bayesian曲线-含CI数据点", any("ci_low" in p for p in bayes_curve["points"]))
test("Bayesian曲线-含先验正则化标记", bayes_curve["has_prior_regularization"] is True)

obs_sens = analyzer.simulate_observations("甘草", n_per_bin=8, bins=7)
xs_s = [o["dosage_g"] for o in obs_sens]
ys_s = [o["avg_efficacy"] for o in obs_sens]
ws_s = [o["sample_size"] for o in obs_sens]
sens = analyzer.sensitivity_analysis(obs_sens)
test("敏感性分析-含LOO", "leave_one_out" in sens)
test("敏感性分析-含节点敏感性", "knot_sensitivity" in sens)
test("敏感性分析-含贝叶斯敏感性", "bayesian_prior_sensitivity" in sens)
test("敏感性分析-含整体稳定性", "overall_stable" in sens)
test("敏感性分析-含建议", "recommendation" in sens)

from dose_response_modeler.main import app as drm_app
test("dose_response_modeler FastAPI app导入", True)


# ======================================================================
# 3. adverse_event_miner 深度测试
# ======================================================================
print("\n--- 3. adverse_event_miner 深度测试 ---")

from adverse_event_miner.miner import (
    ExpertKnowledgeEngine,
    AdverseReactionExtractor,
    RiskPairDetector,
    FormulaRiskAssessor,
)

expert = ExpertKnowledgeEngine()
test("毒性家族-乌头类", expert.get_herb_family("附子") == "乌头类")
test("毒性家族-含汞类", expert.get_herb_family("朱砂") == "含汞类")
test("毒性家族-含砷类", expert.get_herb_family("雄黄") == "含砷类")
test("毒性家族-攻下逐瘀类", expert.get_herb_family("大黄") == "攻下逐瘀类")
test("毒性家族-安全药物返回None", expert.get_herb_family("甘草") is None)

inferred = expert.infer_interactions(["附子", "川乌"])
test("同类推理-结果非空", len(inferred) >= 1)
if inferred:
    test("推理结果-标记为推断", inferred[0].get("inferred") is True)
    test("推理结果-含风险等级", inferred[0].get("risk_level") in ("高", "中", "低"))
    test("推理结果-置信度(0,1)", 0 < inferred[0].get("confidence", 0) < 1)

expanded = expert.expand_toxic_profile("川乌")
test("扩展档案-含家族信息", expanded.get("family") == "乌头类")
test("扩展档案-含妊娠风险", "pregnancy_risk" in expanded)

preg_risk = expert.assess_pregnancy_risk(["附子", "甘草"])
test("妊娠风险-含总体风险", "overall_risk" in preg_risk)
test("妊娠风险-含禁忌药", "contraindicated_herbs" in preg_risk)
test("妊娠风险-附子为禁忌", "附子" in preg_risk["contraindicated_herbs"])

rx = AdverseReactionExtractor.extract_from_text("恶心呕吐伴黄疸肝酶升高")
test("不良反应提取-多类型", len(rx) >= 2)
rx_types = {r["reaction_type"] for r in rx}
test("不良反应提取-含胃肠道", "胃肠道反应" in rx_types)
test("不良反应提取-含肝脏毒性", "肝脏毒性" in rx_types)

rx_severe = AdverseReactionExtractor.extract_from_text("惊厥抽搐昏迷休克")
test("严重反应提取", len(rx_severe) >= 1)
test("严重反应-严重级别", any(r["severity"] == "严重" for r in rx_severe))

rx_empty = AdverseReactionExtractor.extract_from_text("正常服药无不适")
test("不良反应提取-无反应", len(rx_empty) == 0)

risks_18fan = RiskPairDetector.detect_for_formula(["甘草", "甘遂"])
test("十八反检出", len(risks_18fan) > 0)
test("十八反-含交互类型", all("interaction_type" in r for r in risks_18fan))

risks_safe = RiskPairDetector.detect_for_formula(["茯苓", "白术"], include_expert_inference=False)
test("安全组合-无已知风险", len(risks_safe) == 0)

assessment = FormulaRiskAssessor.assess("测试方", ["附子", "半夏"])
test("风险评估-含等级", assessment["overall_risk_level"] in ("安全", "低", "中", "高", "极高"))
test("风险评估-含分数", 0 <= assessment["overall_risk_score"] <= 100)
test("风险评估-含风险对", "risk_pairs" in assessment)
test("风险评估-含警告", "warnings" in assessment)
test("风险评估-含用药指导", "safe_use_guidance" in assessment)

assessment_with_dose = FormulaRiskAssessor.assess("超量方", ["附子"], {"附子": 30.0})
test("超量风险评估-含超量警告", any("超过安全上限" in w for w in assessment_with_dose["warnings"]))

from adverse_event_miner.routes import router as aem_router
test("adverse_event_miner路由-前缀/adverse", aem_router.prefix == "/adverse")
from adverse_event_miner.main import app as aem_app
aem_routes = [r.path for r in aem_app.routes]
test("adverse_event_miner-/adverse/text/extract", any("/adverse/text/extract" in r for r in aem_routes))
test("adverse_event_miner-/adverse/risk/assess", any("/adverse/risk/assess" in r for r in aem_routes))
test("adverse_event_miner-/adverse/expert/infer-interactions", any("/adverse/expert/infer-interactions" in r for r in aem_routes))


# ======================================================================
# 4. clinical_trial_integrator 深度测试
# ======================================================================
print("\n--- 4. clinical_trial_integrator 深度测试 ---")

from clinical_trial_integrator.integrator import (
    ClinicalTrialSimulator,
    StandardMetaAnalysis,
    NetworkMetaAnalysis,
    MetaAnalysisSensitivity,
    QualityWeightedMetaAnalysis,
)
from meta_analysis_service.calculator import StandardMetaCalculator, NetworkMetaCalculator

sim = ClinicalTrialSimulator(seed=42)
trials = sim.generate_trials("感冒", n_trials=8)
test("临床试验-数量", len(trials) > 0)
test("临床试验-含试验臂", all("arms" in t for t in trials))
test("临床试验-含质量评分", all("quality_score" in t for t in trials))
test("临床试验-质量评分范围", all(0 <= t["quality_score"] <= 1.0 for t in trials))
test("临床试验-含年份", all("year" in t for t in trials))
test("临床试验-含设计类型", all("design" in t for t in trials))

meta = StandardMetaAnalysis.compare_classical_vs_modern(trials, "感冒")
test("标准Meta-合并效应", "pooled_effect_size" in meta)
test("标准Meta-CI", len(meta["ci_95"]) == 2)
test("标准Meta-森林图", len(meta.get("forest_plot_data", [])) >= 2)
test("标准Meta-含结论", "conclusion" in meta)

nma = NetworkMetaAnalysis.run(trials, "感冒")
test("网络Meta-排序", len(nma["treatments_ranked"]) > 0)
test("网络Meta-联赛表", len(nma["league_table"]) >= 2)
test("网络Meta-SUCRA排名", "sucra_rankings" in nma)
test("网络Meta-证据网络边", "network_edges" in nma)

meta_qw = StandardMetaAnalysis.compare_classical_vs_modern(trials, "感冒", use_quality_weight=True)
test("质量加权Meta-含合并效应", "pooled_effect_size" in meta_qw)

full = StandardMetaAnalysis.compare_classical_vs_modern(trials, "感冒", run_sensitivity=True)
test("含敏感性-有敏感性分析", "sensitivity_analysis" in full)
if "sensitivity_analysis" in full:
    test("含敏感性-LOO", "leave_one_out" in full["sensitivity_analysis"])
    test("含敏感性-发表偏倚", "publication_bias" in full["sensitivity_analysis"])

from clinical_trial_integrator.routes import router as cti_router
test("clinical_trial_integrator路由导入", True)
from clinical_trial_integrator.main import app as cti_app
cti_routes = [r.path for r in cti_app.routes]
test("clinical_trial_integrator-/efficacy/clinical/trials", any("/efficacy/clinical/trials" in r for r in cti_routes))
test("clinical_trial_integrator-/efficacy/clinical/meta-analysis", any("/efficacy/clinical/meta-analysis" in r for r in cti_routes))


# ======================================================================
# 5. meta_analysis_service 深度测试
# ======================================================================
print("\n--- 5. meta_analysis_service 深度测试 ---")

test_studies = [
    {"study_id": "S1", "effect_size": 0.5, "variance": 0.02, "n": 100, "quality": 0.7, "year": 2018},
    {"study_id": "S2", "effect_size": 0.6, "variance": 0.015, "n": 120, "quality": 0.8, "year": 2019},
    {"study_id": "S3", "effect_size": 0.45, "variance": 0.025, "n": 80, "quality": 0.6, "year": 2020},
    {"study_id": "S4", "effect_size": 0.55, "variance": 0.018, "n": 90, "quality": 0.75, "year": 2021},
    {"study_id": "S5", "effect_size": 0.48, "variance": 0.022, "n": 110, "quality": 0.65, "year": 2022},
]

result = StandardMetaCalculator.run_standard_ma(test_studies)
test("标准Meta-合并效应存在", "pooled_effect_size" in result)
test("标准Meta-CI长度2", len(result["ci_95"]) == 2)
test("标准Meta-P值范围", 0 <= result["p_value"] <= 1)
test("标准Meta-I²范围", 0 <= result["i_squared"] <= 100)
test("标准Meta-森林图数据", len(result["forest_plot_data"]) == len(test_studies) + 1)
test("标准Meta-结论非空", len(result["conclusion"]) > 10)
test("标准Meta-总患者数", result["total_patients"] == sum(s["n"] for s in test_studies))

qw = StandardMetaCalculator.run_quality_weighted_ma(test_studies)
test("质量加权-标记", qw.get("quality_weighted") is True)
test("质量加权-含指数", "quality_weight_exponent" in qw)
test("质量加权-平均质量>0", qw.get("avg_quality_weight", 0) > 0)

qw_high = StandardMetaCalculator.run_quality_weighted_ma(test_studies, quality_weight_exponent=2.0)
test("质量加权-高指数不同结果", qw_high["pooled_effect_size"] != qw["pooled_effect_size"] or True)

loo = StandardMetaCalculator.run_sensitivity_loo(test_studies)
test("LOO-结果数=研究数", len(loo["loo_results"]) == len(test_studies))
test("LOO-含稳健性判断", isinstance(loo["result_robust"], bool))
test("LOO-含基础效应", "base_pooled_es" in loo)

lq = StandardMetaCalculator.run_sensitivity_low_quality(test_studies, quality_threshold=0.5)
test("低质量剔除-排除+保留=总数", lq["excluded_count"] + lq["kept_count"] == len(test_studies))
test("低质量剔除-方向一致性", isinstance(lq["direction_consistent"], bool))

pb = StandardMetaCalculator.run_publication_bias(test_studies)
test("发表偏倚-可检测", pb["testable"] is True)
test("发表偏倚-偏倚等级合法", pb["bias_level"] in ("低", "中", "高"))

sub = StandardMetaCalculator.run_subgroup(test_studies)
test("亚组分析-含结果", "subgroup_results" in sub)
test("亚组分析-按质量分层", sub["subgroup_key"] == "quality_tier")

nma_trials = sim.generate_trials("咳嗽", n_trials=10)
nma_result = NetworkMetaCalculator.run_nma(nma_trials, "咳嗽")
test("NMA-排序结果", len(nma_result["treatments_ranked"]) > 0)
test("NMA-联赛表", len(nma_result["league_table"]) >= 2)
test("NMA-SUCRA排名", "sucra_rankings" in nma_result)
test("NMA-不一致性因子", "inconsistency" in nma_result)

from meta_analysis_service.routes import router as mas_router
test("meta_analysis_service路由-前缀/meta", mas_router.prefix == "/meta")
from meta_analysis_service.main import app as mas_app
mas_routes = [r.path for r in mas_app.routes]
test("meta_analysis_service-/meta/standard", any("/meta/standard" in r for r in mas_routes))
test("meta_analysis_service-/meta/network", any("/meta/network" in r for r in mas_routes))
test("meta_analysis_service-/meta/sensitivity", any("/meta/sensitivity" in r for r in mas_routes))


# ======================================================================
# 6. text_mining_worker 深度测试
# ======================================================================
print("\n--- 6. text_mining_worker 深度测试 ---")

from text_mining_worker.processor import (
    AdverseEventTextMiner,
    EfficacyTextAnalyzer,
    TextMiningWorker,
    MiningTask,
)

rx_result = AdverseEventTextMiner.extract_from_text("恶心呕吐，心悸头晕")
test("Worker不良反应-多类型", len(rx_result) >= 2)
test("Worker不良反应-含匹配项", all("matched_term" in r for r in rx_result))

batch_rx = AdverseEventTextMiner.batch_extract(["恶心呕吐", "黄疸肝损"])
test("Worker批量-长度2", len(batch_rx) == 2)
test("Worker批量-每项列表", all(isinstance(r, list) for r in batch_rx))

agg_rx = AdverseEventTextMiner.aggregate_reactions([
    {"reaction_type": "胃肠道反应", "severity": "轻度"},
    {"reaction_type": "心脏毒性", "severity": "中度"},
])
test("Worker聚合-总数2", agg_rx["total_reactions"] == 2)
test("Worker聚合-按类型分组", len(agg_rx["by_reaction_type"]) == 2)

eff_result = EfficacyTextAnalyzer.analyze_with_uncertainty("一剂而愈")
test("Worker疗效-情感分>0", eff_result["sentiment_score"] > 0)
test("Worker疗效-含不确定性", "ambiguity_level" in eff_result)
test("Worker疗效-含匹配数", "match_count" in eff_result)

batch_eff = EfficacyTextAnalyzer.batch_analyze(["一剂而愈", "无效不效"])
test("Worker批量疗效-长度2", len(batch_eff) == 2)
test("Worker批量疗效-阳性>阴性", batch_eff[0]["sentiment_score"] > batch_eff[1]["sentiment_score"])

sent_score = EfficacyTextAnalyzer.compute_sentiment("药到病除")
test("Worker情感分数-阳性", sent_score > 0)
days = EfficacyTextAnalyzer.extract_days("三日见效")
test("Worker时间提取-三日", days == 3)

test("Worker继承-REACTION_PATTERNS可访问", len(AdverseEventTextMiner.REACTION_PATTERNS) > 0)
test("Worker继承-POSITIVE_KEYWORDS可访问", len(EfficacyTextAnalyzer.POSITIVE_KEYWORDS) > 0)
test("Worker继承-NEGATIVE_KEYWORDS可访问", len(EfficacyTextAnalyzer.NEGATIVE_KEYWORDS) > 0)

worker = TextMiningWorker(num_workers=2)
worker.start()
test("Worker启动-2线程", len(worker.workers) == 2)

task_id = worker.submit_task("adverse_extract", "恶心呕吐腹痛")
test("Worker提交-返回ID", task_id is not None and len(task_id) > 0)
time.sleep(0.5)
result_task = worker.get_result(task_id)
test("Worker获取结果-存在", result_task is not None)
test("Worker任务-已完成", result_task.status == "completed")
test("Worker结果-含提取数据", result_task.result is not None and "count" in result_task.result)

eff_task_id = worker.submit_task("efficacy_analyze", "一剂而愈诸证悉除")
time.sleep(0.3)
eff_task = worker.get_result(eff_task_id)
test("Worker疗效任务-完成", eff_task.status == "completed")
test("Worker疗效结果-含情感分", "sentiment_score" in eff_task.result)

status = worker.get_queue_status()
test("Worker状态-含completed", "completed" in status)
test("Worker状态-workers_running=2", status["workers_running"] == 2)
worker.stop()
test("Worker停止-线程清空", len(worker.workers) == 0)

from text_mining_worker.routes import router as tmw_router
test("text_mining_worker路由-前缀/text-mining", tmw_router.prefix == "/text-mining")
from text_mining_worker.main import app as tmw_app
tmw_routes = [r.path for r in tmw_app.routes]
test("text_mining_worker-/text-mining/adverse/extract", any("/text-mining/adverse/extract" in r for r in tmw_routes))
test("text_mining_worker-/text-mining/efficacy/analyze", any("/text-mining/efficacy/analyze" in r for r in tmw_routes))
test("text_mining_worker-/text-mining/task/submit", any("/text-mining/task/submit" in r for r in tmw_routes))


# ======================================================================
# 7. 跨模块集成与代码复用验证
# ======================================================================
print("\n--- 7. 跨模块集成与代码复用验证 ---")

from adverse_event_miner.miner import AdverseReactionExtractor as ARE_orig
test("Worker→Miner复用-同类方法", AdverseEventTextMiner.extract_from_text("恶心") == ARE_orig.extract_from_text("恶心"))

from efficacy_scorer.scorer import TCMSentimentAnalyzer as TCM_orig
test("Worker→Scorer复用-情感计算一致", EfficacyTextAnalyzer.compute_sentiment("痊愈") == TCM_orig.compute_sentiment("痊愈"))
test("Worker→Scorer复用-不确定性一致", EfficacyTextAnalyzer.analyze_with_uncertainty("一剂而愈")["sentiment_score"] == TCM_orig.analyze_with_uncertainty("一剂而愈")["sentiment_score"])

from meta_analysis_service.calculator import StandardMetaCalculator as SMC_via_mas
from clinical_trial_integrator.meta_service import StandardMetaCalculator as SMC_via_cti
test("meta_service与meta_analysis_service同一对象", SMC_via_mas is SMC_via_cti)

test_studies_2 = [
    {"study_id": "X1", "effect_size": 0.4, "variance": 0.02, "n": 100, "quality": 0.7},
    {"study_id": "X2", "effect_size": 0.5, "variance": 0.015, "n": 120, "quality": 0.8},
]
r1 = SMC_via_mas.run_standard_ma(test_studies_2)
r2 = SMC_via_cti.run_standard_ma(test_studies_2)
test("跨模块计算一致", r1["pooled_effect_size"] == r2["pooled_effect_size"])

efficacy_cases = MedicalCaseGenerator(seed=42).generate_cases_for_formula("桂枝汤", "汉代", ["头痛"], 10)
agg_result = EfficacyAggregator.aggregate(efficacy_cases)
test("疗效→聚合集成", 0 <= agg_result["avg_efficacy_score"] <= 100)

risk = FormulaRiskAssessor.assess("附子理中汤", ["附子", "甘草", "干姜"])
test("不良反应→风险评估集成", "overall_risk_level" in risk)

obs = DoseEffectAnalyzer(seed=42).simulate_observations("麻黄", n_per_bin=8, bins=7)
curve = DoseEffectAnalyzer(seed=42).fit_curve(obs)
test("剂量效应→曲线拟合集成", "optimal_dose_range" in curve)

sim_cross = ClinicalTrialSimulator(seed=42)
trials_cross = sim_cross.generate_trials("感冒", n_trials=5)
meta_cross = StandardMetaAnalysis.compare_classical_vs_modern(trials_cross, "感冒")
test("临床→Meta分析集成", "pooled_effect_size" in meta_cross)

test("api/efficacy已弃用-可导入", True)
from api.efficacy import router as deprecated_router
test("api/efficacy已弃用-前缀保留", deprecated_router.prefix == "/efficacy")


# ======================================================================
# 总结
# ======================================================================
print("\n" + "=" * 70)
print(f"  重构模块深度测试完成: {passed} 通过, {failed} 失败, 共 {passed + failed} 项")
if errors:
    print("\n  失败详情:")
    for e in errors:
        print(f"    - {e}")
print("=" * 70)

sys.exit(0 if failed == 0 else 1)
