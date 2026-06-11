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


class EfficacyRecord(BaseModel):
    formula_name: str
    medical_case: str
    raw_description: str
    sentiment_score: float
    efficacy_grade: int
    days_to_effect: Optional[int] = None
    dosage_regimen: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None


class FormulaEfficacy(BaseModel):
    formula_name: str
    avg_efficacy_score: float
    efficacy_grade_distribution: Dict[int, int]
    total_cases: int
    avg_days_to_effect: float
    case_records: List[EfficacyRecord]
    confidence_interval: Optional[List[float]] = None


class DoseEffectPoint(BaseModel):
    herb_name: str
    dosage_g: float
    avg_efficacy: float
    sample_size: int
    std_error: Optional[float] = None


class DoseEffectCurve(BaseModel):
    herb_name: str
    formula_name: Optional[str] = None
    indication: Optional[str] = None
    points: List[DoseEffectPoint]
    optimal_dose_range: List[float]
    model_type: str
    r_squared: float
    knots: Optional[List[float]] = None


class AdverseReaction(BaseModel):
    reaction_type: str
    severity: str
    symptoms: List[str]
    frequency: Optional[float] = None
    onset_time_hours: Optional[float] = None


class HerbAdverseProfile(BaseModel):
    herb_name: str
    contraindications: List[str]
    toxic_ingredients: List[str]
    adverse_reactions: List[AdverseReaction]
    ld50_mgkg: Optional[float] = None
    max_safe_dose_g: Optional[float] = None
    pregnancy_risk: Optional[str] = None


class RiskHerbPair(BaseModel):
    herb_a: str
    herb_b: str
    risk_level: str
    risk_score: float
    interaction_type: str
    mechanism: str
    evidence_level: str
    references: List[str]


class FormulaRiskAssessment(BaseModel):
    formula_name: str
    overall_risk_level: str
    overall_risk_score: float
    risk_pairs: List[RiskHerbPair]
    individual_risks: Dict[str, HerbAdverseProfile]
    warnings: List[str]
    safe_use_guidance: List[str]


class ClinicalTrialArm(BaseModel):
    treatment_name: str
    treatment_type: str
    sample_size: int
    mean_efficacy: float
    std_efficacy: float
    adverse_event_rate: float


class ClinicalTrial(BaseModel):
    trial_id: str
    title: str
    year: int
    indication: str
    design: str
    arms: List[ClinicalTrialArm]
    total_sample_size: int
    duration_weeks: int
    location: Optional[str] = None
    quality_score: float


class MetaAnalysisResult(BaseModel):
    indication: str
    comparison: str
    pooled_effect_size: float
    ci_95: List[float]
    p_value: float
    i_squared: float
    heterogeneity_p: float
    trials_included: int
    total_patients: int
    forest_plot_data: List[Dict[str, Any]]
    conclusion: str


class NetworkMetaResult(BaseModel):
    indication: str
    treatments_ranked: List[Dict[str, Any]]
    network_edges: List[Dict[str, Any]]
    inconsistency: Optional[float] = None
    league_table: List[List[Any]]
    best_treatment_probability: Dict[str, float]
