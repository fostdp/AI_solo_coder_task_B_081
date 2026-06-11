from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from collections import defaultdict
import networkx as nx

from shared.database import get_collection, run_neo4j_query
from shared.redis_client import cache_get, cache_set, cache_delete, RedisChannels
from shared.config import get_fp_growth_config, get_louvain_config
from pattern_miner.fp_growth import FPGrowth
from pattern_miner.louvain import LouvainCommunity

router = APIRouter(prefix="/mining", tags=["配伍规律挖掘"])


def _get_transactions():
    cached = cache_get(RedisChannels.FORMULA_TRANSACTIONS)
    if cached is not None and "transactions" in cached:
        return cached["transactions"], cached["total_transactions"]
    formulas_col = get_collection("formulas")
    transactions = []
    cursor = formulas_col.find({}, {"herbs.name": 1})
    for f in cursor:
        herb_names = [h["name"] for h in f["herbs"]]
        transactions.append(herb_names)
    cache_set(RedisChannels.FORMULA_TRANSACTIONS,
              {"total_transactions": len(transactions), "transactions": transactions}, ttl=1800)
    return transactions, len(transactions)


def _get_transactions_by_disease(disease_name: str):
    formulas_col = get_collection("formulas")
    cursor = formulas_col.find({"indications": {"$in": [disease_name]}}, {"herbs.name": 1})
    transactions = []
    for f in cursor:
        herb_names = [h["name"] for h in f["herbs"]]
        transactions.append(herb_names)
    return transactions


@router.get("/frequent-itemsets")
def frequent_itemsets(
    min_support: float = Query(default=None, ge=0.001, le=1.0),
    min_confidence: float = Query(default=None, ge=0.0, le=1.0),
    max_items: int = Query(default=None, ge=2, le=5),
    limit: int = Query(default=100, ge=1, le=1000)
):
    cfg = get_fp_growth_config()
    ms = min_support if min_support is not None else cfg["min_support"]
    mc = min_confidence if min_confidence is not None else cfg["min_confidence"]
    mi = max_items if max_items is not None else cfg["max_itemset_length"]

    transactions, total = _get_transactions()

    fpg = FPGrowth(min_support=ms, min_confidence=mc, max_itemset_length=mi)
    freq_itemsets, _ = fpg.fit(transactions)

    itemsets_by_size = defaultdict(list)
    for itemset, support in freq_itemsets.items():
        size = len(itemset)
        if size <= mi:
            itemsets_by_size[size].append({"items": sorted(list(itemset)), "support": round(support, 4), "count": int(support * total)})

    result = {}
    for size in sorted(itemsets_by_size.keys()):
        items = itemsets_by_size[size]
        items.sort(key=lambda x: -x["support"])
        result[f"{size}-item"] = items[:limit]

    return {"total_transactions": total, "min_support": ms, "max_itemset_length": mi,
            "algorithm": "FP-Growth", "itemsets": result}


@router.get("/association-rules")
def association_rules(
    min_support: float = Query(default=None, ge=0.001, le=1.0),
    min_confidence: float = Query(default=None, ge=0.0, le=1.0),
    min_lift: float = Query(default=None, ge=0.0),
    max_items: int = Query(default=None, ge=2, le=5),
    limit: int = Query(default=50, ge=1, le=500)
):
    cfg = get_fp_growth_config()
    ms = min_support if min_support is not None else cfg["min_support"]
    mc = min_confidence if min_confidence is not None else cfg["min_confidence"]
    ml = min_lift if min_lift is not None else cfg["min_lift"]
    mi = max_items if max_items is not None else cfg["max_itemset_length"]

    transactions, total = _get_transactions()

    fpg = FPGrowth(min_support=ms, min_confidence=mc, min_lift=ml, max_itemset_length=mi)
    fpg.fit(transactions)
    rules = fpg.generate_rules()

    return {"total_transactions": total, "min_support": ms, "min_confidence": mc,
            "min_lift": ml, "max_itemset_length": mi, "algorithm": "FP-Growth",
            "total_rules": len(rules), "rules": rules[:limit]}


@router.get("/top-herb-pairs")
def top_herb_pairs(n: int = Query(default=None, ge=1, le=200),
                   min_support: float = Query(default=None, ge=0.001, le=1.0)):
    cfg = get_fp_growth_config()
    top_n = n if n is not None else cfg["top_pairs_n"]
    ms = min_support if min_support is not None else cfg["min_support"]

    transactions, total = _get_transactions()
    fpg = FPGrowth(min_support=ms, max_itemset_length=2)
    fpg.fit(transactions)
    pairs = fpg.get_top_pairs(top_n)

    return {"total_transactions": total, "algorithm": "FP-Growth", "pairs": pairs}


@router.get("/top-herb-triplets")
def top_herb_triplets(n: int = Query(default=None, ge=1, le=100),
                      min_support: float = Query(default=None, ge=0.001, le=1.0)):
    cfg = get_fp_growth_config()
    top_n = n if n is not None else cfg["top_triplets_n"]
    ms = min_support if min_support is not None else cfg["min_support"]

    transactions, total = _get_transactions()
    fpg = FPGrowth(min_support=ms, max_itemset_length=3)
    fpg.fit(transactions)
    triplets = fpg.get_top_triplets(top_n)

    return {"total_transactions": total, "algorithm": "FP-Growth", "triplets": triplets}


@router.get("/communities")
def detect_communities(
    min_co_occurrence: int = Query(default=None, ge=1),
    resolution: float = Query(default=None, ge=0.1, le=5.0),
    partition_size: int = Query(default=None, ge=20, le=500)
):
    cfg = get_louvain_config()
    mco = min_co_occurrence if min_co_occurrence is not None else cfg["min_co_occurrence"]
    res = resolution if resolution is not None else cfg["resolution"]
    ps = partition_size if partition_size is not None else cfg["partition_size"]

    query = """MATCH (h1:Herb)-[r:CO_OCCURS]->(h2:Herb) WHERE r.count >= $min_count
    RETURN h1.name AS herb_a, h2.name AS herb_b, r.count AS count, r.weight AS weight"""
    results = run_neo4j_query(query, {"min_count": mco})

    G = nx.Graph()
    for r in results:
        G.add_edge(r["herb_a"], r["herb_b"], weight=r["weight"], count=r["count"])

    if G.number_of_nodes() == 0:
        return {"communities": [], "modularity": 0, "total_nodes": 0}

    louvain = LouvainCommunity(resolution=res)
    if G.number_of_nodes() > ps:
        communities = louvain.fit_partitioned(G, partition_size=ps)
    else:
        louvain.fit(G)
        communities = louvain.get_communities()

    sizes = louvain.get_community_sizes()
    community_list = []
    for comm_id, herbs in communities.items():
        herb_info = sorted([{"name": h, "degree": G.degree(h)} for h in herbs], key=lambda x: -x["degree"])
        community_list.append({"community_id": comm_id, "size": sizes[comm_id], "herbs": herb_info})
    community_list.sort(key=lambda x: -x["size"])

    return {"total_nodes": G.number_of_nodes(), "total_edges": G.number_of_edges(),
            "modularity": round(louvain.modularity, 6), "num_communities": len(communities),
            "partitioned": G.number_of_nodes() > ps, "communities": community_list}


@router.get("/by-disease/{disease_name}")
def mining_by_disease(disease_name: str,
                      min_support: float = Query(default=None, ge=0.001, le=1.0),
                      min_confidence: float = Query(default=None, ge=0.0, le=1.0),
                      max_items: int = Query(default=None, ge=2, le=5)):
    cfg = get_fp_growth_config()
    ms = min_support if min_support is not None else cfg["min_support"]
    mc = min_confidence if min_confidence is not None else cfg["min_confidence"]
    mi = max_items if max_items is not None else cfg["max_itemset_length"]

    transactions = _get_transactions_by_disease(disease_name)
    if not transactions:
        raise HTTPException(status_code=404, detail=f"未找到治疗{disease_name}的方剂")

    fpg = FPGrowth(min_support=ms, min_confidence=mc, max_itemset_length=mi)
    fpg.fit(transactions)
    rules = fpg.generate_rules()
    pairs = fpg.get_top_pairs(20)
    triplets = fpg.get_top_triplets(10)

    return {"disease": disease_name, "total_formulas": len(transactions),
            "algorithm": "FP-Growth", "top_pairs": pairs, "top_triplets": triplets, "rules": rules[:30]}


@router.get("/config")
def get_mining_config():
    return {"fp_growth": get_fp_growth_config(), "louvain": get_louvain_config()}
