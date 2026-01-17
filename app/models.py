"""
Database models for the SaaS platform
Updated to work with the new database structure
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field
import uuid

# ==================== BASE MODELS ====================
class BaseDocument(BaseModel):
    """Base model for all MongoDB documents"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# ==================== USER MODELS ====================
class UserBase(BaseModel):
    """Base user model"""
    email: EmailStr
    full_name: str
    role: str = "user"
    company_id: Optional[str] = None
    is_active: bool = True

class UserCreate(UserBase):
    """User creation model"""
    password: str

class UserUpdate(BaseModel):
    """User update model"""
    full_name: Optional[str] = None
    role: Optional[str] = None
    company_id: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class UserInDB(BaseDocument, UserBase):
    """User model as stored in database"""
    hashed_password: str
    
    class Config:
        schema_extra = {
            "example": {
                "id": "user_123",
                "email": "john@example.com",
                "full_name": "John Doe",
                "hashed_password": "$2b$12$...",
                "role": "user",
                "company_id": "company_123",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            }
        }

class UserResponse(BaseModel):
    """User response model (without password)"""
    id: str
    email: EmailStr
    full_name: str
    role: str
    company_id: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

# ==================== COMPANY MODELS ====================
class CompanyBase(BaseModel):
    """Base company model"""
    name: str
    slug: str
    description: Optional[str] = None
    industry: Optional[str] = None
    employee_count: int = 0
    manager_count: int = 0
    address: Optional[str] = None
    services: List[str] = []
    owner: Optional[str] = None
    directors: List[str] = []
    founders: List[str] = []

class CompanyCreate(CompanyBase):
    """Company creation model"""
    created_by: str  # User ID

class CompanyUpdate(BaseModel):
    """Company update model"""
    name: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    manager_count: Optional[int] = None
    address: Optional[str] = None
    services: Optional[List[str]] = None
    owner: Optional[str] = None
    directors: Optional[List[str]] = None
    founders: Optional[List[str]] = None

class CompanyInDB(BaseDocument, CompanyBase):
    """Company model as stored in database"""
    created_by: str
    
    class Config:
        schema_extra = {
            "example": {
                "id": "company_123",
                "name": "Acme Corporation",
                "slug": "acme-corporation",
                "description": "A leading tech company",
                "industry": "Technology",
                "employee_count": 500,
                "manager_count": 50,
                "address": "123 Tech Street, San Francisco",
                "services": ["Software Development", "Consulting"],
                "owner": "John Smith",
                "directors": ["Jane Doe", "Bob Johnson"],
                "founders": ["Alice Brown"],
                "created_by": "user_123",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            }
        }

class CompanyResponse(BaseModel):
    """Company response model"""
    id: str
    name: str
    slug: str
    description: Optional[str]
    industry: Optional[str]
    employee_count: int
    manager_count: int
    address: Optional[str]
    services: List[str]
    owner: Optional[str]
    directors: List[str]
    founders: List[str]
    created_by: str
    created_at: datetime
    updated_at: datetime
    form_url: str = ""  # Will be calculated

# ==================== MANAGER MODELS ====================
class ManagerBase(BaseModel):
    """Base manager model"""
    company_id: str
    manager_name: str
    reporting_to: Optional[str] = None
    email: Optional[EmailStr] = None
    department: Optional[str] = None

class ManagerCreate(ManagerBase):
    """Manager creation model"""
    pass

class ManagerUpdate(BaseModel):
    """Manager update model"""
    reporting_to: Optional[str] = None
    email: Optional[EmailStr] = None
    department: Optional[str] = None

class ManagerInDB(BaseDocument, ManagerBase):
    """Manager model as stored in database"""
    total_assessments: int = 0
    category_averages: Dict[str, float] = Field(default_factory=lambda: {
        "trusting": 0.0,
        "tasking": 0.0,
        "tending": 0.0
    })
    category_totals: Dict[str, int] = Field(default_factory=lambda: {
        "trusting": 0,
        "tasking": 0,
        "tending": 0
    })
    confidence_score: int = 0
    first_assessment: Optional[datetime] = None
    last_assessment: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        schema_extra = {
            "example": {
                "id": "manager_123",
                "company_id": "company_123",
                "manager_name": "John Doe",
                "reporting_to": "Jane Smith",
                "email": "john.doe@company.com",
                "department": "Engineering",
                "total_assessments": 25,
                "category_averages": {
                    "trusting": 7.5,
                    "tasking": 8.2,
                    "tending": 6.8
                },
                "category_totals": {
                    "trusting": 1875,
                    "tasking": 2050,
                    "tending": 1700
                },
                "confidence_score": 85,
                "first_assessment": "2024-01-01T00:00:00",
                "last_assessment": "2024-01-15T00:00:00",
                "last_updated": "2024-01-15T00:00:00",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-15T00:00:00"
            }
        }

class ManagerResponse(BaseModel):
    """Manager response model"""
    id: str
    company_id: str
    manager_name: str
    reporting_to: Optional[str]
    email: Optional[str]
    department: Optional[str]
    total_assessments: int
    category_averages: Dict[str, float]
    category_totals: Dict[str, int]
    confidence_score: int
    first_assessment: Optional[datetime]
    last_assessment: Optional[datetime]
    last_updated: datetime
    created_at: datetime
    updated_at: datetime
    percentages: Dict[str, float] = {}  # Will be calculated
    overall_percentage: float = 0.0  # Will be calculated

# ==================== ASSESSMENT MODELS ====================
class AssessmentBase(BaseModel):
    """Base assessment model"""
    company_id: str
    manager_name: str
    respondent_email: Optional[EmailStr] = None
    respondent_role: Optional[str] = None  # peer, subordinate, superior, self

class AssessmentCreate(AssessmentBase):
    """Assessment creation model"""
    answers: Dict[str, str]  # {question_id: answer_value}
    session_id: str

class AssessmentUpdate(BaseModel):
    """Assessment update model"""
    answers: Optional[Dict[str, str]] = None
    category_scores: Optional[Dict[str, int]] = None
    category_averages: Optional[Dict[str, float]] = None
    overall_score: Optional[float] = None

class AssessmentInDB(BaseDocument, AssessmentBase):
    """Assessment model as stored in database"""
    answers: Dict[str, str]
    category_scores: Dict[str, int] = Field(default_factory=lambda: {
        "trusting": 0,
        "tasking": 0,
        "tending": 0
    })
    category_averages: Dict[str, float] = Field(default_factory=lambda: {
        "trusting": 0.0,
        "tasking": 0.0,
        "tending": 0.0
    })
    overall_score: float = 0.0
    submission_time: datetime = Field(default_factory=datetime.utcnow)
    session_id: str
    
    class Config:
        schema_extra = {
            "example": {
                "id": "assessment_123",
                "company_id": "company_123",
                "manager_name": "John Doe",
                "respondent_email": "respondent@example.com",
                "respondent_role": "peer",
                "answers": {
                    "STR_1": "Always",
                    "STR_2": "Sometimes",
                    # ... all 36 questions
                },
                "category_scores": {
                    "trusting": 28,
                    "tasking": 30,
                    "tending": 26
                },
                "category_averages": {
                    "trusting": 7.0,
                    "tasking": 7.5,
                    "tending": 6.5
                },
                "overall_score": 70.0,
                "submission_time": "2024-01-15T10:30:00",
                "session_id": "session_123",
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00"
            }
        }

class AssessmentResponse(BaseModel):
    """Assessment response model"""
    id: str
    company_id: str
    manager_name: str
    respondent_email: Optional[str]
    respondent_role: Optional[str]
    category_scores: Dict[str, int]
    category_averages: Dict[str, float]
    overall_score: float
    submission_time: datetime
    session_id: str
    created_at: datetime
    updated_at: datetime

# ==================== FORM SUBMISSION TRACKING ====================
class FormSubmissionBase(BaseModel):
    """Base form submission tracking model"""
    company_slug: str
    manager_name: str
    respondent_email: Optional[EmailStr] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class FormSubmissionCreate(FormSubmissionBase):
    """Form submission creation model"""
    pass

class FormSubmissionInDB(BaseDocument, FormSubmissionBase):
    """Form submission model as stored in database"""
    status: str = "submitted"  # submitted, processing, completed, failed
    
    class Config:
        schema_extra = {
            "example": {
                "id": "submission_123",
                "company_slug": "acme-corporation",
                "manager_name": "John Doe",
                "respondent_email": "respondent@example.com",
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0...",
                "status": "completed",
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00"
            }
        }

# ==================== LEGACY MODELS (For your existing data) ====================
class LegacyGoogleFormResponse(BaseModel):
    """Legacy Google Form response model"""
    formId: Optional[str] = None
    submittedAt: Optional[str] = None
    manager_name: str
    reporting_to: Optional[str] = None
    raw_manager_name: Optional[str] = None
    raw_reporting_to: Optional[str] = None
    raw_answers: Dict[str, Any] = {}
    processed: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[str] = None

class LegacyManager(BaseModel):
    """Legacy manager model (your existing structure)"""
    manager_name: str
    reporting_to: Optional[str] = None
    category_averages: Optional[Dict[str, float]] = None
    category_totals: Optional[Dict[str, int]] = None
    confidence_score: Optional[int] = None
    first_assessment: Optional[datetime] = None
    last_assessment: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    raw_manager_name: Optional[str] = None
    raw_reporting_to: Optional[str] = None
    score_distribution: Optional[Dict[str, Any]] = None
    total_assessments: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    company_id: str = "legacy_company"  # Added for compatibility

# ==================== QUESTION MODELS ====================
class Question(BaseModel):
    """Question model for assessment form"""
    id: str
    text: str
    type: str  # direct, reconfirmation, reverse
    options: List[str]
    scores: Dict[str, int]
    category: str  # trusting, tasking, tending
    tripod: str  # TRUSTING, TASKING, TENDING
    behavior: str  # e.g., "Honesty, Dependability & Fairness"
    sequence: int  # Order in category

class QuestionCategory(BaseModel):
    """Category of questions"""
    name: str
    description: str
    questions: List[Question]

# ==================== RESPONSE MODELS ====================
class Token(BaseModel):
    """JWT Token response"""
    access_token: str
    token_type: str
    user: UserResponse

class LoginRequest(BaseModel):
    """Login request model"""
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    """Registration request model"""
    email: EmailStr
    full_name: str
    password: str

class DashboardStats(BaseModel):
    """Dashboard statistics model"""
    total_companies: int
    total_managers: int
    total_assessments: int
    companies: List[Dict[str, Any]]

class HealthCheck(BaseModel):
    """Health check response model"""
    status: str
    database: str
    collections: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ==================== EXPORT ALL MODELS ====================
__all__ = [
    # Base
    "BaseDocument",
    
    # Users
    "UserBase", "UserCreate", "UserUpdate", "UserInDB", "UserResponse",
    
    # Companies
    "CompanyBase", "CompanyCreate", "CompanyUpdate", "CompanyInDB", "CompanyResponse",
    
    # Managers
    "ManagerBase", "ManagerCreate", "ManagerUpdate", "ManagerInDB", "ManagerResponse",
    
    # Assessments
    "AssessmentBase", "AssessmentCreate", "AssessmentUpdate", "AssessmentInDB", "AssessmentResponse",
    
    # Form Submissions
    "FormSubmissionBase", "FormSubmissionCreate", "FormSubmissionInDB",
    
    # Legacy
    "LegacyGoogleFormResponse", "LegacyManager",
    
    # Questions
    "Question", "QuestionCategory",
    
    # Responses
    "Token", "LoginRequest", "RegisterRequest", "DashboardStats", "HealthCheck"
]