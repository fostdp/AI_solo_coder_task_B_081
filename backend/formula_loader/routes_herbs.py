from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from bson import ObjectId
from bson.errors import InvalidId

from shared.database import get_collection

router = APIRouter(prefix="/herbs", tags=["中药管理"])


def herb_to_response(herb_doc):
    if not herb_doc:
        return None
    herb_doc["_id"] = str(herb_doc["_id"])
    return herb_doc


@router.get("/")
def list_herbs(skip: int = 0, limit: int = 50, keyword: Optional[str] = None,
               category: Optional[str] = None, nature: Optional[str] = None,
               meridian: Optional[str] = None):
    herbs_col = get_collection("herbs")
    query = {}
    if keyword:
        query["name"] = {"$regex": keyword, "$options": "i"}
    if category:
        query["category"] = category
    if nature:
        query["nature"] = nature
    if meridian:
        query["meridians"] = {"$in": [meridian]}
    cursor = herbs_col.find(query).skip(skip).limit(limit)
    return [herb_to_response(h) for h in cursor]


@router.get("/count")
def count_herbs(category: Optional[str] = None, nature: Optional[str] = None):
    herbs_col = get_collection("herbs")
    query = {}
    if category:
        query["category"] = category
    if nature:
        query["nature"] = nature
    return {"count": herbs_col.count_documents(query)}


@router.get("/by-name/{name}")
def get_herb_by_name(name: str):
    herbs_col = get_collection("herbs")
    herb = herbs_col.find_one({"name": name})
    if not herb:
        raise HTTPException(status_code=404, detail="药物不存在")
    return herb_to_response(herb)


@router.get("/stats/categories")
def get_herb_categories():
    herbs_col = get_collection("herbs")
    pipeline = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    return [{"category": r["_id"], "count": r["count"]} for r in herbs_col.aggregate(pipeline)]


@router.get("/stats/natures")
def get_herb_natures():
    herbs_col = get_collection("herbs")
    pipeline = [{"$group": {"_id": "$nature", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    return [{"nature": r["_id"], "count": r["count"]} for r in herbs_col.aggregate(pipeline)]


@router.get("/stats/meridians")
def get_herb_meridians():
    herbs_col = get_collection("herbs")
    pipeline = [{"$unwind": "$meridians"}, {"$group": {"_id": "$meridians", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    return [{"meridian": r["_id"], "count": r["count"]} for r in herbs_col.aggregate(pipeline)]


@router.get("/{herb_id}/targets")
def get_herb_targets(herb_id: str):
    try:
        oid = ObjectId(herb_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="无效的ID格式")
    herbs_col = get_collection("herbs")
    herb = herbs_col.find_one({"_id": oid})
    if not herb:
        raise HTTPException(status_code=404, detail="药物不存在")
    targets_col = get_collection("herb_targets")
    targets_doc = targets_col.find_one({"herb_name": herb["name"]})
    if targets_doc:
        targets_doc["_id"] = str(targets_doc["_id"])
        return targets_doc
    return {"herb_name": herb["name"], "targets": []}


@router.get("/{herb_id}/formulas")
def get_herb_formulas(herb_id: str, skip: int = 0, limit: int = 20):
    try:
        oid = ObjectId(herb_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="无效的ID格式")
    herbs_col = get_collection("herbs")
    herb = herbs_col.find_one({"_id": oid})
    if not herb:
        raise HTTPException(status_code=404, detail="药物不存在")
    formulas_col = get_collection("formulas")
    cursor = formulas_col.find({"herbs.name": herb["name"]}).sort("frequency", -1).skip(skip).limit(limit)
    formulas = []
    for f in cursor:
        f["_id"] = str(f["_id"])
        formulas.append(f)
    total = formulas_col.count_documents({"herbs.name": herb["name"]})
    return {"herb": herb["name"], "formulas": formulas, "total": total}
