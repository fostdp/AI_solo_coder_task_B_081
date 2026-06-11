from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class HerbIngredient(BaseModel):
    name: str
    dosage: str
    preparation: Optional[str] = None


class FormulaBase(BaseModel):
    name: str
    dynasty: str
    author: str
    indications: List[str]
    herbs: List[HerbIngredient]
    frequency: int = 1


class FormulaCreate(FormulaBase):
    pass


class Formula(FormulaBase):
    id: str = Field(alias="_id")

    class Config:
        from_attributes = True


class HerbBase(BaseModel):
    name: str
    nature: str
    flavor: List[str]
    meridians: List[str]
    category: str


class Herb(HerbBase):
    id: str = Field(alias="_id")

    class Config:
        from_attributes = True


class DiseaseBase(BaseModel):
    name: str
    category: str
    symptoms: List[str]


class Disease(DiseaseBase):
    id: str = Field(alias="_id")

    class Config:
        from_attributes = True


class AssociationRule(BaseModel):
    antecedent: List[str]
    consequent: List[str]
    support: float
    confidence: float
    lift: float


class CommunityResult(BaseModel):
    community_id: int
    herbs: List[str]
    size: int


class LinkPredictionResult(BaseModel):
    herb_a: str
    herb_b: str
    score: float
    method: str
    known_support: Optional[float] = None


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    size: Optional[float] = None
    color: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


class GraphEdge(BaseModel):
    source: str
    target: str
    label: Optional[str] = None
    weight: Optional[float] = None


class GraphData(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
