from pydantic import BaseModel
from typing import Dict, Any, Optional


class FormPayload(BaseModel):
    submittedAt: Optional[str] = None
    formId: Optional[str] = None
    answers: Dict[str, Any]  # {"Question": ["Answer"]}


class SubcategoryMarks(BaseModel):
    subcategory_scores: Dict[str, int] = {}
    subcategory_averages: Dict[str, float] = {}
    subcategory_remarks: Dict[str, Any] = {}


class AssessmentComputedPayload(SubcategoryMarks):
    category_scores: Dict[str, int] = {}
    category_averages: Dict[str, float] = {}
    overall_score: float = 0.0
