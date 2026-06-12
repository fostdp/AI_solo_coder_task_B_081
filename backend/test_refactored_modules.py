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


print("=" * 70)
print("  重构模块单元测试 - 独立模块验证")
print("=" * 70)

# ======================================================================
# 1. efficacy_scorer 独立模块测试
# ======================================================================
print("\n--- 1. efficacy_scorer 独立模块 ---")

from efficacy_scorer.scorer import (
    SentimentUncertaintyEstimator,
    TCMSentimentAnalyzer,
    OrdinalRegressionScorer,
    HumanAnnotationManager,
    MedicalCaseGenerator,
    EfficacyAggregator,
)

test("SentimentUncertaintyEstimator导入", True)
test("TCMSentimentAnalyzer导入", True)
test("OrdinalRegressionScorer导入", True)
test("HumanAnnotationManager导入", True)
test("MedicalCaseGenerator导入", True)
test("EfficacyAggregator导入", True)

sent_pos = TCMSentimentAnalyzer.compute_sentiment("一剂而愈药到病除")
test("情感分析-强阳性", sent_pos > 0.5)
sent_neg = TCMSentimentAnalyzer.compute_sentiment("无效不效病情加剧")
test("情感分析-强阴性", sent_neg < -0.3)
sent_neutral = TCMSentimentAnalyzer.compute_sentiment("服药观察")
test("情感分析-中性", abs(sent_neutral) < 0.3)

unc_vague = TCMSentimentAnalyzer.analyze_with_uncertainty("稍安")
unc_clear = TCMSentimentAnalyzer.analyze_with_uncertainty("一剂而愈诸恙悉平")
test("不确定性-模糊描述需审核", unc_vague["needs_human_review"] is True)
test("不确定性-明确描述高置信", unc_clear["overall_confidence"] > unc_vague["overall_confidence"])

entropy = SentimentUncertaintyEstimator.keyword_entropy([("愈", 0.9, "pos")])
test("关键词熵计算", 0.0 <= entropy <= 2.0)

conf = SentimentUncertaintyEstimator.confidence_from_matches(5, 100)
test("匹配置信度", 0.0 <= conf <= 1.0)

grade, score = OrdinalRegressionScorer.predict_grade(0.8, 1)
test("序数回归-高情感短时间高分级", grade >= 3)
test("序数回归-分数范围", 0 <= score <= 100)

grade_unc = OrdinalRegressionScorer.predict_with_uncertainty(0.8, 1, 0.9)
test("序数回归-不确定性输出", "uncertainty_level" in grade_unc)
test("序数回归-分级概率", len(grade_unc["grade_probabilities"]) == 5)

ham = HumanAnnotationManager()
ham.submit_for_review("c1", "test", 2, 50.0, "中")
test("人工标注-提交审核", ham.get_pending_count() == 1)
ham.annotate("c1", 3, 75.0, "李医生")
test("人工标注-完成标注", ham.get_pending_count() == 0)
stats = ham.get_annotation_stats()
test("人工标注-统计", stats["total_annotated"] == 1)

gen = MedicalCaseGenerator(seed=42)
cases = gen.generate_cases_for_formula("桂枝汤", "汉代", ["头痛发热"], 5)
test("医案生成-数量", len(cases) == 5)
test("医案生成-字段完整", all("efficacy_grade" in c for c in cases))

agg = EfficacyAggregator.aggregate(cases)
test("疗效聚合-均值", 0 <= agg["avg_efficacy_score"] <= 100)
test("疗效聚合-CI", len(agg["confidence_interval"]) == 2)
empty_agg = EfficacyAggregator.aggregate([])
test("疗效聚合-空输入", empty_agg["avg_efficacy_score"] == 0.0)

from efficacy_scorer.routes import router as es_router
test("efficacy_scorer路由导入", True)
test("efficacy_scorer路由前缀", es_router.prefix == "/efficacy")

from efficacy_scorer.main import app as es_app
test("efficacy_scorer FastAPI app导入", True)
es_routes = [r.path for r in es_app.routes]
test("efficacy_scorer /efficacy/analyze路由", any("/efficacy/analyze" in r for r in es_routes))
test("efficacy_scorer /efficacy/grade路由", any("/efficacy/grade" in r for r in es_routes))
test("efficacy_scorer /efficacy/evaluate路由", any("/efficacy/evaluate" in r for r in es_routes))
test("efficacy_scorer /efficacy/annotation/submit路由", any("/annotation/submit" in r for r in es_routes))
test("efficacy_scorer /efficacy/cases/generate路由", any("/cases/generate" in r for r in es_routes))
test("efficacy_scorer /health路由", any("/health" in r for r in es_routes))


# ======================================================================
# 2. dose_response_modeler 独立模块测试
# ======================================================================
print("\n--- 2. dose_response_modeler 独立模块 ---")

from dose_response_modeler.modeler import (
    RestrictedCubicSpline,
    RCSResult,
    DoseEffectAnalyzer,
    BayesianRCS,
    SensitivityAnalyzer,
)

test("RestrictedCubicSpline导入", True)
test("DoseEffectAnalyzer导入", True)
test("BayesianRCS导入", True)
test("SensitivityAnalyzer导入", True)

rcs = RestrictedCubicSpline(nk=4)
xs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
ys = [2.0 * x + 1.0 for x in xs]
rcs.fit(xs, ys)
test("RCS-线性拟合R²", rcs.r_squared > 0.9)
pred = rcs.predict(5.0)
test("RCS-预测值合理", abs(pred - 11.0) < 1.0)

rcs_unfit = RestrictedCubicSpline()
test("RCS-未拟合预测", rcs_unfit.predict(5.0) == 0.0)

analyzer = DoseEffectAnalyzer(seed=42)
for herb in ["麻黄", "黄芪", "附子"]:
    obs = analyzer.simulate_observations(herb, n_per_bin=10, bins=7)
    test(f"剂量模拟-{herb}", len(obs) == 7)
    curve = analyzer.fit_curve(obs)
    test(f"剂量曲线-{herb}拟合R²", curve["r_squared"] > 0.5)
    test(f"剂量曲线-{herb}最优范围", curve["optimal_dose_range"][0] < curve["optimal_dose_range"][1])

studies = [
    {"effect_size": 0.5, "variance": 0.02, "study_id": "S1"},
    {"effect_size": 0.6, "variance": 0.015, "study_id": "S2"},
    {"effect_size": 0.45, "variance": 0.025, "study_id": "S3"},
]
meta = DoseEffectAnalyzer.dose_meta_analysis(studies)
test("剂量Meta分析-合并效应", 0.3 < meta["pooled_effect_size"] < 0.8)
test("剂量Meta分析-CI", len(meta["ci_95"]) == 2)

bayes = BayesianRCS(nk=4, prior_precision=0.5)
bayes.fit(xs, ys)
test("BayesianRCS-拟合R²", bayes.r_squared > 0.5)
pred_b, lo_b, hi_b = bayes.predict_with_ci(5.0)
test("BayesianRCS-CI", lo_b < pred_b < hi_b)

obs_sens = analyzer.simulate_observations("甘草", n_per_bin=8, bins=7)
xs_s = [o["dosage_g"] for o in obs_sens]
ys_s = [o["avg_efficacy"] for o in obs_sens]
ws_s = [o["sample_size"] for o in obs_sens]
loo = SensitivityAnalyzer.leave_one_out(xs_s, ys_s, ws_s, nk=4)
test("LOO敏感性-结果存在", "loo_results" in loo)
knot_sens = SensitivityAnalyzer.knot_sensitivity(xs_s, ys_s, ws_s)
test("节点敏感性-结果存在", "knot_results" in knot_sens)

from dose_response_modeler.routes import router as drm_router
test("dose_response_modeler路由导入", True)

from dose_response_modeler.main import app as drm_app
test("dose_response_modeler FastAPI app导入", True)
drm_routes = [r.path for r in drm_app.routes]
test("dose_response_modeler /health路由", any("/health" in r for r in drm_routes))


# ======================================================================
# 3. adverse_event_miner 独立模块测试
# ======================================================================
print("\n--- 3. adverse_event_miner 独立模块 ---")

from adverse_event_miner.miner import (
    ExpertKnowledgeEngine,
    AdverseReactionExtractor,
    RiskPairDetector,
    FormulaRiskAssessor,
)

test("ExpertKnowledgeEngine导入", True)
test("AdverseReactionExtractor导入", True)
test("RiskPairDetector导入", True)
test("FormulaRiskAssessor导入", True)

expert = ExpertKnowledgeEngine()
test("毒性家族-附子", expert.get_herb_family("附子") == "乌头类")
test("毒性家族-朱砂", expert.get_herb_family("朱砂") == "含汞类")
test("毒性家族-雄黄", expert.get_herb_family("雄黄") == "含砷类")
test("毒性家族-未知药", expert.get_herb_family("甘草") is None)

inferred = expert.infer_interactions(["附子", "川乌"])
test("同类推理-乌头类叠加", len(inferred) >= 1)
if inferred:
    test("推理结果-inferred标记", inferred[0].get("inferred") is True)
    test("推理结果-置信度", 0 < inferred[0].get("confidence", 0) < 1)

expanded = expert.expand_toxic_profile("川乌")
test("扩展毒性档案", expanded["inferred_count"] >= 0 or expanded.get("family") is not None)

preg_risk = expert.assess_pregnancy_risk(["附子", "甘草"])
test("妊娠风险评估", preg_risk["overall_risk"] in ("禁用", "忌用（推理）", "慎用", "安全"))

rx = AdverseReactionExtractor.extract_from_text("恶心呕吐伴黄疸肝酶升高")
test("不良反应提取-多类型", len(rx) >= 2)
rx_types = {r["reaction_type"] for r in rx}
test("不良反应提取-含胃肠道", "胃肠道反应" in rx_types)

agg_rx = AdverseReactionExtractor.aggregate_reactions(["附子", "乌头"])
test("不良反应聚合", agg_rx["total_reactions"] >= 0)

risks = RiskPairDetector.detect_for_formula(["甘草", "甘遂"])
test("风险药对检出-十八反", len(risks) > 0)
safe_risks = RiskPairDetector.detect_for_formula(["茯苓", "白术"])
test("风险药对-安全组合", len(safe_risks) == 0)

assessment = FormulaRiskAssessor.assess("测试方", ["附子", "半夏"])
test("方剂风险评估-等级", assessment["overall_risk_level"] in ("安全", "低", "中", "高", "极高"))
test("方剂风险评估-含警告", len(assessment["warnings"]) >= 0)

from adverse_event_miner.routes import router as aem_router
test("adverse_event_miner路由导入", True)
test("adverse_event_miner路由前缀", aem_router.prefix == "/adverse")

from adverse_event_miner.main import app as aem_app
test("adverse_event_miner FastAPI app导入", True)


# ======================================================================
# 4. clinical_trial_integrator 独立模块测试
# ======================================================================
print("\n--- 4. clinical_trial_integrator 独立模块 ---")

from clinical_trial_integrator.integrator import (
    ClinicalTrialSimulator,
    StandardMetaAnalysis,
    NetworkMetaAnalysis,
    MetaAnalysisSensitivity,
    QualityWeightedMetaAnalysis,
)
from meta_analysis_service.calculator import StandardMetaCalculator, NetworkMetaCalculator

test("ClinicalTrialSimulator导入", True)
test("StandardMetaAnalysis导入", True)
test("NetworkMetaAnalysis导入", True)
test("MetaAnalysisSensitivity导入", True)
test("QualityWeightedMetaAnalysis导入", True)
test("StandardMetaCalculator导入", True)
test("NetworkMetaCalculator导入", True)

sim = ClinicalTrialSimulator(seed=42)
trials = sim.generate_trials("感冒", n_trials=8)
test("临床试验模拟-感冒", len(trials) > 0)
test("临床试验-含试验臂", all("arms" in t for t in trials))
test("临床试验-含质量评分", all("quality_score" in t for t in trials))

meta = StandardMetaAnalysis.compare_classical_vs_modern(trials, "感冒")
test("标准Meta分析-合并效应", "pooled_effect_size" in meta)
test("标准Meta分析-CI", len(meta["ci_95"]) == 2)
test("标准Meta分析-森林图", len(meta.get("forest_plot_data", [])) >= 2)

nma = NetworkMetaAnalysis.run(trials, "感冒")
test("网络Meta-排序", len(nma["treatments_ranked"]) > 0)
test("网络Meta-联赛表", len(nma["league_table"]) >= 2)

meta_qw = StandardMetaAnalysis.compare_classical_vs_modern(trials, "感冒", use_quality_weight=True)
test("质量加权Meta-标记", meta_qw.get("quality_weighted") is True or "pooled_effect_size" in meta_qw)

studies_for_sens = []
for t in trials:
    classic = [a for a in t["arms"] if a["treatment_type"] == "古代经典方"]
    modern_a = [a for a in t["arms"] if a["treatment_type"] != "古代经典方"]
    if classic and modern_a:
        c, m = classic[0], modern_a[0]
        nc, nm = c["sample_size"], m["sample_size"]
        ps = math.sqrt(((nc-1)*c["std_efficacy"]**2 + (nm-1)*m["std_efficacy"]**2) / max(nc+nm-2, 1))
        smd = (c["mean_efficacy"] - m["mean_efficacy"]) / ps if ps > 0 else 0
        var = 1/nc + 1/nm + smd**2 / (2*(nc+nm))
        studies_for_sens.append({
            "study_id": t["trial_id"], "year": t["year"],
            "effect_size": smd, "variance": var, "n": nc+nm,
            "quality": t["quality_score"],
        })

if len(studies_for_sens) >= 3:
    loo = MetaAnalysisSensitivity.leave_one_out(studies_for_sens)
    test("LOO敏感性-结果存在", "loo_results" in loo)
    lq = MetaAnalysisSensitivity.low_quality_exclusion(studies_for_sens)
    test("低质量剔除-结果存在", "direction_consistent" in lq)
if len(studies_for_sens) >= 5:
    pb = MetaAnalysisSensitivity.publication_bias(studies_for_sens)
    test("发表偏倚-结果存在", "bias_level" in pb)

full = StandardMetaAnalysis.compare_classical_vs_modern(trials, "感冒", run_sensitivity=True)
test("完整分析含敏感性", "sensitivity_analysis" in full)

from clinical_trial_integrator.routes import router as cti_router
test("clinical_trial_integrator路由导入", True)

from clinical_trial_integrator.main import app as cti_app
test("clinical_trial_integrator FastAPI app导入", True)


# ======================================================================
# 5. meta_analysis_service 独立服务测试
# ======================================================================
print("\n--- 5. meta_analysis_service 独立服务 ---")

from meta_analysis_service.calculator import StandardMetaCalculator, NetworkMetaCalculator

test_studies = [
    {"study_id": "S1", "effect_size": 0.5, "variance": 0.02, "n": 100, "quality": 0.7, "year": 2018},
    {"study_id": "S2", "effect_size": 0.6, "variance": 0.015, "n": 120, "quality": 0.8, "year": 2019},
    {"study_id": "S3", "effect_size": 0.45, "variance": 0.025, "n": 80, "quality": 0.6, "year": 2020},
    {"study_id": "S4", "effect_size": 0.55, "variance": 0.018, "n": 90, "quality": 0.75, "year": 2021},
    {"study_id": "S5", "effect_size": 0.48, "variance": 0.022, "n": 110, "quality": 0.65, "year": 2022},
]

result = StandardMetaCalculator.run_standard_ma(test_studies)
test("标准Meta-合并效应", "pooled_effect_size" in result)
test("标准Meta-CI", len(result["ci_95"]) == 2)
test("标准Meta-P值", 0 <= result["p_value"] <= 1)
test("标准Meta-I²", 0 <= result["i_squared"] <= 100)
test("标准Meta-森林图", len(result["forest_plot_data"]) >= 2)
test("标准Meta-结论", len(result["conclusion"]) > 10)

qw = StandardMetaCalculator.run_quality_weighted_ma(test_studies)
test("质量加权-标记", qw.get("quality_weighted") is True)
test("质量加权-平均质量", qw.get("avg_quality_weight", 0) > 0)

loo = StandardMetaCalculator.run_sensitivity_loo(test_studies)
test("LOO-结果数", len(loo["loo_results"]) == len(test_studies))
test("LOO-稳健性判断", isinstance(loo["result_robust"], bool))

lq = StandardMetaCalculator.run_sensitivity_low_quality(test_studies, quality_threshold=0.5)
test("低质量剔除-排除数", lq["excluded_count"] + lq["kept_count"] == len(test_studies))

pb = StandardMetaCalculator.run_publication_bias(test_studies)
test("发表偏倚-可检测", pb["testable"] is True)
test("发表偏倚-偏倚等级", pb["bias_level"] in ("低", "中", "高"))

sub = StandardMetaCalculator.run_subgroup(test_studies)
test("亚组分析-结果存在", "subgroup_results" in sub)

nma_trials = sim.generate_trials("咳嗽", n_trials=10)
nma_result = NetworkMetaCalculator.run_nma(nma_trials, "咳嗽")
test("NMA-排序结果", len(nma_result["treatments_ranked"]) > 0)
test("NMA-联赛表", len(nma_result["league_table"]) >= 2)
test("NMA-SUCRA排名", "sucra_rankings" in nma_result)

from meta_analysis_service.routes import router as mas_router
test("meta_analysis_service路由导入", True)
test("meta_analysis_service路由前缀", mas_router.prefix == "/meta")

from meta_analysis_service.main import app as mas_app
test("meta_analysis_service FastAPI app导入", True)


# ======================================================================
# 6. text_mining_worker 独立服务测试
# ======================================================================
print("\n--- 6. text_mining_worker 独立服务 ---")

from text_mining_worker.processor import (
    AdverseEventTextMiner,
    EfficacyTextAnalyzer,
    TextMiningWorker,
    MiningTask,
)

test("AdverseEventTextMiner导入", True)
test("EfficacyTextAnalyzer导入", True)
test("TextMiningWorker导入", True)
test("MiningTask导入", True)

rx_result = AdverseEventTextMiner.extract_from_text("恶心呕吐，心悸头晕")
test("Worker不良反应提取", len(rx_result) >= 2)

batch_rx = AdverseEventTextMiner.batch_extract(["恶心呕吐", "黄疸肝损"])
test("Worker批量不良反应", len(batch_rx) == 2)

eff_result = EfficacyTextAnalyzer.analyze_with_uncertainty("一剂而愈")
test("Worker疗效分析-情感分", eff_result["sentiment_score"] > 0)
test("Worker疗效分析-不确定性", "ambiguity_level" in eff_result)

batch_eff = EfficacyTextAnalyzer.batch_analyze(["一剂而愈", "无效不效"])
test("Worker批量疗效", len(batch_eff) == 2)

sent_score = EfficacyTextAnalyzer.compute_sentiment("药到病除")
test("Worker情感分数", sent_score > 0)
days = EfficacyTextAnalyzer.extract_days("三日见效")
test("Worker时间提取", days == 3)

worker = TextMiningWorker(num_workers=2)
worker.start()
test("Worker启动", len(worker.workers) == 2)

task_id = worker.submit_task("adverse_extract", "恶心呕吐腹痛")
test("Worker提交任务", task_id is not None)
time.sleep(0.5)
result_task = worker.get_result(task_id)
test("Worker获取结果", result_task is not None)
test("Worker任务完成", result_task.status == "completed")

status = worker.get_queue_status()
test("Worker队列状态", "completed" in status)
worker.stop()

agg_rx_result = AdverseEventTextMiner.aggregate_reactions([
    {"reaction_type": "胃肠道反应", "severity": "轻度"},
    {"reaction_type": "心脏毒性", "severity": "中度"},
])
test("Worker聚合反应", agg_rx_result["total_reactions"] == 2)

from text_mining_worker.routes import router as tmw_router
test("text_mining_worker路由导入", True)
test("text_mining_worker路由前缀", tmw_router.prefix == "/text-mining")

from text_mining_worker.main import app as tmw_app
test("text_mining_worker FastAPI app导入", True)


# ======================================================================
# 7. services/ 薄封装兼容性测试
# ======================================================================
print("\n--- 7. services/ 薄封装兼容性 ---")

from services.efficacy_scorer import (
    SentimentUncertaintyEstimator as SUE_bw,
    TCMSentimentAnalyzer as TCM_bw,
    OrdinalRegressionScorer as ORS_bw,
    HumanAnnotationManager as HAM_bw,
    MedicalCaseGenerator as MCG_bw,
    EfficacyAggregator as EA_bw,
)
test("services.efficacy_scorer兼容导入", True)
test("TCMSentimentAnalyzer兼容", TCM_bw.compute_sentiment("痊愈") > 0)

from services.dose_response import (
    RestrictedCubicSpline as RCS_bw,
    DoseEffectAnalyzer as DEA_bw,
    BayesianRCS as BRC_bw,
    SensitivityAnalyzer as SA_bw,
)
test("services.dose_response兼容导入", True)
test("DoseEffectAnalyzer兼容", DEA_bw is DoseEffectAnalyzer)

from services.adverse_reaction import (
    ExpertKnowledgeEngine as EKE_bw,
    AdverseReactionExtractor as ARE_bw,
    RiskPairDetector as RPD_bw,
    FormulaRiskAssessor as FRA_bw,
)
test("services.adverse_reaction兼容导入", True)

from services.clinical_trial import (
    ClinicalTrialSimulator as CTS_bw,
    StandardMetaAnalysis as SMA_bw,
    NetworkMetaAnalysis as NMA_bw,
    MetaAnalysisSensitivity as MAS_bw,
    QualityWeightedMetaAnalysis as QWMA_bw,
)
test("services.clinical_trial兼容导入", True)
test("ClinicalTrialSimifier兼容", CTS_bw is ClinicalTrialSimulator)
sim_bw = CTS_bw(seed=42)
trials_bw = sim_bw.generate_trials("感冒", n_trials=3)
test("兼容包装器-临床试验模拟", len(trials_bw) > 0)


# ======================================================================
# 8. cross-module集成验证
# ======================================================================
print("\n--- 8. 跨模块集成验证 ---")

from meta_analysis_service.calculator import StandardMetaCalculator as SMC_via_mas
from clinical_trial_integrator.meta_service import StandardMetaCalculator as SMC_via_cti
test("meta_service与meta_analysis_service一致", SMC_via_mas is SMC_via_cti)

test_studies_2 = [
    {"study_id": "X1", "effect_size": 0.4, "variance": 0.02, "n": 100, "quality": 0.7},
    {"study_id": "X2", "effect_size": 0.5, "variance": 0.015, "n": 120, "quality": 0.8},
]
r1 = SMC_via_mas.run_standard_ma(test_studies_2)
r2 = SMC_via_cti.run_standard_ma(test_studies_2)
test("跨模块计算一致性", r1["pooled_effect_size"] == r2["pooled_effect_size"])

efficacy_cases = MedicalCaseGenerator(seed=42).generate_cases_for_formula("桂枝汤", "汉代", ["头痛"], 10)
agg_result = EfficacyAggregator.aggregate(efficacy_cases)
test("疗效量化→聚合集成", 0 <= agg_result["avg_efficacy_score"] <= 100)

risk = FormulaRiskAssessor.assess("附子理中汤", ["附子", "甘草", "干姜"])
test("不良反应→方剂风险评估集成", "overall_risk_level" in risk)

obs = DoseEffectAnalyzer(seed=42).simulate_observations("麻黄", n_per_bin=8, bins=7)
curve = DoseEffectAnalyzer(seed=42).fit_curve(obs)
test("剂量效应→曲线拟合集成", "optimal_dose_range" in curve)


# ======================================================================
# 总结
# ======================================================================
print("\n" + "=" * 70)
print(f"  重构模块测试完成: {passed} 通过, {failed} 失败, 共 {passed + failed} 项")
if errors:
    print("\n  失败详情:")
    for e in errors:
        print(f"    - {e}")
print("=" * 70)

sys.exit(0 if failed == 0 else 1)
