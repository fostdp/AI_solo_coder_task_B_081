from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from bson.errors import InvalidId

from shared.database import get_collection
from shared.redis_client import cache_set, cache_delete, RedisChannels, publish
from shared.models import FormulaCreate

router = APIRouter(prefix="/formulas", tags=["方剂管理"])


def formula_to_response(formula_doc):
    if not formula_doc:
        return None
    formula_doc["_id"] = str(formula_doc["_id"])
    return formula_doc


def _build_text_query(keyword, dynasty, disease, herb):
    query = {}
    if keyword:
        try:
            formulas_col = get_collection("formulas")
            indexes = formulas_col.list_indexes()
            has_text = any(idx.get("name") == "formula_text_index" for idx in indexes)
        except Exception:
            has_text = False

        if has_text:
            text_query = {"$text": {"$search": keyword}}
            if dynasty or disease or herb:
                query["$and"] = [text_query]
                if dynasty:
                    query["$and"].append({"dynasty": dynasty})
                if disease:
                    query["$and"].append({"indications": {"$in": [disease]}})
                if herb:
                    query["$and"].append({"herbs.name": herb})
            else:
                query = text_query
        else:
            query["name"] = {"$regex": keyword, "$options": "i"}
            if dynasty:
                query["dynasty"] = dynasty
            if disease:
                query["indications"] = {"$in": [disease]}
            if herb:
                query["herbs.name"] = herb
    else:
        if dynasty:
            query["dynasty"] = dynasty
        if disease:
            query["indications"] = {"$in": [disease]}
        if herb:
            query["herbs.name"] = herb
    return query


def _should_text_sort(keyword):
    if not keyword:
        return False
    try:
        formulas_col = get_collection("formulas")
        indexes = formulas_col.list_indexes()
        return any(idx.get("name") == "formula_text_index" for idx in indexes)
    except Exception:
        return False


@router.get("/", response_model=List[dict])
def list_formulas(
    skip: int = 0, limit: int = 20,
    keyword: Optional[str] = None, dynasty: Optional[str] = None,
    disease: Optional[str] = None, herb: Optional[str] = None,
    sort_by: str = "frequency", sort_order: str = "desc"
):
    formulas_col = get_collection("formulas")
    query = _build_text_query(keyword, dynasty, disease, herb)

    if _should_text_sort(keyword) and sort_by == "frequency":
        sort_direction = -1 if sort_order == "desc" else 1
        cursor = formulas_col.find(query, {"score": {"$meta": "textScore"}}) \
            .sort([("score", {"$meta": "textScore"}), (sort_by, sort_direction)]) \
            .skip(skip).limit(limit)
    else:
        sort_direction = -1 if sort_order == "desc" else 1
        cursor = formulas_col.find(query).sort(sort_by, sort_direction).skip(skip).limit(limit)

    return [formula_to_response(f) for f in cursor]


@router.get("/count")
def count_formulas(keyword: Optional[str] = None, dynasty: Optional[str] = None,
                   disease: Optional[str] = None, herb: Optional[str] = None):
    formulas_col = get_collection("formulas")
    query = _build_text_query(keyword, dynasty, disease, herb)
    return {"count": formulas_col.count_documents(query)}


@router.get("/{formula_id}")
def get_formula(formula_id: str):
    try:
        oid = ObjectId(formula_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="无效的ID格式")
    formulas_col = get_collection("formulas")
    formula = formulas_col.find_one({"_id": oid})
    if not formula:
        raise HTTPException(status_code=404, detail="方剂不存在")
    return formula_to_response(formula)


@router.get("/by-name/{name}")
def get_formula_by_name(name: str):
    formulas_col = get_collection("formulas")
    formula = formulas_col.find_one({"name": name})
    if not formula:
        raise HTTPException(status_code=404, detail="方剂不存在")
    return formula_to_response(formula)


@router.post("/")
def create_formula(formula: FormulaCreate):
    formulas_col = get_collection("formulas")
    existing = formulas_col.find_one({"name": formula.name})
    if existing:
        raise HTTPException(status_code=400, detail="方剂名称已存在")
    formula_dict = formula.model_dump()
    result = formulas_col.insert_one(formula_dict)
    cache_delete(RedisChannels.FORMULA_TRANSACTIONS)
    publish(RedisChannels.FORMULA_UPDATED, {"action": "create", "name": formula.name})
    return {"id": str(result.inserted_id), "name": formula.name}


@router.put("/{formula_id}")
def update_formula(formula_id: str, formula: FormulaCreate):
    try:
        oid = ObjectId(formula_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="无效的ID格式")
    formulas_col = get_collection("formulas")
    result = formulas_col.update_one({"_id": oid}, {"$set": formula.model_dump()})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="方剂不存在")
    cache_delete(RedisChannels.FORMULA_TRANSACTIONS)
    publish(RedisChannels.FORMULA_UPDATED, {"action": "update", "name": formula.name})
    return {"message": "更新成功"}


@router.delete("/{formula_id}")
def delete_formula(formula_id: str):
    try:
        oid = ObjectId(formula_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="无效的ID格式")
    formulas_col = get_collection("formulas")
    result = formulas_col.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="方剂不存在")
    cache_delete(RedisChannels.FORMULA_TRANSACTIONS)
    publish(RedisChannels.FORMULA_UPDATED, {"action": "delete", "id": formula_id})
    return {"message": "删除成功"}


@router.get("/search/by-disease")
def search_formulas_by_disease(disease: str, skip: int = 0, limit: int = 20):
    formulas_col = get_collection("formulas")
    cursor = formulas_col.find({"indications": {"$in": [disease]}}).sort("frequency", -1).skip(skip).limit(limit)
    result = [formula_to_response(f) for f in cursor]
    total = formulas_col.count_documents({"indications": {"$in": [disease]}})
    return {"formulas": result, "total": total, "disease": disease}


@router.get("/search/by-herbs")
def search_formulas_by_herbs(herbs: List[str] = Query(...), match_all: bool = False,
                              skip: int = 0, limit: int = 20):
    formulas_col = get_collection("formulas")
    query = {"herbs.name": {"$all": herbs}} if match_all else {"herbs.name": {"$in": herbs}}
    cursor = formulas_col.find(query).sort("frequency", -1).skip(skip).limit(limit)
    result = [formula_to_response(f) for f in cursor]
    total = formulas_col.count_documents(query)
    return {"formulas": result, "total": total, "herbs": herbs}


@router.get("/transactions")
def get_transactions():
    formulas_col = get_collection("formulas")
    cached = cache_get(RedisChannels.FORMULA_TRANSACTIONS)
    if cached is not None:
        return cached
    transactions = []
    cursor = formulas_col.find({}, {"herbs.name": 1})
    for f in cursor:
        herb_names = [h["name"] for h in f["herbs"]]
        transactions.append(herb_names)
    result = {"total_transactions": len(transactions), "transactions": transactions}
    cache_set(RedisChannels.FORMULA_TRANSACTIONS, result, ttl=1800)
    return result
