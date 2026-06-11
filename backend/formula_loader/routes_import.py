from fastapi import APIRouter
from shared.database import get_collection, get_neo4j_driver, run_neo4j_query
from shared.redis_client import cache_delete, RedisChannels, publish
from shared.config import get_algorithm_config

router = APIRouter(prefix="/import", tags=["数据导入"])


@router.post("/mongodb")
def import_mongodb():
    import random
    from bson import ObjectId
    from data.tcm_data import (
        HERBS_DATA, DISEASES_DATA, DYNASTIES,
        FORMULA_NAME_PREFIXES, FORMULA_NAME_SUFFIXES,
        DOSAGE_UNITS, PREPARATIONS, PHARMACOLOGY_TARGETS
    )

    random.seed(42)

    def gen_name(idx):
        if idx < len(FORMULA_NAME_PREFIXES):
            p = FORMULA_NAME_PREFIXES[idx]
            s = random.choice(FORMULA_NAME_SUFFIXES)
            return f"{p}{s}"
        p = random.choice(FORMULA_NAME_PREFIXES)
        s = random.choice(FORMULA_NAME_SUFFIXES)
        m = random.choice(["加味", "减味", "复方", "新"])
        if random.random() < 0.3:
            return f"{m}{p}{s}"
        return f"{p}{random.randint(1,99)}号{s}"

    def gen_dosage():
        if random.random() < 0.7:
            return f"{round(random.uniform(3, 30), 1)}g"
        return f"{random.choice([3,6,9,12,15,18,24,30])}{random.choice(DOSAGE_UNITS)}"

    def gen_prep():
        return random.choice(PREPARATIONS) if random.random() < 0.4 else "生用"

    herbs_col = get_collection("herbs")
    herbs_col.delete_many({})
    for herb in HERBS_DATA:
        herb_doc = herb.copy()
        herb_doc["_id"] = ObjectId()
        herbs_col.insert_one(herb_doc)

    diseases_col = get_collection("diseases")
    diseases_col.delete_many({})
    for disease in DISEASES_DATA:
        disease_doc = disease.copy()
        disease_doc["_id"] = ObjectId()
        diseases_col.insert_one(disease_doc)

    formulas_col = get_collection("formulas")
    formulas_col.delete_many({})
    used_names = set()
    for i in range(5000):
        disease = random.choice(DISEASES_DATA)
        dynasty, author = random.choice(DYNASTIES)
        name = gen_name(i)
        counter = 1
        while name in used_names:
            name = f"{gen_name(i)}_{counter}"
            counter += 1
        used_names.add(name)

        num_herbs = random.choice([3,4,5,5,6,6,7,7,8,9,10,12])
        herb_indices = random.sample(range(len(HERBS_DATA)), min(num_herbs, len(HERBS_DATA)))
        herbs = [{"name": HERBS_DATA[idx]["name"], "dosage": gen_dosage(), "preparation": gen_prep()} for idx in herb_indices]

        indications = [disease["name"]]
        if random.random() < 0.3:
            extra = random.choice(DISEASES_DATA)
            if extra["name"] not in indications:
                indications.append(extra["name"])

        formulas_col.insert_one({
            "_id": ObjectId(), "name": name, "dynasty": dynasty, "author": author,
            "indications": indications, "herbs": herbs,
            "frequency": min(int(random.lognormvariate(3, 1.5)) + 1, 500),
            "source": random.choice(["《伤寒论》","《金匮要略》","《本草纲目》","《太平惠民和剂局方》","《温病条辨》","《脾胃论》"]),
            "form": random.choice(["汤剂","丸剂","散剂","膏剂","丹剂","颗粒剂"]),
            "usage": random.choice(["水煎服，每日一剂","共为细末，每服6-9克","炼蜜为丸，每丸重9克"])
        })

    targets_col = get_collection("herb_targets")
    targets_col.delete_many({})
    for herb in HERBS_DATA:
        num_targets = random.randint(2, 15)
        targets = random.sample(PHARMACOLOGY_TARGETS, min(num_targets, len(PHARMACOLOGY_TARGETS)))
        targets_col.insert_one({
            "_id": ObjectId(), "herb_name": herb["name"],
            "targets": [{"target": t, "affinity": round(random.uniform(0.3, 0.95), 3),
                          "effect_type": random.choice(["激动剂","抑制剂","拮抗剂","调节剂"])} for t in targets]
        })

    cfg = get_algorithm_config().get("formula_search", {})
    formulas_col.create_index([("name", 1)])
    formulas_col.create_index([("indications", 1)])
    formulas_col.create_index([("herbs.name", 1)])
    formulas_col.create_index([("dynasty", 1)])
    formulas_col.create_index([("frequency", -1)])
    formulas_col.create_index(
        [("name", "text"), ("indications", "text"), ("source", "text")],
        name="formula_text_index",
        default_language=cfg.get("default_language", "none"),
        weights=cfg.get("text_index_weights", {"name": 10, "indications": 5, "source": 1})
    )
    herbs_col.create_index([("name", 1)], unique=True)
    herbs_col.create_index([("category", 1)])
    diseases_col.create_index([("name", 1)], unique=True)
    targets_col.create_index([("herb_name", 1)], unique=True)

    cache_delete(RedisChannels.FORMULA_TRANSACTIONS)
    publish(RedisChannels.FORMULA_UPDATED, {"action": "full_import"})

    return {"status": "success", "herbs": len(HERBS_DATA), "diseases": len(DISEASES_DATA), "formulas": 5000}


@router.post("/neo4j")
def import_neo4j():
    run_neo4j_query("MATCH (n) DETACH DELETE n")

    constraints = [
        "CREATE CONSTRAINT herb_name IF NOT EXISTS FOR (h:Herb) REQUIRE h.name IS UNIQUE",
        "CREATE CONSTRAINT formula_name IF NOT EXISTS FOR (f:Formula) REQUIRE f.name IS UNIQUE",
        "CREATE CONSTRAINT disease_name IF NOT EXISTS FOR (d:Disease) REQUIRE d.name IS UNIQUE",
    ]
    for q in constraints:
        try:
            run_neo4j_query(q)
        except Exception:
            pass

    herbs = list(get_collection("herbs").find())
    driver = get_neo4j_driver()
    with driver.session() as session:
        for herb in herbs:
            session.run("CREATE (h:Herb {name: $name, nature: $nature, flavor: $flavor, meridians: $meridians, category: $category})",
                        {"name": herb["name"], "nature": herb["nature"], "flavor": herb["flavor"],
                         "meridians": herb["meridians"], "category": herb["category"]})

    diseases = list(get_collection("diseases").find())
    with driver.session() as session:
        for disease in diseases:
            session.run("CREATE (d:Disease {name: $name, category: $category, symptoms: $symptoms})",
                        {"name": disease["name"], "category": disease["category"], "symptoms": disease["symptoms"]})

    formulas = list(get_collection("formulas").find())
    with driver.session() as session:
        for f in formulas:
            herb_names = [h["name"] for h in f["herbs"]]
            session.run(
                """CREATE (form:Formula {name: $name, dynasty: $dynasty, author: $author, frequency: $frequency, source: $source, form: $form})
                WITH form UNWIND $herb_names AS herb_name
                MATCH (h:Herb {name: herb_name}) CREATE (form)-[:CONTAINS]->(h)
                WITH form UNWIND $indications AS disease_name
                MATCH (d:Disease {name: disease_name}) CREATE (form)-[:TREATS]->(d)""",
                {"name": f["name"], "dynasty": f["dynasty"], "author": f["author"],
                 "frequency": f["frequency"], "source": f.get("source", ""), "form": f.get("form", ""),
                 "herb_names": herb_names, "indications": f["indications"]})

    run_neo4j_query(
        """MATCH (f:Formula)-[:CONTAINS]->(h1:Herb)
        MATCH (f:Formula)-[:CONTAINS]->(h2:Herb)
        WHERE h1.name < h2.name
        WITH h1, h2, COUNT(f) AS co_count, SUM(f.frequency) AS weight
        CREATE (h1)-[:CO_OCCURS {count: co_count, weight: weight}]->(h2)""")

    cache_delete(RedisChannels.GRAPH_NETWORK)
    publish(RedisChannels.FORMULA_UPDATED, {"action": "neo4j_import"})
    return {"status": "success", "formulas": len(formulas)}


@router.post("/all")
def import_all():
    mongo_result = import_mongodb()
    neo4j_result = import_neo4j()
    return {"mongodb": mongo_result, "neo4j": neo4j_result}
