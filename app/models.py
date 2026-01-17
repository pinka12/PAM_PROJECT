from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str = "user"
    is_active: bool = True


class CompanyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    owner: Optional[str] = None
    directors: List[str] = Field(default_factory=list)
    founders: List[str] = Field(default_factory=list)


class CompanyResponse(BaseModel):
    id: str
    name: str
    slug: str
    form_url: Optional[str] = None


class ManagerResponse(BaseModel):
    id: str
    manager_name: str
    department: Optional[str] = None
    email: Optional[EmailStr] = None
    total_assessments: int = 0
    category_averages: Dict[str, float] = Field(default_factory=dict)
    confidence_score: int = 0


class AssessmentCreate(BaseModel):
    company_slug: str
    manager_name: str
    reporting_to: Optional[str] = ""
    respondent_email: Optional[EmailStr] = None
    respondent_role: Optional[str] = "anonymous"
    answers: Dict[str, str]
    session_id: Optional[str] = None


class DashboardStats(BaseModel):
    total_companies: int = 0
    total_managers: int = 0
    total_assessments: int = 0
    recent_assessments: int = 0


class HealthCheck(BaseModel):
    status: str
    timestamp: Optional[datetime] = None
    database: Optional[str] = None
    collections: Dict[str, Any] = Field(default_factory=dict)
