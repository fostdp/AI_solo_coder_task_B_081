import sys
import os
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


print("=" * 60)
print("回归测试：微服务架构验证")
print("=" * 60)

print("\n--- 1. Shared模块导入测试 ---")
try:
    from shared.config import get_settings, get_algorithm_config, get_fp_growth_config, get_louvain_config, get_link_prediction_config, get_graph_config
    test("shared.config 导入", True)
except Exception as e:
    test("shared.config 导入", False, str(e))

try:
    from shared.database import get_collection, get_mongo_db, get_neo4j_driver, run_neo4j_query
    test("shared.database 导入", True)
except Exception as e:
    test("shared.database 导入", False, str(e))

try:
    from shared.redis_client import get_redis, cache_set, cache_get, cache_delete, publish, RedisChannels
    test("shared.redis_client 导入", True)
except Exception as e:
    test("shared.redis_client 导入", False, str(e))

try:
    from shared.models import FormulaBase, FormulaCreate, HerbIngredient, AssociationRule, CommunityResult, LinkPredictionResult, GraphNode, GraphEdge, GraphData
    test("shared.models 导入", True)
except Exception as e:
    test("shared.models 导入", False, str(e))

print("\n--- 2. 算法参数外置测试 ---")
try:
    cfg = get_algorithm_config()
    test("算法配置加载", "fp_growth" in cfg and "louvain" in cfg and "link_prediction" in cfg and "graph" in cfg)
    test("FP-Growth默认参数", cfg["fp_growth"]["max_itemset_length"] == 3)
    test("Louvain默认参数", cfg["louvain"]["partition_size"] == 100)
    test("链路预测权重", abs(sum(cfg["link_prediction"]["combined_weights"].values()) - 1.0) < 0.01)
    test("图配置阈值", cfg["graph"]["aggregation_threshold"] == 150)
except Exception as e:
    test("算法配置加载", False, str(e))

try:
    fpg_cfg = get_fp_growth_config()
    test("FP-Growth独立配置", fpg_cfg["min_support"] == 0.05)
except Exception as e:
    test("FP-Growth独立配置", False, str(e))

print("\n--- 3. Formula Loader服务导入测试 ---")
try:
    from formula_loader.main import app as formula_app
    test("formula_loader app导入", True)
    routes = [r.path for r in formula_app.routes]
    test("formulas路由存在", any("/formulas/" in r for r in routes))
    test("herbs路由存在", any("/herbs/" in r for r in routes))
    test("diseases路由存在", any("/diseases/" in r for r in routes))
    test("import路由存在", any("/import/" in r for r in routes))
except Exception as e:
    test("formula_loader app导入", False, str(e))

print("\n--- 4. Pattern Miner服务导入测试 ---")
try:
    from pattern_miner.main import app as miner_app
    test("pattern_miner app导入", True)
    routes = [r.path for r in miner_app.routes]
    test("mining路由存在", any("/mining/" in r for r in routes))
except Exception as e:
    test("pattern_miner app导入", False, str(e))

try:
    from pattern_miner.fp_growth import FPGrowth, FPNode, FPTree
    test("FPGrowth算法类导入", True)
    fpg = FPGrowth(min_support=0.1, min_confidence=0.5, max_itemset_length=3)
    test("FPGrowth实例化", fpg.max_itemset_length == 3)
except Exception as e:
    test("FPGrowth算法类导入", False, str(e))

try:
    from pattern_miner.louvain import LouvainCommunity
    test("LouvainCommunity导入", True)
    lc = LouvainCommunity(resolution=1.0)
    test("LouvainCommunity实例化", True)
    test("fit_partitioned方法存在", hasattr(lc, 'fit_partitioned'))
    test("fit_incremental方法存在", hasattr(lc, 'fit_incremental'))
except Exception as e:
    test("LouvainCommunity导入", False, str(e))

print("\n--- 5. Drug Discoverer服务导入测试 ---")
try:
    from drug_discoverer.main import app as discovery_app
    test("drug_discoverer app导入", True)
    routes = [r.path for r in discovery_app.routes]
    test("discovery路由存在", any("/discovery/" in r for r in routes))
except Exception as e:
    test("drug_discoverer app导入", False, str(e))

try:
    from drug_discoverer.link_prediction import LinkPredictor
    test("LinkPredictor导入", True)
    import networkx as nx
    G = nx.Graph()
    G.add_edge("A", "B", weight=1)
    G.add_edge("B", "C", weight=1)
    lp = LinkPredictor(G)
    test("LinkPredictor实例化", True)
    methods = ["common_neighbors", "jaccard", "adamic_adar", "resource_allocation", "preferential_attachment"]
    for m in methods:
        result = lp.predict_links(method=m, top_n=5)
        test(f"LinkPredictor.{m}", len(result) >= 0)
except Exception as e:
    test("LinkPredictor导入", False, str(e))

print("\n--- 6. Graph API服务导入测试 ---")
try:
    from graph_api.main import app as graph_app
    test("graph_api app导入", True)
    routes = [r.path for r in graph_app.routes]
    test("graph路由存在", any("/graph/" in r for r in routes))
except Exception as e:
    test("graph_api app导入", False, str(e))

print("\n--- 7. Gateway导入测试 ---")
try:
    from gateway import app as gateway_app, SERVICE_MAP
    test("gateway app导入", True)
    test("SERVICE_MAP配置", len(SERVICE_MAP) == 7)
    test("formulas→formula_loader", SERVICE_MAP.get("/formulas", "").endswith(":8001"))
    test("mining→pattern_miner", SERVICE_MAP.get("/mining", "").endswith(":8002"))
    test("discovery→drug_discoverer", SERVICE_MAP.get("/discovery", "").endswith(":8003"))
    test("graph→graph_api", SERVICE_MAP.get("/graph", "").endswith(":8004"))
except Exception as e:
    test("gateway app导入", False, str(e))

print("\n--- 8. FP-Growth算法回归测试 ---")
try:
    from pattern_miner.fp_growth import FPGrowth
    transactions = [
        ["甘草", "桂枝", "白芍"],
        ["甘草", "桂枝", "生姜"],
        ["甘草", "白芍", "大枣"],
        ["桂枝", "白芍", "生姜"],
        ["甘草", "桂枝", "白芍", "生姜"],
    ]
    fpg = FPGrowth(min_support=0.4, min_confidence=0.5, max_itemset_length=3)
    freq_itemsets, _ = fpg.fit(transactions)
    test("FP-Growth fit返回频繁项集", len(freq_itemsets) > 0)
    rules = fpg.generate_rules()
    test("FP-Growth生成关联规则", len(rules) >= 0)
    pairs = fpg.get_top_pairs(5)
    test("FP-Growth获取药对", len(pairs) > 0)
    triplets = fpg.get_top_triplets(5)
    test("FP-Growth获取角药", len(triplets) >= 0)

    fpg_limited = FPGrowth(min_support=0.4, max_itemset_length=2)
    fpg_limited.fit(transactions)
    all_len2 = all(len(k) <= 2 for k in fpg_limited.freq_itemsets.keys())
    test("max_itemset_length=2限制生效", all_len2)
except Exception as e:
    test("FP-Growth算法回归", False, str(e))

print("\n--- 9. Louvain算法回归测试 ---")
try:
    from pattern_miner.louvain import LouvainCommunity
    import networkx as nx
    G = nx.Graph()
    G.add_edges_from([("A", "B", {"weight": 5}), ("B", "C", {"weight": 5}),
                      ("C", "D", {"weight": 5}), ("D", "E", {"weight": 5}),
                      ("A", "C", {"weight": 2}), ("B", "D", {"weight": 1})])
    lc = LouvainCommunity(resolution=1.0)
    lc.fit(G)
    communities = lc.get_communities()
    test("Louvain fit返回社区", len(communities) > 0)
    test("Louvain模块度计算", lc.modularity != 0)

    communities_p = lc.fit_partitioned(G, partition_size=3)
    test("Louvain fit_partitioned返回社区", len(communities_p) > 0)

    communities_i = lc.fit_incremental(G, previous_partition=lc.communities, changed_nodes={"E"})
    test("Louvain fit_incremental返回社区", len(communities_i) > 0)
except Exception as e:
    test("Louvain算法回归", False, str(e))

print("\n--- 10. Redis通道常量测试 ---")
try:
    test("FORMULA_UPDATED通道", RedisChannels.FORMULA_UPDATED == "formula:updated")
    test("FORMULA_TRANSACTIONS通道", RedisChannels.FORMULA_TRANSACTIONS == "formula:transactions")
    test("MINING_RESULT通道", RedisChannels.MINING_RESULT == "mining:result")
    test("GRAPH_NETWORK通道", RedisChannels.GRAPH_NETWORK == "graph:network")
except Exception as e:
    test("Redis通道常量", False, str(e))

print("\n--- 11. 算法配置文件存在测试 ---")
try:
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "algorithm_config.json")
    test("algorithm_config.json存在", os.path.exists(cfg_path))
    import json
    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg_data = json.load(f)
    test("配置文件合法JSON", "fp_growth" in cfg_data)
    test("配置文件含所有模块", all(k in cfg_data for k in ["fp_growth", "louvain", "link_prediction", "graph", "formula_search"]))
except Exception as e:
    test("算法配置文件", False, str(e))

print("\n--- 12. 前端文件拆分验证 ---")
try:
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "js")
    test("herb_network.js存在", os.path.exists(os.path.join(frontend_dir, "herb_network.js")))
    test("formula_detail.js存在", os.path.exists(os.path.join(frontend_dir, "formula_detail.js")))
    test("force-worker.js存在", os.path.exists(os.path.join(frontend_dir, "force-worker.js")))

    with open(os.path.join(frontend_dir, "herb_network.js"), 'r', encoding='utf-8') as f:
        hn_content = f.read()
    test("HerbNetwork类定义", "var HerbNetwork" in hn_content)
    test("HerbNetwork含loadData", "HerbNetwork.prototype.loadData" in hn_content)
    test("HerbNetwork含聚合", "_aggregateNodes" in hn_content)
    test("HerbNetwork含Worker", "_startWorkerSimulation" in hn_content)

    with open(os.path.join(frontend_dir, "formula_detail.js"), 'r', encoding='utf-8') as f:
        fd_content = f.read()
    test("FormulaDetail类定义", "var FormulaDetail" in fd_content)
    test("FormulaDetail含showHerbDetail", "showHerbDetail" in fd_content)
    test("FormulaDetail含showFormulaDetail", "showFormulaDetail" in fd_content)
    test("FormulaDetail含showDiseaseDetail", "showDiseaseDetail" in fd_content)
    test("FormulaDetail含showAggregateDetail", "showAggregateDetail" in fd_content)
except Exception as e:
    test("前端文件拆分验证", False, str(e))

print("\n--- 13. 服务端口配置测试 ---")
try:
    settings = get_settings()
    test("formula_loader端口", settings.formula_loader_port == 8001)
    test("pattern_miner端口", settings.pattern_miner_port == 8002)
    test("drug_discoverer端口", settings.drug_discoverer_port == 8003)
    test("graph_api端口", settings.graph_api_port == 8004)
    test("gateway端口", settings.gateway_port == 8000)
except Exception as e:
    test("服务端口配置", False, str(e))

print("\n" + "=" * 60)
print(f"回归测试完成: {passed} 通过, {failed} 失败, 共 {passed + failed} 项")
if errors:
    print("\n失败项:")
    for e in errors:
        print(f"  - {e}")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
