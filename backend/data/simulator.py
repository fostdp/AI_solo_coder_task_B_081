"""
中医药方剂数据模拟器

支持按朝代权重生成不同风格的方剂，包含药物组成、炮制方法、剂量，
以及药理靶点数据。

用法:
    python -m data.simulator --formulas 5000 --seed 42
    python -m data.simulator --formulas 2000 --dynasty-weights '{"汉代":0.3,"唐代":0.3,"宋代":0.2,"金元":0.1,"明代":0.05,"清代":0.05}'
"""

import argparse
import json
import os
import sys
import random
from collections import defaultdict
from datetime import datetime

from bson import ObjectId

from shared.database import get_collection
from shared.redis_client import cache_delete, publish, RedisChannels
from data.tcm_data import HERBS_DATA, DISEASES_DATA, PHARMACOLOGY_TARGETS


DYNASTY_AUTHORS = {
    "汉代": ["张仲景", "华佗", "仓公", "郭玉", "华佗", "王叔和", "皇甫谧", "葛洪"],
    "唐代": ["孙思邈", "王焘", "巢元方", "苏敬", "甄权", "孟诜", "王冰", "许胤宗"],
    "宋代": ["钱乙", "刘完素", "陈无择", "朱肱", "许叔微", "郭雍", "严用和", "杨士瀛"],
    "金元": ["李东垣", "张从正", "朱丹溪", "刘河间", "罗天益", "王好古", "张元素", "危亦林"],
    "明代": ["李时珍", "张景岳", "朱丹溪", "薛己", "汪机", "孙一奎", "缪希雍", "王肯堂", "吴又可"],
    "清代": ["叶天士", "吴鞠通", "薛雪", "王清任", "张锡纯", "喻嘉言", "陈士铎", "张志聪", "柯琴"],
}

DYNASTY_SOURCES = {
    "汉代": ["《伤寒论》", "《金匮要略》", "《黄帝内经》", "《神农本草经》", "《八十一难经》"],
    "唐代": ["《千金要方》", "《千金翼方》", "《外台秘要》", "《新修本草》", "《本草经集注》"],
    "宋代": ["《太平惠民和剂局方》", "《小儿药证直诀》", "《三因极一病证方论》", "《南阳活人书》"],
    "金元": ["《脾胃论》", "《儒门事亲》", "《格致余论》", "《素问玄机原病式》", "《兰室秘藏》"],
    "明代": ["《本草纲目》", "《景岳全书》", "《温疫论》", "《医宗必读》", "《证治准绳》"],
    "清代": ["《温病条辨》", "《温热论》", "《湿热条辨》", "《医林改错》", "《医学衷中参西录》"],
}

DYNASTY_STYLES = {
    "汉代":   {"min_herbs": 3,  "max_herbs": 10, "avg_freq": 50,  "style": "经方"},
    "唐代":   {"min_herbs": 5,  "max_herbs": 15, "avg_freq": 35,  "style": "大方"},
    "宋代":   {"min_herbs": 6,  "max_herbs": 18, "avg_freq": 25,  "style": "和剂"},
    "金元":   {"min_herbs": 4,  "max_herbs": 12, "avg_freq": 20,  "style": "攻邪"},
    "明代":   {"min_herbs": 5,  "max_herbs": 20, "avg_freq": 15,  "style": "温补"},
    "清代":   {"min_herbs": 4,  "max_herbs": 14, "avg_freq": 10,  "style": "温病"},
}

DOSAGE_UNITS = ["g", "两", "钱", "分"]
PREPARATIONS = ["生用", "酒炙", "醋炙", "蜜炙", "盐炙", "姜炙", "炒", "炒焦", "炒炭", "煅", "蒸", "煮", "煨"]

DISEASE_CATEGORY_MAP = {
    "外感热病": "温性",
    "内科杂病": "平性",
    "妇科": "温性",
    "外科": "寒性",
    "五官科": "平性",
    "儿科": "平性",
}

TARGET_CLASSES = [
    "G蛋白偶联受体", "离子通道", "酶", "转运体", "核受体",
    "细胞因子", "激酶", "蛋白酶", "转录因子", "免疫靶点"
]

EFFECT_TYPES = ["激动剂", "抑制剂", "拮抗剂", "调节剂", "部分激动剂", "反向激动剂"]


def weighted_choice(weights_dict):
    """按权重字典随机选择键"""
    items = list(weights_dict.items())
    total = sum(w for _, w in items)
    r = random.random() * total
    cum = 0
    for item, weight in items:
        cum += weight
        if r <= cum:
            return item
    return items[-1][0]


def generate_herb_bank_by_nature():
    """按药性分类药物"""
    nature_herbs = defaultdict(list)
    for herb in HERBS_DATA:
        nature_herbs[herb["nature"]].append(herb)
    return dict(nature_herbs)


def generate_target_for_herb(herb_name, targets_pool, num_targets_range=(2, 15)):
    """为单味药生成靶点数据"""
    k = random.randint(*num_targets_range)
    selected = random.sample(targets_pool, min(k, len(targets_pool)))
    result = []
    for target in selected:
        result.append({
            "target": target,
            "affinity": round(random.uniform(0.3, 0.95), 3),
            "effect_type": random.choice(EFFECT_TYPES),
            "target_class": random.choice(TARGET_CLASSES),
            "kd_value": round(random.uniform(0.001, 10.0), 4),
            "source": "模拟数据"
        })
    return result


def generate_formula(idx, dynasty, nature_herbs, style):
    """生成一首方剂"""
    dynasty = dynasty
    author = random.choice(DYNASTY_AUTHORS[dynasty])
    source = random.choice(DYNASTY_SOURCES[dynasty])
    disease = random.choice(DISEASES_DATA)

    style_info = DYNASTY_STYLES[dynasty]
    num_herbs = random.randint(style_info["min_herbs"], style_info["max_herbs"])

    disease_category = disease["category"]
    preferred_nature = DISEASE_CATEGORY_MAP.get(disease_category, "平性")

    herbs = []
    herb_names_set = set()

    if preferred_nature in nature_herbs:
        preferred_pool = nature_herbs[preferred_nature]
        num_preferred = int(num_herbs * 0.6)
        if preferred_pool:
            selected = random.sample(preferred_pool, min(num_preferred, len(preferred_pool)))
            for h in selected:
                herbs.append(h)
                herb_names_set.add(h["name"])

    remaining = num_herbs - len(herbs)
    if remaining > 0:
        for herb in HERBS_DATA:
            if herb["name"] not in herb_names_set:
                herbs.append(herb)
                herb_names_set.add(herb["name"])
                if len(herbs) >= num_herbs:
                    break
        if len(herbs) < num_herbs:
            herbs = random.sample(HERBS_DATA, min(num_herbs, len(HERBS_DATA)))

    random.shuffle(herbs)

    name = generate_formula_name(idx, dynasty, disease, herbs)

    herb_details = []
    for herb in herbs:
        dosage = generate_dosage(herb["name"])
        prep = random.choice(PREPARATIONS) if random.random() < 0.4 else "生用"
        herb_details.append({"name": herb["name"], "dosage": dosage, "preparation": prep})

    indications = [disease["name"]]
    if random.random() < 0.35:
        extra = random.choice(DISEASES_DATA)
        if extra["name"] not in indications:
            indications.append(extra["name"])

    freq = max(1, int(random.lognormvariate(3, 1.5) * style_info["avg_freq"] / 50))
    freq = min(freq, 500)

    return {
        "name": name,
        "dynasty": dynasty,
        "author": author,
        "indications": indications,
        "herbs": herb_details,
        "frequency": freq,
        "source": source,
        "form": random.choice(["汤剂", "丸剂", "散剂", "膏剂", "丹剂", "颗粒剂"]),
        "usage": generate_usage(dynasty),
        "style": style_info["style"],
        "created_at": datetime.now().isoformat(),
    }


def generate_formula_name(idx, dynasty, disease, herbs):
    """生成方剂名"""
    prefixes = ["大", "小", "加味", "减味", "复方", "新", "秘", "神", "妙", "奇"]
    middle_parts = ["黄芪", "桂枝", "柴胡", "麻黄", "白虎", "青龙", "真武", "理中", "逍遥", "归脾", "金匮"]
    suffixes = ["汤", "丸", "散", "膏", "丹", "饮", "煎"]

    if random.random() < 0.3 and herbs:
        main_herb = herbs[0]["name"]
        suffix = random.choice(suffixes)
        return f"{main_herb}{suffix}"

    if random.random() < 0.25:
        prefix = random.choice(prefixes)
        suffix = random.choice(suffixes)
        return f"{prefix}{random.choice(middle_parts)}{suffix}"

    if random.random() < 0.2:
        return f"{disease['name']}{random.choice(suffixes)}"

    p = random.choice(FORMULA_NAME_PREFIXES) if 'FORMULA_NAME_PREFIXES' in globals() else random.choice(middle_parts)
    s = random.choice(suffixes)
    if random.random() < 0.3:
        return f"{random.choice(prefixes)}{p}{idx + 1}号{s}"
    return f"{p}{s}"


FORMULA_NAME_PREFIXES = [
    "桂枝", "麻黄", "白虎", "青龙", "真武", "小柴胡", "大柴胡", "理中", "逍遥", "归脾",
    "八珍", "十全大补", "六味地黄", "金匮肾气", "天王补心", "朱砂安神", "补中益气", "藿香正气",
    "黄连解毒", "龙胆泻肝", "参苓白术", "四君子", "四物汤", "桃红四物", "血府逐瘀", "温胆"
]


def generate_dosage(herb_name):
    """生成剂量"""
    if random.random() < 0.6:
        return f"{round(random.uniform(3, 30), 1)}g"
    if random.random() < 0.5:
        return f"{random.choice([3, 6, 9, 12, 15, 18, 24, 30])}g"
    unit = random.choice(DOSAGE_UNITS)
    if unit == "两":
        return f"{random.choice([1, 2, 3, 5, 8, 10])}{unit}"
    if unit == "钱":
        return f"{random.choice([1, 2, 3, 4, 5])}{unit}"
    return f"{random.choice([0.5, 1, 1.5, 2, 3])}{unit}"


def generate_usage(dynasty):
    """生成用法"""
    usages = [
        "水煎服，每日一剂，分温再服",
        "共为细末，每服6-9克，日三服",
        "炼蜜为丸，每丸重9克，每次一丸，日二服",
        "水煎服，日一剂，早晚分服",
        "上七味，以水一斗，煮取六升，去滓，再煎，温服一升，日三服",
        "共研细末，醋糊为丸，如梧桐子大，每服三十丸",
        "水煎服，生姜三片，大枣五枚为引",
    ]
    return random.choice(usages)


def run_simulation(num_formulas=5000, num_targets=100, seed=42,
                    dynasty_weights=None, clear_before=True,
                    import_neo4j_flag=True):
    """运行模拟器，生成数据并写入MongoDB和Neo4j"""
    random.seed(seed)

    print(f"[模拟器] 开始生成数据，种子: {seed}, 方剂数: {num_formulas}")

    if dynasty_weights is None:
        dynasty_weights = {
            "汉代": 0.20, "唐代": 0.20, "宋代": 0.20,
            "金元": 0.15, "明代": 0.15, "清代": 0.10
        }
    print(f"[模拟器] 朝代权重: {dynasty_weights}")

    nature_herbs = generate_herb_bank_by_nature()

    formulas_col = get_collection("formulas")
    herbs_col = get_collection("herbs")
    diseases_col = get_collection("diseases")
    targets_col = get_collection("herb_targets")

    if clear_before:
        print("[模拟器] 清空现有数据...")
        formulas_col.delete_many({})
        herbs_col.delete_many({})
        diseases_col.delete_many({})
        targets_col.delete_many({})

    print("[模拟器] 写入中药基础数据...")
    herb_ids = {}
    for herb in HERBS_DATA:
        doc = herb.copy()
        doc["_id"] = ObjectId()
        result = herbs_col.insert_one(doc)
        herb_ids[herb["name"]] = result.inserted_id

    print("[模拟器] 写入病症基础数据...")
    for disease in DISEASES_DATA:
        doc = disease.copy()
        doc["_id"] = ObjectId()
        diseases_col.insert_one(doc)

    print("[模拟器] 生成方剂数据...")
    dynasties = list(dynasty_weights.keys())
    weights = list(dynasty_weights.values())

    formulas = []
    used_names = set()
    batch_size = 1000

    for i in range(num_formulas):
        dynasty = random.choices(dynasties, weights=weights, k=1)[0]
        formula = generate_formula(i, dynasty, nature_herbs, DYNASTY_STYLES[dynasty])

        counter = 1
        while formula["name"] in used_names:
            formula["name"] = f"{formula['name']}_{counter}"
            counter += 1
        used_names.add(formula["name"])

        formula["_id"] = ObjectId()
        formulas.append(formula)

        if len(formulas) >= batch_size:
            formulas_col.insert_many(formulas)
            print(f"  已生成 {len(formulas) + (i // batch_size * batch_size)} / {num_formulas} 首")
            formulas = []

    if formulas:
        formulas_col.insert_many(formulas)

    print(f"[模拟器] 生成药理靶点数据（{num_targets}个靶点）...")
    target_pool = PHARMACOLOGY_TARGETS[:num_targets] if num_targets <= len(PHARMACOLOGY_TARGETS) else PHARMACOLOGY_TARGETS

    target_docs = []
    for herb in HERBS_DATA:
        target_docs.append({
            "_id": ObjectId(),
            "herb_name": herb["name"],
            "herb_category": herb.get("category", ""),
            "targets": generate_target_for_herb(herb["name"], target_pool, (2, 15)),
            "created_at": datetime.now().isoformat()
        })
    targets_col.insert_many(target_docs)

    print("[模拟器] 创建索引...")
    formulas_col.create_index([("name", 1)])
    formulas_col.create_index([("dynasty", 1)])
    formulas_col.create_index([("indications", 1)])
    formulas_col.create_index([("herbs.name", 1)])
    formulas_col.create_index([("frequency", -1)])
    formulas_col.create_index(
        [("name", "text"), ("indications", "text"), ("source", "text")],
        name="formula_text_index",
        default_language="none",
        weights={"name": 10, "indications": 5, "source": 1}
    )
    herbs_col.create_index([("name", 1)], unique=True)
    herbs_col.create_index([("category", 1)])
    herbs_col.create_index([("nature", 1)])
    diseases_col.create_index([("name", 1)], unique=True)
    diseases_col.create_index([("category", 1)])
    targets_col.create_index([("herb_name", 1)], unique=True)
    targets_col.create_index([("targets.target", 1)])

    print("[模拟器] MongoDB数据导入完成")

    if import_neo4j_flag:
        print("[模拟器] 导入Neo4j图数据库...")
        import_neo4j_data()

    print("[模拟器] 清除Redis缓存...")
    cache_delete(RedisChannels.FORMULA_TRANSACTIONS)
    cache_delete(RedisChannels.GRAPH_NETWORK)
    publish(RedisChannels.FORMULA_UPDATED, {"action": "full_import", "count": num_formulas})

    dynasty_counts = formulas_col.aggregate([
        {"$group": {"_id": "$dynasty", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ])

    print("\n[模拟器] ========== 生成统计 ==========")
    print(f"总方剂数: {num_formulas}")
    print(f"中药数: {len(HERBS_DATA)}")
    print(f"病症数: {len(DISEASES_DATA)}")
    print(f"靶点数据: {len(target_docs)} 味药 × 2-15个靶点")
    print("\n按朝代分布:")
    for dc in dynasty_counts:
        print(f"  {dc['_id']}: {dc['count']} 首 ({dc['count']/num_formulas*100:.1f}%)")
    print("[模拟器] 完成！")

    return {
        "formulas": num_formulas,
        "herbs": len(HERBS_DATA),
        "diseases": len(DISEASES_DATA),
        "targets": len(target_docs),
        "dynasty_distribution": {dc["_id"]: dc["count"] for dc in dynasty_counts},
    }


def import_neo4j_data():
    """导入Neo4j图数据"""
    from shared.database import get_neo4j_driver, run_neo4j_query

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

    herbs_col = get_collection("herbs")
    diseases_col = get_collection("diseases")
    formulas_col = get_collection("formulas")

    driver = get_neo4j_driver()

    print("  导入中药节点...")
    with driver.session() as session:
        herbs = list(herbs_col.find())
        batch = []
        for h in herbs:
            batch.append(h)
            if len(batch) >= 100:
                session.run("""
                    UNWIND $batch AS h
                    CREATE (:Herb {name: h.name, nature: h.nature, flavor: h.flavor,
                                   meridians: h.meridians, category: h.category})
                """, {"batch": [{"name": h["name"], "nature": h["nature"], "flavor": h["flavor"],
                                 "meridians": h["meridians"], "category": h.get("category", "")} for h in batch]})
                batch = []
        if batch:
            session.run("""
                UNWIND $batch AS h
                CREATE (:Herb {name: h.name, nature: h.nature, flavor: h.flavor,
                               meridians: h.meridians, category: h.category})
            """, {"batch": [{"name": h["name"], "nature": h["nature"], "flavor": h["flavor"],
                             "meridians": h["meridians"], "category": h.get("category", "")} for h in batch]})

    print("  导入病症节点...")
    with driver.session() as session:
        diseases = list(diseases_col.find())
        batch = []
        for d in diseases:
            batch.append(d)
            if len(batch) >= 100:
                session.run("""
                    UNWIND $batch AS d
                    CREATE (:Disease {name: d.name, category: d.category, symptoms: d.symptoms})
                """, {"batch": [{"name": d["name"], "category": d.get("category", ""),
                                 "symptoms": d.get("symptoms", [])} for d in batch]})
                batch = []
        if batch:
            session.run("""
                UNWIND $batch AS d
                CREATE (:Disease {name: d.name, category: d.category, symptoms: d.symptoms})
            """, {"batch": [{"name": d["name"], "category": d.get("category", ""),
                             "symptoms": d.get("symptoms", [])} for d in batch]})

    print("  导入方剂节点及关系（批量）...")
    total_formulas = formulas_col.count_documents({})
    processed = 0
    batch_size = 100

    with driver.session() as session:
        cursor = formulas_col.find({})
        batch = []
        for f in cursor:
            batch.append(f)
            if len(batch) >= batch_size:
                _import_formula_batch(session, batch)
                processed += len(batch)
                print(f"    {processed} / {total_formulas}")
                batch = []
        if batch:
            _import_formula_batch(session, batch)
            processed += len(batch)

    print("  计算共现关系...")
    run_neo4j_query("""
        MATCH (f:Formula)-[:CONTAINS]->(h1:Herb)
        MATCH (f:Formula)-[:CONTAINS]->(h2:Herb)
        WHERE h1.name < h2.name
        WITH h1, h2, COUNT(f) AS co_count, SUM(f.frequency) AS weight
        CREATE (h1)-[:CO_OCCURS {count: co_count, weight: weight}]->(h2)
    """)

    print("  Neo4j导入完成！")


def _import_formula_batch(session, batch):
    """批量导入方剂及关系"""
    data = []
    for f in batch:
        data.append({
            "name": f["name"], "dynasty": f.get("dynasty", ""),
            "author": f.get("author", ""), "frequency": f.get("frequency", 1),
            "source": f.get("source", ""), "form": f.get("form", ""),
            "herb_names": [h["name"] for h in f["herbs"]],
            "indications": f.get("indications", [])
        })

    session.run("""
        UNWIND $batch AS f
        CREATE (form:Formula {name: f.name, dynasty: f.dynasty, author: f.author,
                             frequency: f.frequency, source: f.source, form: f.form})
        WITH form, f.herb_names AS herb_names
        UNWIND herb_names AS herb_name
        MATCH (h:Herb {name: herb_name})
        MERGE (form)-[:CONTAINS]->(h)
    """, {"batch": data})

    session.run("""
        UNWIND $batch AS f
        MATCH (form:Formula {name: f.name})
        UNWIND f.indications AS disease_name
        MATCH (d:Disease {name: disease_name})
        MERGE (form)-[:TREATS]->(d)
    """, {"batch": data})


def main():
    parser = argparse.ArgumentParser(description="中医药方剂数据模拟器")
    parser.add_argument("--formulas", type=int, default=None, help="生成方剂数量")
    parser.add_argument("--targets", type=int, default=None, help="靶点数量上限")
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    parser.add_argument("--dynasty-weights", type=str, default=None,
                        help='朝代权重 JSON 字符串，如: {"汉代":0.3,"唐代":0.3}')
    parser.add_argument("--no-clear", action="store_true", help="不清空现有数据")
    parser.add_argument("--no-neo4j", action="store_true", help="不导入Neo4j")

    args = parser.parse_args()

    num_formulas = args.formulas or int(os.environ.get("SIM_NUM_FORMULAS", "5000"))
    num_targets = args.targets or int(os.environ.get("SIM_NUM_TARGETS", "100"))
    seed = args.seed or int(os.environ.get("SIM_SEED", "42"))

    clear_before = not args.no_clear
    if not args.no_clear and os.environ.get("SIM_CLEAR_BEFORE", "").lower() in ("false", "0", "no"):
        clear_before = False

    import_neo4j_flag = not args.no_neo4j
    if not args.no_neo4j and os.environ.get("SIM_IMPORT_NEO4J", "").lower() in ("false", "0", "no"):
        import_neo4j_flag = False

    dynasty_weights = None
    if args.dynasty_weights:
        try:
            dynasty_weights = json.loads(args.dynasty_weights)
        except json.JSONDecodeError as e:
            print(f"错误: 朝代权重JSON解析失败: {e}")
            sys.exit(1)
    elif os.environ.get("SIM_DYNASTY_WEIGHTS"):
        try:
            dynasty_weights = json.loads(os.environ["SIM_DYNASTY_WEIGHTS"])
        except json.JSONDecodeError as e:
            print(f"警告: SIM_DYNASTY_WEIGHTS 环境变量JSON解析失败: {e}，使用默认分布")

    result = run_simulation(
        num_formulas=num_formulas,
        num_targets=num_targets,
        seed=seed,
        dynasty_weights=dynasty_weights,
        clear_before=clear_before,
        import_neo4j_flag=import_neo4j_flag,
    )

    print("\n生成完成！")


if __name__ == "__main__":
    main()
