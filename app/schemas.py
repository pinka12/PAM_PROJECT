from pydantic import BaseModel
from typing import Dict, Any, Optional


class FormPayload(BaseModel):
    submittedAt: Optional[str] = None
    formId: Optional[str] = None
    answers: Dict[str, Any]  # {"Question": ["Answer"]}
