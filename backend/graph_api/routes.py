from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from shared.database import run_neo4j_query
from shared.redis_client import cache_get, cache_set, RedisChannels
from shared.config import get_graph_config

router = APIRouter(prefix="/graph", tags=["图数据"])


@router.get("/network")
def get_graph_network(
    node_types: Optional[List[str]] = Query(default=None),
    limit_per_type: int = Query(default=None),
    include_relations: bool = True
):
    cfg = get_graph_config()
    limit = limit_per_type or cfg["default_limit_per_type"]
    co_limit = cfg["co_occurs_limit"]

    nodes = []
    edges = []

    if node_types is None or "Herb" in node_types:
        herbs = run_neo4j_query("MATCH (h:Herb) RETURN h LIMIT $limit", {"limit": limit})
        for h in herbs:
            d = h["h"]
            nodes.append({"id": f"herb_{d['name']}", "label": d["name"], "type": "herb",
                          "properties": {"nature": d.get("nature", ""), "flavor": d.get("flavor", []),
                                         "meridians": d.get("meridians", []), "category": d.get("category", "")}})

    if node_types is None or "Formula" in node_types:
        formulas = run_neo4j_query("MATCH (f:Formula) RETURN f ORDER BY f.frequency DESC LIMIT $limit", {"limit": limit})
        for f in formulas:
            d = f["f"]
            nodes.append({"id": f"formula_{d['name']}", "label": d["name"], "type": "formula",
                          "size": d.get("frequency", 1),
                          "properties": {"dynasty": d.get("dynasty", ""), "author": d.get("author", ""),
                                         "frequency": d.get("frequency", 1), "source": d.get("source", "")}})

    if node_types is None or "Disease" in node_types:
        diseases = run_neo4j_query("MATCH (d:Disease) RETURN d LIMIT $limit", {"limit": limit})
        for d in diseases:
            data = d["d"]
            nodes.append({"id": f"disease_{data['name']}", "label": data["name"], "type": "disease",
                          "properties": {"category": data.get("category", ""), "symptoms": data.get("symptoms", [])}})

    if include_relations:
        formula_names = [n["label"] for n in nodes if n["type"] == "formula"]
        herb_names = [n["label"] for n in nodes if n["type"] == "herb"]
        disease_names = [n["label"] for n in nodes if n["type"] == "disease"]

        if formula_names and herb_names:
            rels = run_neo4j_query(
                "MATCH (f:Formula)-[:CONTAINS]->(h:Herb) WHERE f.name IN $fn AND h.name IN $hn RETURN f.name AS source, h.name AS target",
                {"fn": formula_names, "hn": herb_names})
            for r in rels:
                edges.append({"source": f"formula_{r['source']}", "target": f"herb_{r['target']}", "label": "contains", "type": "contains"})

        if formula_names and disease_names:
            rels = run_neo4j_query(
                "MATCH (f:Formula)-[:TREATS]->(d:Disease) WHERE f.name IN $fn AND d.name IN $dn RETURN f.name AS source, d.name AS target",
                {"fn": formula_names, "dn": disease_names})
            for r in rels:
                edges.append({"source": f"formula_{r['source']}", "target": f"disease_{r['target']}", "label": "treats", "type": "treats"})

        if herb_names:
            co = run_neo4j_query(
                "MATCH (h1:Herb)-[r:CO_OCCURS]->(h2:Herb) WHERE h1.name IN $hn AND h2.name IN $hn RETURN h1.name AS source, h2.name AS target, r.count AS count, r.weight AS weight ORDER BY r.weight DESC LIMIT $lim",
                {"hn": herb_names, "lim": co_limit})
            for r in co:
                edges.append({"source": f"herb_{r['source']}", "target": f"herb_{r['target']}",
                              "label": "co-occurs", "type": "co_occurs", "weight": r.get("weight", 0), "count": r.get("count", 0)})

    cache_set(RedisChannels.GRAPH_NETWORK, {"nodes": nodes, "edges": edges}, ttl=600)
    return {"nodes": nodes, "edges": edges, "total_nodes": len(nodes), "total_edges": len(edges)}


@router.get("/herb-cooccurrence")
def get_herb_cooccurrence(min_count: int = 10, limit: int = 100):
    results = run_neo4j_query(
        "MATCH (h1:Herb)-[r:CO_OCCURS]->(h2:Herb) WHERE r.count >= $min_count RETURN h1.name AS herb_a, h2.name AS herb_b, r.count AS count, r.weight AS weight ORDER BY r.weight DESC LIMIT $limit",
        {"min_count": min_count, "limit": limit})
    return {"pairs": results, "total": len(results)}


@router.get("/disease-formulas/{disease_name}")
def get_disease_formula_graph(disease_name: str):
    results = run_neo4j_query(
        "MATCH (d:Disease {name: $disease_name}) OPTIONAL MATCH (f:Formula)-[:TREATS]->(d) OPTIONAL MATCH (f)-[:CONTAINS]->(h:Herb) WITH d, COLLECT(DISTINCT f) AS formulas, COLLECT(DISTINCT h) AS herbs RETURN d, formulas, herbs",
        {"disease_name": disease_name})
    if not results:
        raise HTTPException(status_code=404, detail="病症不存在")

    result = results[0]
    nodes = []
    edges = []
    dd = result["d"]
    nodes.append({"id": f"disease_{dd['name']}", "label": dd["name"], "type": "disease",
                  "properties": {"category": dd.get("category", ""), "symptoms": dd.get("symptoms", [])}})

    formula_set = set()
    herb_set = set()
    for f in result["formulas"]:
        fid = f"formula_{f['name']}"
        if fid not in formula_set:
            formula_set.add(fid)
            nodes.append({"id": fid, "label": f["name"], "type": "formula", "size": f.get("frequency", 1),
                          "properties": {"dynasty": f.get("dynasty", ""), "frequency": f.get("frequency", 1)}})
            edges.append({"source": fid, "target": f"disease_{disease_name}", "label": "treats", "type": "treats"})

    for h in result["herbs"]:
        hid = f"herb_{h['name']}"
        if hid not in herb_set:
            herb_set.add(hid)
            nodes.append({"id": hid, "label": h["name"], "type": "herb",
                          "properties": {"nature": h.get("nature", ""), "category": h.get("category", "")}})

    return {"nodes": nodes, "edges": edges, "total_nodes": len(nodes), "total_edges": len(edges)}


@router.get("/herb-formulas/{herb_name}")
def get_herb_formula_graph(herb_name: str):
    results = run_neo4j_query(
        "MATCH (h:Herb {name: $herb_name}) OPTIONAL MATCH (f:Formula)-[:CONTAINS]->(h) OPTIONAL MATCH (f)-[:TREATS]->(d:Disease) WITH h, COLLECT(DISTINCT f) AS formulas, COLLECT(DISTINCT d) AS diseases RETURN h, formulas, diseases",
        {"herb_name": herb_name})
    if not results:
        raise HTTPException(status_code=404, detail="药物不存在")

    result = results[0]
    nodes = []
    edges = []
    hd = result["h"]
    nodes.append({"id": f"herb_{hd['name']}", "label": hd["name"], "type": "herb",
                  "properties": {"nature": hd.get("nature", ""), "flavor": hd.get("flavor", []),
                                 "meridians": hd.get("meridians", []), "category": hd.get("category", "")}})

    formula_set = set()
    disease_set = set()
    for f in result["formulas"]:
        fid = f"formula_{f['name']}"
        if fid not in formula_set:
            formula_set.add(fid)
            nodes.append({"id": fid, "label": f["name"], "type": "formula", "size": f.get("frequency", 1),
                          "properties": {"dynasty": f.get("dynasty", ""), "frequency": f.get("frequency", 1)}})
            edges.append({"source": fid, "target": f"herb_{herb_name}", "label": "contains", "type": "contains"})

    for d in result["diseases"]:
        did = f"disease_{d['name']}"
        if did not in disease_set:
            disease_set.add(did)
            nodes.append({"id": did, "label": d["name"], "type": "disease", "properties": {"category": d.get("category", "")}})

    return {"nodes": nodes, "edges": edges, "total_nodes": len(nodes), "total_edges": len(edges)}


@router.get("/formula-detail/{formula_name}")
def get_formula_detail_graph(formula_name: str):
    results = run_neo4j_query(
        "MATCH (f:Formula {name: $formula_name}) OPTIONAL MATCH (f)-[:CONTAINS]->(h:Herb) OPTIONAL MATCH (f)-[:TREATS]->(d:Disease) WITH f, COLLECT(DISTINCT h) AS herbs, COLLECT(DISTINCT d) AS diseases RETURN f, herbs, diseases",
        {"formula_name": formula_name})
    if not results:
        raise HTTPException(status_code=404, detail="方剂不存在")

    result = results[0]
    nodes = []
    edges = []
    fd = result["f"]
    nodes.append({"id": f"formula_{fd['name']}", "label": fd["name"], "type": "formula", "size": fd.get("frequency", 1),
                  "properties": {"dynasty": fd.get("dynasty", ""), "author": fd.get("author", ""),
                                 "frequency": fd.get("frequency", 1), "source": fd.get("source", ""), "form": fd.get("form", "")}})

    for h in result["herbs"]:
        nodes.append({"id": f"herb_{h['name']}", "label": h["name"], "type": "herb",
                      "properties": {"nature": h.get("nature", ""), "category": h.get("category", ""), "meridians": h.get("meridians", [])}})
        edges.append({"source": f"formula_{formula_name}", "target": f"herb_{h['name']}", "label": "contains", "type": "contains"})

    for d in result["diseases"]:
        nodes.append({"id": f"disease_{d['name']}", "label": d["name"], "type": "disease",
                      "properties": {"category": d.get("category", ""), "symptoms": d.get("symptoms", [])}})
        edges.append({"source": f"formula_{formula_name}", "target": f"disease_{d['name']}", "label": "treats", "type": "treats"})

    return {"nodes": nodes, "edges": edges, "total_nodes": len(nodes), "total_edges": len(edges)}


@router.get("/config")
def get_graph_config_endpoint():
    return {"graph": get_graph_config()}
