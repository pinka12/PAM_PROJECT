print("** 360-DEGREE MANAGER ASSESSMENT SAAS PLATFORM **")
import os
import asyncio
import json
import uuid
import urllib.parse
import io
import base64
import re
import random
import smtplib
import ssl
import textwrap
from email.message import EmailMessage
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Header, HTTPException, Request, Query, BackgroundTasks, Depends, Form, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
import plotly.graph_objects as go
import plotly.io as pio
from dotenv import load_dotenv
from openai import OpenAI
try:
    import cloudinary
    import cloudinary.uploader
except Exception:
    cloudinary = None

# Local imports - Updated for SaaS
from app.db import (
    # Legacy collections (sync)
    raw_responses, managers, reports,
    # New SaaS collections (async)
    async_users, async_companies, async_managers, async_assessments, 
    async_form_submissions, async_raw_responses, async_reports, async_saas_reports,
    # Functions
    create_indexes, check_database_health, migrate_legacy_data
)
from app.processor import (
    process_form_answers,
    normalize_name,
    aggregate_manager_scores,
    get_subcategory_keys,
    SUBCATEGORY_ORDER,
    compute_subcategory_averages,
    build_subcategory_remark_context,
    build_subcategory_prompt_block,
)
from app.aggregator import update_manager_aggregation, migrate_existing_data, get_manager_hierarchy
from app.auth import (
    verify_password, get_password_hash, create_access_token,
    get_current_user, get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES, oauth2_scheme
)
from app.models import (
    UserCreate, UserResponse, CompanyCreate, CompanyResponse,
    ManagerResponse, AssessmentCreate, DashboardStats, HealthCheck
)
from app.reports import build_manager_pdf_report, build_company_pdf_report

load_dotenv()

app = FastAPI(
    title="360Â° Manager Assessment SaaS",
    description="Multi-company manager assessment platform with real-time analytics",
    version="3.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")


def require_admin_user(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    role = current_user.get("role", "")
    if role in ["admin", "superadmin"]:
        return current_user
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    if admin_email and current_user.get("email", "").strip().lower() == admin_email:
        return current_user
    raise HTTPException(status_code=403, detail="Admin access required")

FORM_SECRET = os.getenv("FORM_SECRET", "")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")

@app.get("/")
async def root():
    return RedirectResponse(url="/login")

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

@app.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Login form submission - POST request
@app.post("/login", response_class=HTMLResponse)
async def post_login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        email = email.strip().lower()
        admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        if admin_email and email != admin_email:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Access restricted. Please use the admin email."
            })
        user = await async_users.find_one({"email": email})
        if not user or not verify_password(password, user["hashed_password"]):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Invalid email or password"
            })
        if not user.get("is_active", True):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Account is inactive"
            })
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["id"]},
            expires_delta=access_token_expires
        )
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        return response
    except Exception as e:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": str(e)
        })

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response


# ==================== QUESTION DEFINITIONS ====================
# Complete 36 questions as per your requirements
ASSESSMENT_QUESTIONS = {
    "trusting": [
        {
            "id": "STR_1",
            "text": "Does your manager follow through on commitments in a way that makes you feel you can rely on them?",
            "type": "direct",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "trusting",
            "tripod": "TRUSTING",
            "behavior": "Honesty, Dependability & Fairness",
            "sequence": 1
        },
        {
            "id": "STR_2",
            "text": "Does your manager interact with team members in a way that feels consistent and predictable?",
            "type": "reconfirmation",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "trusting",
            "tripod": "TRUSTING",
            "behavior": "Honesty, Dependability & Fairness",
            "sequence": 2
        },
        {
            "id": "STR_3",
            "text": "Do you often feel unsure about how your manager will respond in similar situations?",
            "type": "reverse",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 3, "Sometimes": 2, "Always": 1},
            "category": "trusting",
            "tripod": "TRUSTING",
            "behavior": "Honesty, Dependability & Fairness",
            "sequence": 3
        },
        {
            "id": "STR_4",
            "text": "Does your manager distribute work based on skills and workload rather than personal preference?",
            "type": "direct",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "trusting",
            "tripod": "TRUSTING",
            "behavior": "Task Delegation Without Bias",
            "sequence": 4
        },
        {
            "id": "STR_5",
            "text": "Does your manager give opportunities to different team members over time, not just a select few?",
            "type": "reconfirmation",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "trusting",
            "tripod": "TRUSTING",
            "behavior": "Task Delegation Without Bias",
            "sequence": 5
        },
        {
            "id": "STR_6",
            "text": "Do you notice that the same people repeatedly receive favourable or easier assignments?",
            "type": "reverse",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 3, "Sometimes": 2, "Always": 1},
            "category": "trusting",
            "tripod": "TRUSTING",
            "behavior": "Task Delegation Without Bias",
            "sequence": 6
        },
        {
            "id": "STR_7",
            "text": "When you are stuck, does your manager make themselves available to help you move forward?",
            "type": "direct",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "trusting",
            "tripod": "TRUSTING",
            "behavior": "Providing Necessary Support",
            "sequence": 7
        },
        {
            "id": "STR_8",
            "text": "Does your manager check if you have the resources or guidance you need to complete your work?",
            "type": "reconfirmation",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "trusting",
            "tripod": "TRUSTING",
            "behavior": "Providing Necessary Support",
            "sequence": 8
        },
        {
            "id": "STR_9",
            "text": "Do you often feel left on your own when facing challenges at work?",
            "type": "reverse",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 3, "Sometimes": 2, "Always": 1},
            "category": "trusting",
            "tripod": "TRUSTING",
            "behavior": "Providing Necessary Support",
            "sequence": 9
        },
        {
            "id": "STR_10",
            "text": "Do you feel comfortable approaching your manager with concerns, ideas, or feedback?",
            "type": "direct",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "trusting",
            "tripod": "TRUSTING",
            "behavior": "Encouraging Open Communication",
            "sequence": 10
        },
        {
            "id": "STR_11",
            "text": "Does your manager respond calmly and constructively when team members speak up?",
            "type": "reconfirmation",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "trusting",
            "tripod": "TRUSTING",
            "behavior": "Encouraging Open Communication",
            "sequence": 11
        },
        {
            "id": "STR_12",
            "text": "Do people in the team hesitate to bring up issues because of how your manager might react?",
            "type": "reverse",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 3, "Sometimes": 2, "Always": 1},
            "category": "trusting",
            "tripod": "TRUSTING",
            "behavior": "Encouraging Open Communication",
            "sequence": 12
        }
    ],
    "tasking": [
        {
            "id": "STA_1",
            "text": "Does your manager clarify what is expected from you in tasks or projects?",
            "type": "direct",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tasking",
            "tripod": "TASKING",
            "behavior": "Defining Roles & Responsibilities",
            "sequence": 1
        },
        {
            "id": "STA_2",
            "text": "Does your manager explain responsibilities in a way that reduces uncertainty?",
            "type": "reconfirmation",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tasking",
            "tripod": "TASKING",
            "behavior": "Defining Roles & Responsibilities",
            "sequence": 2
        },
        {
            "id": "STA_3",
            "text": "Do you frequently have to guess or assume what your manager wants from you?",
            "type": "reverse",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 3, "Sometimes": 2, "Always": 1},
            "category": "tasking",
            "tripod": "TASKING",
            "behavior": "Defining Roles & Responsibilities",
            "sequence": 3
        },
        {
            "id": "STA_4",
            "text": "Does your manager plan work ahead so you know what to prepare for?",
            "type": "direct",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tasking",
            "tripod": "TASKING",
            "behavior": "Planning & Organizing",
            "sequence": 4
        },
        {
            "id": "STA_5",
            "text": "Does your manager organise tasks in a way that prevents last-minute confusion?",
            "type": "reconfirmation",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tasking",
            "tripod": "TASKING",
            "behavior": "Planning & Organizing",
            "sequence": 5
        },
        {
            "id": "STA_6",
            "text": "Do you often receive unclear or sudden instructions that disrupt your workflow?",
            "type": "reverse",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 3, "Sometimes": 2, "Always": 1},
            "category": "tasking",
            "tripod": "TASKING",
            "behavior": "Planning & Organizing",
            "sequence": 6
        },
        {
            "id": "STA_7",
            "text": "Does your manager help the team understand which tasks are most important?",
            "type": "direct",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tasking",
            "tripod": "TASKING",
            "behavior": "Prioritising Tasks",
            "sequence": 7
        },
        {
            "id": "STA_8",
            "text": "Does your manager explain why certain tasks need attention first?",
            "type": "reconfirmation",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tasking",
            "tripod": "TASKING",
            "behavior": "Prioritising Tasks",
            "sequence": 8
        },
        {
            "id": "STA_9",
            "text": "Do you sometimes feel the team works on low-priority tasks while important ones wait?",
            "type": "reverse",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 3, "Sometimes": 2, "Always": 1},
            "category": "tasking",
            "tripod": "TASKING",
            "behavior": "Prioritising Tasks",
            "sequence": 9
        },
        {
            "id": "STA_10",
            "text": "Does your manager check in on progress in a way that helps you stay on track?",
            "type": "direct",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tasking",
            "tripod": "TASKING",
            "behavior": "Monitoring Progress & Providing Assistance",
            "sequence": 10
        },
        {
            "id": "STA_11",
            "text": "Does your manager notice early when tasks are falling behind and step in to support?",
            "type": "reconfirmation",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tasking",
            "tripod": "TASKING",
            "behavior": "Monitoring Progress & Providing Assistance",
            "sequence": 11
        },
        {
            "id": "STA_12",
            "text": "Do delays or problems often go unnoticed by your manager until they become serious?",
            "type": "reverse",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 3, "Sometimes": 2, "Always": 1},
            "category": "tasking",
            "tripod": "TASKING",
            "behavior": "Monitoring Progress & Providing Assistance",
            "sequence": 12
        }
    ],
    "tending": [
        {
            "id": "STE_1",
            "text": "Does your manager take steps to support your professional growth?",
            "type": "direct",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tending",
            "tripod": "TENDING",
            "behavior": "Helping Team Members Learn & Improve",
            "sequence": 1
        },
        {
            "id": "STE_2",
            "text": "Does your manager guide you when you need to develop a new skill?",
            "type": "reconfirmation",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tending",
            "tripod": "TENDING",
            "behavior": "Helping Team Members Learn & Improve",
            "sequence": 2
        },
        {
            "id": "STE_3",
            "text": "Do you feel that learning or improvement is mostly left to you without guidance?",
            "type": "reverse",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 3, "Sometimes": 2, "Always": 1},
            "category": "tending",
            "tripod": "TENDING",
            "behavior": "Helping Team Members Learn & Improve",
            "sequence": 3
        },
        {
            "id": "STE_4",
            "text": "Does your manager encourage the team to work together and support each other?",
            "type": "direct",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tending",
            "tripod": "TENDING",
            "behavior": "Creating a Collaborative Environment",
            "sequence": 4
        },
        {
            "id": "STE_5",
            "text": "Does your manager help resolve friction so the team can collaborate smoothly?",
            "type": "reconfirmation",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tending",
            "tripod": "TENDING",
            "behavior": "Creating a Collaborative Environment",
            "sequence": 5
        },
        {
            "id": "STE_6",
            "text": "Do you notice silos, groupism, or disconnect within the team that your manager does not address?",
            "type": "reverse",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 3, "Sometimes": 2, "Always": 1},
            "category": "tending",
            "tripod": "TENDING",
            "behavior": "Creating a Collaborative Environment",
            "sequence": 6
        },
        {
            "id": "STE_7",
            "text": "When disagreements occur, does your manager help resolve them constructively?",
            "type": "direct",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tending",
            "tripod": "TENDING",
            "behavior": "Resolving Conflicts & Fostering Camaraderie",
            "sequence": 7
        },
        {
            "id": "STE_8",
            "text": "Does your manager help restore positive working relationships after conflicts?",
            "type": "reconfirmation",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tending",
            "tripod": "TENDING",
            "behavior": "Resolving Conflicts & Fostering Camaraderie",
            "sequence": 8
        },
        {
            "id": "STE_9",
            "text": "Do conflicts often linger or resurface because they are not adequately addressed?",
            "type": "reverse",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 3, "Sometimes": 2, "Always": 1},
            "category": "tending",
            "tripod": "TENDING",
            "behavior": "Resolving Conflicts & Fostering Camaraderie",
            "sequence": 9
        },
        {
            "id": "STE_10",
            "text": "Does your manager acknowledge good work in a way that feels meaningful?",
            "type": "direct",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tending",
            "tripod": "TENDING",
            "behavior": "Recognising & Rewarding Achievement",
            "sequence": 10
        },
        {
            "id": "STE_11",
            "text": "Does your manager notice and appreciate improvements or extra effort?",
            "type": "reconfirmation",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 1, "Sometimes": 2, "Always": 3},
            "category": "tending",
            "tripod": "TENDING",
            "behavior": "Recognising & Rewarding Achievement",
            "sequence": 11
        },
        {
            "id": "STE_12",
            "text": "Do you feel that good work often goes unnoticed or is taken for granted?",
            "type": "reverse",
            "options": ["Never", "Sometimes", "Always"],
            "scores": {"Never": 3, "Sometimes": 2, "Always": 1},
            "category": "tending",
            "tripod": "TENDING",
            "behavior": "Recognising & Rewarding Achievement",
            "sequence": 12
        }
    ]
}

def get_randomized_questions():
    """Get questions in random order while maintaining category grouping"""
    randomized = {}
    
    for category in ["trusting", "tasking", "tending"]:
        # Shuffle questions within each category
        questions = ASSESSMENT_QUESTIONS[category].copy()
        random.shuffle(questions)
        randomized[category] = questions
    
    return randomized

def get_sequential_questions():
    """Get questions in sequential order (for reference)"""
    return ASSESSMENT_QUESTIONS

# ==================== AUTHENTICATION MIDDLEWARE ====================
def auth_required(func):
    """Decorator to require authentication"""
    async def wrapper(*args, **kwargs):
        try:
            request = kwargs.get('request')
            if request:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header.split(" ")[1]
                    user = await get_current_user(token)
                    kwargs['current_user'] = user
        except:
            pass
        return await func(*args, **kwargs)
    return wrapper

# ==================== HEALTH & INFO ENDPOINTS ====================
@app.get("/")
async def home(request: Request):
    """Serve login page (default)"""
    # Check if user is already logged in
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            user = await get_current_user(token)
            if user:
                return RedirectResponse(url="/dashboard")
        except:
            pass
    
    # Check localStorage token via query param (for frontend)
    token = request.query_params.get("token")
    if token:
        try:
            user = await get_current_user(token)
            if user:
                response = RedirectResponse(url="/dashboard")
                response.set_cookie(
                    key="access_token",
                    value=token,
                    httponly=True,
                    samesite="lax",
                    max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                    expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                )
                return response
        except:
            pass
    
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/health")
async def health_check():
    """System health check"""
    try:
        health_data = await check_database_health()
        
        if health_data["status"] == "healthy":
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "database": health_data["database"],
                "collections": health_data["collections"],
                "recent_activity": {
                    "last_24h_responses": await async_raw_responses.count_documents({
                        "created_at": {"$gte": datetime.utcnow() - timedelta(hours=24)}
                    }),
                    "total_managers": await async_managers.count_documents({}),
                    "total_users": await async_users.count_documents({}),
                    "total_companies": await async_companies.count_documents({})
                }
            }
        else:
            raise HTTPException(status_code=500, detail=f"Unhealthy: {health_data.get('error', 'Unknown error')}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

# ==================== AUTHENTICATION ENDPOINTS ====================
@app.get("/signup")
async def signup_page(request: Request):
    """Serve signup page"""
    return templates.TemplateResponse("signup.html", {"request": request})

@app.get("/forgot-password")
async def forgot_password_page(request: Request):
    """Serve forgot password page"""
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@app.get("/reset-password")
async def reset_password_page(request: Request, token: str = Query("")):
    """Serve reset password page"""
    return templates.TemplateResponse("reset_password.html", {
        "request": request,
        "token": token
    })

def _get_smtp_settings() -> Dict[str, Any]:
    return {
        "host": os.getenv("SMTP_HOST", ""),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "from_email": os.getenv("SMTP_FROM", ""),
        "use_tls": os.getenv("SMTP_TLS", "true").lower() == "true"
    }

def _send_activation_email(to_email: str, activation_url: str) -> None:
    settings = _get_smtp_settings()
    if not settings["host"] or not settings["from_email"]:
        raise ValueError("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = "Activate your PAM account"
    message["From"] = settings["from_email"]
    message["To"] = to_email
    message.set_content(
        "Welcome to PAM.\n\n"
        f"Activate your account using this link (valid for 24 hours):\n{activation_url}\n\n"
        "If you did not request this, you can ignore this email."
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(settings["host"], settings["port"]) as server:
        if settings["use_tls"]:
            server.starttls(context=context)
        if settings["user"] and settings["password"]:
            server.login(settings["user"], settings["password"])
        server.send_message(message)

def _send_company_report_email(to_email: str, subject: str, body: str) -> None:
    settings = _get_smtp_settings()
    if not settings["host"] or not settings["from_email"]:
        raise ValueError("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings["from_email"]
    message["To"] = to_email
    message.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(settings["host"], settings["port"]) as server:
        if settings["use_tls"]:
            server.starttls(context=context)
        if settings["user"] and settings["password"]:
            server.login(settings["user"], settings["password"])
        server.send_message(message)

@app.post("/api/auth/register")
async def register_user(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...)
):
    """Register new user"""
    try:
        email = email.strip().lower()
        admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        if admin_email and email != admin_email:
            raise HTTPException(status_code=403, detail="Registration disabled. Use admin email only.")
        # Check if user already exists
        existing_user = await async_users.find_one({"email": email})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create user (inactive until email activation)
        user_id = str(uuid.uuid4())
        activation_token = uuid.uuid4().hex
        activation_expires = datetime.utcnow() + timedelta(hours=24)
        user_data = {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "hashed_password": get_password_hash(password),
            "role": "admin",
            "is_active": False,
            "activation_token": activation_token,
            "activation_expires": activation_expires,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        await async_users.insert_one(user_data)

        activation_url = f"{str(request.base_url).rstrip('/')}/activate?token={activation_token}"
        _send_activation_email(email, activation_url)

        return {
            "success": True,
            "message": "Registration successful. Check your email to activate your account."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/login")
async def login_user(
    email: str = Form(...),
    password: str = Form(...)
):
    """Login user"""
    try:
        # Find user
        email = email.strip().lower()
        user = await async_users.find_one({"email": email})
        if not user or not verify_password(password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account not activated. Please check your email for the activation link."
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["id"]},
            expires_delta=access_token_expires
        )
        
        return {
            "success": True,
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user.get("role", "user")
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== DASHBOARD ENDPOINTS ====================
@app.get("/dashboard")
async def dashboard_page(request: Request, current_user = Depends(require_admin_user)):
    """Serve dashboard page"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user
    })

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user = Depends(require_admin_user)):
    """Get dashboard statistics for the user"""
    try:
        # Always show all companies for any authenticated user
        user_companies = await async_companies.find({}).to_list(length=200)
        
        stats = {
            "total_companies": len(user_companies),
            "total_managers": 0,
            "total_assessments": 0,
            "companies": []
        }
        
        for company in user_companies:
            company_id = company["id"]
            
            # Count managers in this company
            manager_count = await async_managers.count_documents({"company_id": company_id})
            
            # Count assessments
            assessment_count = await async_assessments.count_documents({"company_id": company_id})
            
            # Calculate average scores
            pipeline = [
                {"$match": {"company_id": company_id}},
                {"$group": {
                    "_id": None,
                    "avg_trusting": {"$avg": "$category_averages.trusting"},
                    "avg_tasking": {"$avg": "$category_averages.tasking"},
                    "avg_tending": {"$avg": "$category_averages.tending"}
                }}
            ]
            
            avg_result = await async_managers.aggregate(pipeline).to_list(length=1)
            avg_scores = avg_result[0] if avg_result else {
                "avg_trusting": 0,
                "avg_tasking": 0,
                "avg_tending": 0
            }
            
            company_stats = {
                "id": company_id,
                "name": company["name"],
                "slug": company["slug"],
                "description": company.get("description", ""),
                "industry": company.get("industry", ""),
                "employee_count": company.get("employee_count", 0),
                "owner": company.get("owner", ""),
                "address": company.get("address", ""),
                "services": company.get("services", []),
                "directors": company.get("directors", []),
                "founders": company.get("founders", []),
                "contact_emails": company.get("contact_emails", []),
                "contact_phones": company.get("contact_phones", []),
                "manager_count": manager_count,
                "assessment_count": assessment_count,
                "avg_scores": {
                    "trusting": round(avg_scores.get("avg_trusting", 0), 1),
                    "tasking": round(avg_scores.get("avg_tasking", 0), 1),
                    "tending": round(avg_scores.get("avg_tending", 0), 1)
                },
                "created_at": company["created_at"],
                "form_url": f"/form/{company['slug']}"
            }
            
            stats["companies"].append(company_stats)
            stats["total_managers"] += manager_count
            stats["total_assessments"] += assessment_count
        
        return {"success": True, "stats": stats}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/activate")
async def activate_account(request: Request, token: str = Query("")):
    if not token:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Activation failed",
            "message": "Activation token is missing."
        }, status_code=400)

    user = await async_users.find_one({"activation_token": token})
    if not user:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Activation failed",
            "message": "Activation token is invalid."
        }, status_code=400)

    if user.get("activation_expires") and user["activation_expires"] < datetime.utcnow():
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Activation expired",
            "message": "Activation token has expired. Please register again."
        }, status_code=400)

    await async_users.update_one(
        {"id": user["id"]},
        {"$set": {"is_active": True, "updated_at": datetime.utcnow()},
         "$unset": {"activation_token": "", "activation_expires": ""}}
    )

    return templates.TemplateResponse("activation_success.html", {
        "request": request,
        "email": user.get("email", "")
    })

@app.post("/api/auth/forgot")
async def forgot_password(email: str = Form(...)):
    """Generate password reset token"""
    try:
        email = email.strip().lower()
        user = await async_users.find_one({"email": email})
        if not user:
            return {"success": True, "message": "If the email exists, a reset link will be sent."}

        reset_token = str(uuid.uuid4())
        reset_expires = datetime.utcnow() + timedelta(hours=1)
        await async_users.update_one(
            {"email": email},
            {"$set": {
                "reset_token": reset_token,
                "reset_expires": reset_expires
            }}
        )

        return {
            "success": True,
            "message": "Reset token generated. Use the reset link to change your password.",
            "reset_url": f"/reset-password?token={reset_token}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/reset")
async def reset_password(token: str = Form(...), password: str = Form(...)):
    """Reset password using token"""
    try:
        user = await async_users.find_one({"reset_token": token})
        if not user:
            raise HTTPException(status_code=400, detail="Invalid reset token")
        if user.get("reset_expires") and user["reset_expires"] < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Reset token expired")

        await async_users.update_one(
            {"id": user["id"]},
            {"$set": {
                "hashed_password": get_password_hash(password),
                "updated_at": datetime.utcnow()
            },
             "$unset": {"reset_token": "", "reset_expires": ""}}
        )

        return {"success": True, "message": "Password updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def legacy_stats(current_user = Depends(require_admin_user)):
    return await get_dashboard_stats(current_user)

# ==================== COMPANY ENDPOINTS ====================
@app.get("/company/new")
async def new_company_page(request: Request, current_user = Depends(require_admin_user)):
    """Serve new company form"""
    return templates.TemplateResponse("new_company.html", {
        "request": request,
        "user": current_user
    })

@app.post("/api/companies/create")
async def create_company(
    request: Request,
    current_user = Depends(require_admin_user)
):
    """Create new company"""
    try:
        data = await request.json()
        
        # Generate URL slug
        company_name = data.get("name", "").strip()
        if not company_name:
            raise HTTPException(status_code=400, detail="Company name is required")
        slug = company_name.lower().replace(" ", "-").replace("&", "and").replace(",", "")
        slug = ''.join(c for c in slug if c.isalnum() or c == '-')
        
        # Check if slug already exists
        existing_company = await async_companies.find_one({"slug": slug})
        if existing_company:
            slug = f"{slug}-{str(uuid.uuid4())[:8]}"
        
        # Create company
        company_id = str(uuid.uuid4())
        company_data = {
            "id": company_id,
            "name": company_name,
            "slug": slug,
            "description": data.get("description", ""),
            "industry": data.get("industry", ""),
            "employee_count": int(data.get("employee_count", 0)),
            "manager_count": int(data.get("manager_count", 0)),
            "address": data.get("address", ""),
            "services": data.get("services", []),
            "owner": data.get("owner", ""),
            "directors": data.get("directors", []),
            "founders": data.get("founders", []),
            "contact_emails": data.get("contact_emails", []),
            "contact_phones": data.get("contact_phones", []),
            "created_by": current_user["id"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        await async_companies.insert_one(company_data)
        
        return {
            "success": True,
            "message": "Company created successfully",
            "company": {
                "id": company_id,
                "name": company_name,
                "slug": slug,
                "form_url": f"/form/{slug}"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== COMPANY DASHBOARD ====================
@app.get("/company/{company_id}")
async def company_dashboard_page(company_id: str, request: Request, current_user = Depends(require_admin_user)):
    """Serve company dashboard page"""
    company = await async_companies.find_one({"id": company_id})
    if not company:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Company not found",
            "message": "The company does not exist."
        }, status_code=404)
    return templates.TemplateResponse("company_dashboard.html", {
        "request": request,
        "user": current_user,
        "company": company
    })

def _build_form_link(request: Request, company: Dict[str, Any], token: str) -> str:
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/form/{company['slug']}?token={token}"

async def _ensure_company_form_token(company: Dict[str, Any], force_refresh: bool = False) -> Dict[str, Any]:
    now = datetime.utcnow()
    token = company.get("form_token")
    expires = company.get("form_token_expires")

    if not force_refresh and token and expires and expires > now:
        return {"token": token, "expires": expires}

    token = uuid.uuid4().hex
    expires = now + timedelta(hours=24)
    await async_companies.update_one(
        {"id": company["id"]},
        {"$set": {"form_token": token, "form_token_expires": expires, "updated_at": now}}
    )
    return {"token": token, "expires": expires}

@app.get("/api/companies/{company_id}/form-link")
async def company_form_link(
    company_id: str,
    request: Request,
    force: bool = Query(False),
    current_user = Depends(require_admin_user)
):
    company = await async_companies.find_one({"id": company_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    token_info = await _ensure_company_form_token(company, force_refresh=force)
    url = _build_form_link(request, company, token_info["token"])
    return {
        "success": True,
        "url": url,
        "expires_at": token_info["expires"].isoformat()
    }

@app.get("/company/{company_id}/manager/{manager_name}")
async def manager_report_page(company_id: str, manager_name: str, request: Request, current_user = Depends(require_admin_user)):
    """Serve manager report page"""
    company = await async_companies.find_one({"id": company_id})
    if not company:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Company not found",
            "message": "The company does not exist."
        }, status_code=404)
    return templates.TemplateResponse("manager_report.html", {
        "request": request,
        "user": current_user,
        "company": company,
        "manager_name": manager_name
    })

def _build_company_hierarchy(managers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def normalize_name(value: str) -> str:
        return " ".join((value or "").strip().lower().split())

    manager_map: Dict[str, Dict[str, Any]] = {}
    reports_map: Dict[str, List[str]] = {}
    all_names: Dict[str, str] = {}

    for manager in managers:
        raw_name = manager.get("manager_name", "")
        key = normalize_name(raw_name)
        if not key:
            continue
        manager_map[key] = manager
        all_names[key] = raw_name or key
        reports_map.setdefault(key, [])

    for manager in managers:
        manager_name = normalize_name(manager.get("manager_name", ""))
        reporting_to = normalize_name(manager.get("reporting_to", ""))
        if manager_name and reporting_to:
            reports_map.setdefault(reporting_to, []).append(manager_name)
            all_names.setdefault(reporting_to, manager.get("reporting_to", "") or reporting_to)

    roots = []
    for name_key in all_names.keys():
        reporting_to = ""
        if name_key in manager_map:
            reporting_to = normalize_name(manager_map[name_key].get("reporting_to", ""))
        if not reporting_to or reporting_to not in all_names:
            roots.append(name_key)

    def build_node(name_key: str) -> Dict[str, Any]:
        manager = manager_map.get(name_key, {})
        children = [build_node(child) for child in reports_map.get(name_key, [])]
        return {
            "manager": {
                "name": manager.get("manager_name", "") or all_names.get(name_key, ""),
                "reporting_to": manager.get("reporting_to", ""),
                "total_assessments": manager.get("total_assessments", 0),
                "category_averages": manager.get("category_averages", {})
            },
            "direct_reports": children
        }

    return [build_node(root) for root in roots if root]

@app.get("/api/companies/{company_id}/overview")
async def company_overview(company_id: str, current_user = Depends(require_admin_user)):
    """Company overview stats"""
    company = await async_companies.find_one({"id": company_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    manager_count = await async_managers.count_documents({"company_id": company_id})
    assessment_count = await async_assessments.count_documents({"company_id": company_id})

    # Company averages by manager count (each manager contributes equally)
    manager_docs = await async_managers.find(
        {"company_id": company_id},
        {"category_averages": 1}
    ).to_list(length=5000)
    manager_total = 0
    sums = {"trusting": 0.0, "tasking": 0.0, "tending": 0.0}
    for mgr in manager_docs:
        category_scores = mgr.get("category_averages", {}) or {}
        sums["trusting"] += float(category_scores.get("trusting", 0) or 0)
        sums["tasking"] += float(category_scores.get("tasking", 0) or 0)
        sums["tending"] += float(category_scores.get("tending", 0) or 0)
        manager_total += 1

    avg_scores = {}
    if manager_total > 0:
        avg_scores = {
            "avg_trusting": sums["trusting"] / manager_total,
            "avg_tasking": sums["tasking"] / manager_total,
            "avg_tending": sums["tending"] / manager_total,
        }

    if not avg_scores:
        assessment_pipeline = [
            {"$match": {"company_id": company_id}},
            {"$group": {
                "_id": None,
                "avg_trusting": {"$avg": "$category_averages.trusting"},
                "avg_tasking": {"$avg": "$category_averages.tasking"},
                "avg_tending": {"$avg": "$category_averages.tending"}
            }}
        ]
        assessment_result = await async_assessments.aggregate(assessment_pipeline).to_list(length=1)
        avg_scores = assessment_result[0] if assessment_result else {}

    return {
        "success": True,
        "company": {
            "id": company["id"],
            "name": company["name"],
            "slug": company["slug"],
            "description": company.get("description", ""),
            "industry": company.get("industry", ""),
            "owner": company.get("owner", ""),
            "address": company.get("address", ""),
            "services": company.get("services", []),
            "directors": company.get("directors", []),
            "founders": company.get("founders", []),
            "contact_emails": company.get("contact_emails", []),
            "contact_phones": company.get("contact_phones", []),
            "employee_count": company.get("employee_count", 0),
            "manager_count": company.get("manager_count", 0)
        },
        "counts": {
            "managers": manager_count,
            "assessments": assessment_count,
            "employees": company.get("employee_count", 0)
        },
        "averages": {
            "trusting": round(avg_scores.get("avg_trusting", 0) or 0, 1),
            "tasking": round(avg_scores.get("avg_tasking", 0) or 0, 1),
            "tending": round(avg_scores.get("avg_tending", 0) or 0, 1)
        }
    }

@app.post("/api/companies/{company_id}/email-report")
async def email_company_report(company_id: str, request: Request, current_user = Depends(require_admin_user)):
    data = await request.json()
    to_email = (data.get("email") or "").strip().lower()
    if not to_email:
        raise HTTPException(status_code=400, detail="Email is required")

    overview = await company_overview(company_id, current_user)
    company = overview.get("company", {})
    counts = overview.get("counts", {})
    averages = overview.get("averages", {})

    trusting = averages.get("trusting", 0)
    tasking = averages.get("tasking", 0)
    tending = averages.get("tending", 0)
    overall = round((trusting + tasking + tending) / 3, 1)

    dashboard_url = f"{str(request.base_url).rstrip('/')}/company/{company_id}"
    subject = f"Company Report - {company.get('name', 'Company')}"
    body = (
        f"Company Report: {company.get('name', '')}\n"
        f"Industry: {company.get('industry', '-')}\n"
        f"Owner: {company.get('owner', '-')}\n"
        f"Managers: {counts.get('managers', 0)}\n"
        f"Assessments: {counts.get('assessments', 0)}\n\n"
        f"Average Scores\n"
        f"Trusting: {trusting}\n"
        f"Tasking: {tasking}\n"
        f"Tending: {tending}\n"
        f"Overall: {overall}\n\n"
        f"Dashboard: {dashboard_url}\n"
    )

    _send_company_report_email(to_email, subject, body)
    return {"success": True, "message": f"Report sent to {to_email}"}

@app.get("/api/companies/{company_id}/managers")
async def company_managers(company_id: str, current_user = Depends(require_admin_user)):
    """Get managers for a company"""
    managers = await async_managers.find({"company_id": company_id}).sort("manager_name", 1).to_list(length=500)
    for manager in managers:
        if "_id" in manager:
            manager["_id"] = str(manager["_id"])
    return {"success": True, "managers": managers}

@app.get("/api/companies/{company_id}/manager/{manager_name}")
async def company_manager(company_id: str, manager_name: str, current_user = Depends(require_admin_user)):
    manager = await async_managers.find_one({"company_id": company_id, "manager_name": manager_name})
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found")
    if "_id" in manager:
        manager["_id"] = str(manager["_id"])
    return {"success": True, "manager": manager}

@app.get("/api/companies/{company_id}/hierarchy")
async def company_hierarchy(company_id: str, current_user = Depends(require_admin_user)):
    managers = await async_managers.find({"company_id": company_id}).to_list(length=500)
    hierarchy = _build_company_hierarchy(managers)
    return {"success": True, "hierarchy": hierarchy}

@app.post("/api/companies/{company_id}/update")
async def update_company(company_id: str, request: Request, current_user = Depends(require_admin_user)):
    """Update company details"""
    data = await request.json()
    update_fields = {
        "name": data.get("name", "").strip(),
        "description": data.get("description", ""),
        "industry": data.get("industry", ""),
        "employee_count": int(data.get("employee_count", 0)),
        "manager_count": int(data.get("manager_count", 0)),
        "address": data.get("address", ""),
        "owner": data.get("owner", ""),
        "services": data.get("services", []),
        "directors": data.get("directors", []),
        "founders": data.get("founders", []),
        "contact_emails": data.get("contact_emails", []),
        "contact_phones": data.get("contact_phones", []),
        "updated_at": datetime.utcnow()
    }
    await async_companies.update_one({"id": company_id}, {"$set": update_fields})
    return {"success": True}

def _extract_summary_from_report(report_text: str) -> str:
    if not report_text:
        return ""
    lines = [line.strip() for line in report_text.splitlines() if line.strip()]
    if not lines:
        return ""
    for idx, line in enumerate(lines):
        if line.lower().startswith("summary:"):
            value = line.split(":", 1)[1].strip()
            if value:
                return value
            if idx + 1 < len(lines):
                return lines[idx + 1]
    return lines[0]

def _extract_openai_text(response: Any) -> str:
    text = getattr(response, "output_text", "") or ""
    if text:
        return str(text).strip()
    output = getattr(response, "output", None) or []
    collected: List[str] = []
    for item in output:
        content = getattr(item, "content", None) or []
        for chunk in content:
            chunk_text = getattr(chunk, "text", None)
            if chunk_text:
                collected.append(str(chunk_text))
    return "\n".join(collected).strip()

def _normalize_category_averages_scale(category_averages: Dict[str, Any]) -> Dict[str, float]:
    trusting = float(category_averages.get("trusting", 0) or 0)
    tasking = float(category_averages.get("tasking", 0) or 0)
    tending = float(category_averages.get("tending", 0) or 0)
    return {
        "trusting": round(trusting, 2),
        "tasking": round(tasking, 2),
        "tending": round(tending, 2),
    }

def _strip_internal_report_fields(report_doc: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = dict(report_doc or {})
    cleaned.pop("_id", None)
    cleaned.pop("pdf_content_b64", None)
    return cleaned

def _get_openai_client() -> Optional[OpenAI]:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    try:
        return OpenAI(api_key=api_key)
    except Exception:
        return None

def _is_cloudinary_enabled() -> bool:
    if cloudinary is None:
        return False
    cloudinary_url = (os.getenv("CLOUDINARY_URL") or "").strip()
    if cloudinary_url:
        return True
    return bool(
        (os.getenv("CLOUDINARY_CLOUD_NAME") or "").strip()
        and (os.getenv("CLOUDINARY_API_KEY") or "").strip()
        and (os.getenv("CLOUDINARY_API_SECRET") or "").strip()
    )

def _configure_cloudinary() -> None:
    if not _is_cloudinary_enabled():
        return
    cloudinary_url = (os.getenv("CLOUDINARY_URL") or "").strip()
    if cloudinary_url:
        cloudinary.config(cloudinary_url=cloudinary_url, secure=True)
        return
    cloudinary.config(
        cloud_name=(os.getenv("CLOUDINARY_CLOUD_NAME") or "").strip(),
        api_key=(os.getenv("CLOUDINARY_API_KEY") or "").strip(),
        api_secret=(os.getenv("CLOUDINARY_API_SECRET") or "").strip(),
        secure=True,
    )

def _safe_cloudinary_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", (value or "").strip())
    cleaned = cleaned.strip("_")
    return cleaned or "na"

async def _upload_pdf_to_cloudinary(
    pdf_bytes: bytes,
    company_id: str,
    report_scope: str,
    manager_name: str,
) -> Dict[str, Any]:
    if not _is_cloudinary_enabled():
        return {}

    folder = (os.getenv("CLOUDINARY_PDF_FOLDER") or "pam_reports").strip().strip("/")
    public_id = (
        f"{folder}/"
        f"{_safe_cloudinary_part(company_id)}/"
        f"{_safe_cloudinary_part(report_scope)}/"
        f"{_safe_cloudinary_part(manager_name)}"
    )

    def _upload() -> Dict[str, Any]:
        _configure_cloudinary()
        return cloudinary.uploader.upload(
            io.BytesIO(pdf_bytes),
            resource_type="raw",
            public_id=public_id,
            overwrite=True,
            invalidate=True,
            unique_filename=False,
            use_filename=False,
            format="pdf",
        )

    try:
        result = await asyncio.to_thread(_upload)
        return result or {}
    except Exception as exc:
        print(f"Cloudinary upload failed: {exc}")
        return {}

async def _run_openai_prompt(system_text: str, user_text: str, model_name: str) -> str:
    client = _get_openai_client()
    if not client:
        return ""

    def _call_openai() -> str:
        response = client.responses.create(
            model=model_name,
            input=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_text},
            ],
        )
        return _extract_openai_text(response)

    try:
        return (await asyncio.to_thread(_call_openai)).strip()
    except Exception as exc:
        print(f"OpenAI call failed: {exc}")
        return ""

def _extract_first_json_object(raw: str) -> Dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        snippet = text[start : end + 1]
        try:
            parsed = json.loads(snippet)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}

def _coerce_manager_report_json(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    def _arr(key: str) -> List[str]:
        value = data.get(key, [])
        if not isinstance(value, list):
            return []
        out: List[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                out.append(text)
        return out
    return {
        "executive_summary": str(data.get("executive_summary", "")).strip(),
        "behavioral_interpretation": str(data.get("behavioral_interpretation", "")).strip(),
        "strengths": _arr("strengths"),
        "development_areas": _arr("development_areas"),
        "risks": _arr("risks"),
        "coaching_plan": str(data.get("coaching_plan", "")).strip(),
        "action_plan_30_60_90": str(data.get("action_plan_30_60_90", "")).strip(),
    }

def _is_valid_manager_report_json(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    required = [
        "executive_summary",
        "behavioral_interpretation",
        "strengths",
        "development_areas",
        "risks",
        "coaching_plan",
        "action_plan_30_60_90",
    ]
    return all(key in payload for key in required)

async def _generate_manager_report(company_id: str, manager_name: str, force_refresh: bool = False) -> Dict[str, Any]:
    manager = await async_managers.find_one({"company_id": company_id, "manager_name": manager_name})
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found")

    existing = await async_saas_reports.find_one({"company_id": company_id, "manager_name": manager_name})
    api_key = os.getenv("OPENAI_API_KEY", "")

    if existing and not force_refresh:
        report_text_existing = str(existing.get("report_text", "") or "").strip()
        if not report_text_existing and existing.get("ai_analysis"):
            report_text_existing = str(existing.get("ai_analysis", "")).strip()
            existing["report_text"] = report_text_existing
            await async_saas_reports.update_one(
                {"company_id": company_id, "manager_name": manager_name},
                {"$set": {"report_text": report_text_existing, "updated_at": datetime.utcnow()}}
            )

        parsed_existing = _extract_first_json_object(report_text_existing)
        parsed_existing = _coerce_manager_report_json(parsed_existing) if parsed_existing else {}
        has_valid_shape = _is_valid_manager_report_json(parsed_existing)

        should_retry = bool(api_key) and (
            existing.get("source") in ["fallback", "error"] or not has_valid_shape
        )

        updates: Dict[str, Any] = {}
        if has_valid_shape and not existing.get("report_json"):
            updates["report_json"] = parsed_existing
        if not existing.get("summary_text"):
            summary = parsed_existing.get("executive_summary", "") if has_valid_shape else _extract_summary_from_report(report_text_existing)
            updates["summary_text"] = summary
            existing["summary_text"] = summary
        if updates:
            updates["updated_at"] = datetime.utcnow()
            await async_saas_reports.update_one(
                {"company_id": company_id, "manager_name": manager_name},
                {"$set": updates}
            )
            existing.update(updates)

        if not should_retry:
            if "_id" in existing:
                existing["_id"] = str(existing["_id"])
            if has_valid_shape:
                existing["report_json"] = parsed_existing
                existing["report_text"] = json.dumps(parsed_existing, indent=2)
            return existing

    averages = _normalize_category_averages_scale(manager.get("category_averages", {}) or {})
    subcategory_averages = manager.get("subcategory_averages", {})
    subcategory_remarks = manager.get("subcategory_remarks", {})
    subcategory_prompt_block = build_subcategory_prompt_block(subcategory_averages)
    total_assessments = manager.get("total_assessments", 0)
    model_name = (os.getenv("OPENAI_MANAGER_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()

    # ===============================
    # 🔥 ADVANCED DIAGNOSTIC PROMPT
    # ===============================

    system_prompt = (
        "You are a Senior Leadership Diagnostic Expert and Executive Coach with 25+ years of "
        "experience in behavioral analytics, executive performance evaluation, and organizational development. "
        "You produce deep, evidence-based leadership diagnostic reports suitable for HR board review."
    )

    user_prompt = (
        "Analyze the manager using the 3-Dimensional Leadership Framework:\n"
        "1. Trusting (psychological safety, delegation, transparency)\n"
        "2. Tasking (execution discipline, accountability, performance drive)\n"
        "3. Tending (people development, empathy, coaching ability)\n\n"

        "SUBCATEGORY ZONE CLASSIFICATION RULES:\n"
        "🔴 RED (3–5): Behavioral risk zone; consistent weakness or credibility gap.\n"
        "🟠 AMBER (6–7): Functional but inconsistent; situational leadership maturity.\n"
        "🟢 GREEN (8–9): Demonstrated strength; reliable and visible capability.\n\n"

        "MANDATORY MICRO ANALYSIS REQUIREMENTS:\n"
        "- Classify each subcategory into RED/AMBER/GREEN.\n"
        "- Detect repeated RED clusters and interpret systemic pattern.\n"
        "- Cross-correlate subcategory patterns with main category scores.\n"
        "- Identify imbalance across Trusting, Tasking, Tending.\n"
        "- Assign Leadership Archetype based on score pattern.\n"
        "- Interpret behavioral implications; DO NOT restate raw scores.\n"
        "- Use qualitative remarks as behavioral evidence.\n"
        "- Provide business impact insights and leadership risk projection.\n\n"

        "Return STRICTLY valid JSON in this exact structure:\n"
        "{\n"
        '  "executive_summary": "",\n'
        '  "behavioral_interpretation": "",\n'
        '  "strengths": [],\n'
        '  "development_areas": [],\n'
        '  "risks": [],\n'
        '  "coaching_plan": "",\n'
        '  "action_plan_30_60_90": ""\n'
        "}\n\n"

        f"Manager Name: {manager_name}\n"
        f"Total Assessments: {total_assessments}\n\n"

        "MAIN CATEGORY SCORES:\n"
        f"Trusting: {averages.get('trusting', 0)}\n"
        f"Tasking: {averages.get('tasking', 0)}\n"
        f"Tending: {averages.get('tending', 0)}\n\n"

        "SUBCATEGORY AVERAGES:\n"
        f"{subcategory_prompt_block}\n\n"

        "SUBCATEGORY REMARKS:\n"
        f"{json.dumps(subcategory_remarks, default=str)}\n\n"

        "Ensure deep diagnostic reasoning and executive-level professionalism."
    )

    if not api_key:
        report_json = {
            "executive_summary": "OpenAI API key not configured.",
            "behavioral_interpretation": "OpenAI API key not configured.",
            "strengths": [],
            "development_areas": [],
            "risks": [],
            "coaching_plan": "OpenAI API key not configured.",
            "action_plan_30_60_90": "OpenAI API key not configured."
        }
        summary_text = report_json["executive_summary"]
        report_text = json.dumps(report_json, indent=2)
        source = "fallback"

    else:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)

            report_json = {}

            try:
                response = client.responses.create(
                    model=model_name,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.5
                )
                report_text_raw = _extract_openai_text(response)
                report_json = _extract_first_json_object(report_text_raw)
            except Exception:
                report_json = {}

            if not _is_valid_manager_report_json(report_json):
                chat_response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.5,
                    response_format={"type": "json_object"}
                )
                chat_text = (chat_response.choices[0].message.content or "").strip()
                report_json = _extract_first_json_object(chat_text)

            if not _is_valid_manager_report_json(report_json):
                raise ValueError("Model did not return valid manager report JSON")

            report_json = _coerce_manager_report_json(report_json)
            report_text = json.dumps(report_json, indent=2)

            summary_text = report_json.get("executive_summary", "")
            source = "openai"

        except Exception as e:
            report_json = {
                "executive_summary": "Unable to generate report.",
                "behavioral_interpretation": str(e),
                "strengths": [],
                "development_areas": [],
                "risks": [],
                "coaching_plan": "Please retry later.",
                "action_plan_30_60_90": "Please retry later."
            }
            summary_text = report_json["executive_summary"]
            report_text = json.dumps(report_json, indent=2)
            source = "error"

    report_doc = {
        "company_id": company_id,
        "manager_name": manager_name,
        "summary_text": summary_text,
        "report_text": report_text,
        "report_json": report_json,
        "ai_analysis": report_text,
        "source": source,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    await async_saas_reports.update_one(
        {"company_id": company_id, "manager_name": manager_name},
        {"$set": report_doc},
        upsert=True
    )

    return report_doc

async def _generate_company_owner_report(company_id: str, force_refresh: bool = False) -> Dict[str, Any]:
    company = await async_companies.find_one({"id": company_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    owner_key = "__COMPANY_OWNER__"
    query = {"company_id": company_id, "manager_name": owner_key}
    existing = await async_saas_reports.find_one(query)
    if existing and not force_refresh:
        existing_report_text = str(existing.get("report_text", "")).strip() or str(existing.get("ai_analysis", "")).strip()
        if existing_report_text:
            existing["report_text"] = existing_report_text
            return _strip_internal_report_fields(existing)

    manager_docs = await async_managers.find({"company_id": company_id}).sort("manager_name", 1).to_list(length=5000)
    overview_weight = {"trusting": 0.0, "tasking": 0.0, "tending": 0.0}
    total_responses = 0.0
    manager_lines: List[str] = []
    for mgr in manager_docs:
        count = float(mgr.get("total_assessments", 0) or 0)
        averages = _normalize_category_averages_scale(mgr.get("category_averages", {}) or {})
        if count > 0:
            overview_weight["trusting"] += averages["trusting"] * count
            overview_weight["tasking"] += averages["tasking"] * count
            overview_weight["tending"] += averages["tending"] * count
            total_responses += count
        manager_lines.append(
            f"- {mgr.get('manager_name', '')} | reports: {int(count)} | "
            f"trusting {averages['trusting']:.2f}, tasking {averages['tasking']:.2f}, tending {averages['tending']:.2f}"
        )

    company_averages = {
        "trusting": round(overview_weight["trusting"] / total_responses, 2) if total_responses else 0.0,
        "tasking": round(overview_weight["tasking"] / total_responses, 2) if total_responses else 0.0,
        "tending": round(overview_weight["tending"] / total_responses, 2) if total_responses else 0.0,
    }
    model_name = (os.getenv("OPENAI_COMPANY_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
    company_prompt = textwrap.dedent(
        f"""
        You are an experienced leadership consultant writing a company-wide consolidated report.
        Use the manager-level score data below and produce:
        1) Executive summary
        2) Organization-level strengths
        3) Systemic risk themes
        4) Manager cohort observations
        5) 90-day company action plan with measurable outcomes

        Company: {company.get("name", "")}
        Total Managers: {len(manager_docs)}
        Total Responses: {int(total_responses)}
        Weighted Company Averages (0-10): {json.dumps(company_averages)}

        Manager summaries:
        {chr(10).join(manager_lines)}
        """
    ).strip()
    report_text = await _run_openai_prompt(
        "You write objective, practical consulting reports for leadership teams.",
        company_prompt,
        model_name,
    )
    if not report_text:
        report_text = (
            f"Company Leadership Consolidated Report\n\n"
            f"Company: {company.get('name', '')}\n"
            f"Managers assessed: {len(manager_docs)}\n"
            f"Weighted scores (0-10): Trusting {company_averages['trusting']}, "
            f"Tasking {company_averages['tasking']}, Tending {company_averages['tending']}.\n"
            f"\nDetailed narrative could not be generated from AI at this moment."
        )

    now = datetime.utcnow()
    report_doc = {
        "id": str(uuid.uuid4()),
        "company_id": company_id,
        "manager_name": owner_key,
        "report_scope": "company_owner",
        "report_text": report_text,
        "ai_analysis": report_text,
        "model_name": model_name,
        "generated_at": now,
        "company_averages": company_averages,
        "manager_count": len(manager_docs),
        "response_count": int(total_responses),
        "updated_at": now,
    }
    await async_saas_reports.update_one(
        query,
        {"$set": report_doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    saved = await async_saas_reports.find_one(query)
    return _strip_internal_report_fields(saved or report_doc)

async def _save_pdf_in_report(
    query: Dict[str, Any],
    filename: str,
    pdf_bytes: bytes,
    company_id: str,
    report_scope: str,
    manager_name: str,
) -> Dict[str, Any]:
    now = datetime.utcnow()
    cloudinary_result = await _upload_pdf_to_cloudinary(
        pdf_bytes=pdf_bytes,
        company_id=company_id,
        report_scope=report_scope,
        manager_name=manager_name,
    )
    cloudinary_url = str(cloudinary_result.get("secure_url", "") or "").strip()

    set_payload = {
        "pdf_filename": filename,
        "pdf_mime": "application/pdf",
        "pdf_size_bytes": len(pdf_bytes),
        "pdf_generated_at": now,
        "updated_at": now,
    }
    if cloudinary_url:
        set_payload.update(
            {
                "pdf_storage": "cloudinary",
                "cloudinary_public_id": cloudinary_result.get("public_id"),
                "cloudinary_version": cloudinary_result.get("version"),
                "cloudinary_secure_url": cloudinary_url,
            }
        )
    else:
        set_payload.update(
            {
                "pdf_storage": "db_fallback",
                "pdf_content_b64": base64.b64encode(pdf_bytes).decode("ascii"),
            }
        )

    await async_saas_reports.update_one(
        query,
        {
            "$set": set_payload,
            "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now},
        },
        upsert=True,
    )
    return {
        "cloudinary_url": cloudinary_url,
        "storage": set_payload.get("pdf_storage", ""),
    }

@app.get("/api/companies/{company_id}/manager/{manager_name}/report")
async def manager_report(
    company_id: str,
    manager_name: str,
    force: bool = Query(False),
    current_user = Depends(require_admin_user),
):
    report_doc = await _generate_manager_report(company_id, manager_name, force_refresh=force)
    return {"success": True, "report": report_doc}

@app.get("/api/companies/{company_id}/manager/{manager_name}/report.pdf")
async def manager_report_pdf(
    company_id: str,
    manager_name: str,
    force: bool = Query(False),
    current_user = Depends(require_admin_user),
):
    report_query = {"company_id": company_id, "manager_name": manager_name}
    existing_report = await async_saas_reports.find_one(report_query)
    existing_url = str((existing_report or {}).get("cloudinary_secure_url", "") or "").strip()
    if existing_url and not force:
        return RedirectResponse(url=existing_url, status_code=307)

    manager = await async_managers.find_one({"company_id": company_id, "manager_name": manager_name})
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found")
    company = await async_companies.find_one({"id": company_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    report_doc = await _generate_manager_report(company_id, manager_name)

    buffer = io.BytesIO()
    build_manager_pdf_report(buffer, company, manager_name, manager, report_doc)
    pdf_bytes = buffer.getvalue()
    filename = f"{manager_name}_report.pdf".replace(" ", "_")
    save_result = await _save_pdf_in_report(
        report_query,
        filename,
        pdf_bytes,
        company_id=company_id,
        report_scope="manager",
        manager_name=manager_name,
    )
    cloudinary_url = str(save_result.get("cloudinary_url", "") or "").strip()
    if cloudinary_url:
        return RedirectResponse(url=cloudinary_url, status_code=307)

    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)

@app.get("/api/companies/{company_id}/report.pdf")
async def company_owner_report_pdf(
    company_id: str,
    force: bool = Query(False),
    current_user = Depends(require_admin_user)
):
    report_query = {"company_id": company_id, "manager_name": "__COMPANY_OWNER__"}
    existing_report = await async_saas_reports.find_one(report_query)
    existing_url = str((existing_report or {}).get("cloudinary_secure_url", "") or "").strip()
    if existing_url and not force:
        return RedirectResponse(url=existing_url, status_code=307)

    company = await async_companies.find_one({"id": company_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    overview = await company_overview(company_id, current_user)
    manager_docs = await async_managers.find({"company_id": company_id}).sort("manager_name", 1).to_list(length=5000)
    hierarchy = _build_company_hierarchy(manager_docs)
    report_doc = await _generate_company_owner_report(company_id, force_refresh=force)

    buffer = io.BytesIO()
    build_company_pdf_report(buffer, company, overview, hierarchy, manager_docs, report_doc)
    pdf_bytes = buffer.getvalue()
    filename = f"{company.get('name', 'company')}_owner_report.pdf".replace(" ", "_")
    save_result = await _save_pdf_in_report(
        report_query,
        filename,
        pdf_bytes,
        company_id=company_id,
        report_scope="company_owner",
        manager_name="__COMPANY_OWNER__",
    )
    cloudinary_url = str(save_result.get("cloudinary_url", "") or "").strip()
    if cloudinary_url:
        return RedirectResponse(url=cloudinary_url, status_code=307)

    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)

@app.get("/api/companies/{company_id}/report")
async def company_owner_report(
    company_id: str,
    force: bool = Query(False),
    current_user = Depends(require_admin_user)
):
    report_doc = await _generate_company_owner_report(company_id, force_refresh=force)
    return {"success": True, "report": report_doc}

# ==================== ASSESSMENT FORM ENDPOINTS ====================
@app.get("/form/{company_slug}")
async def assessment_form(company_slug: str, request: Request, token: str = Query("")):
    """Serve assessment form for a company with RANDOMIZED questions"""
    try:
        # Get company
        company = await async_companies.find_one({"slug": company_slug})
        if not company:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Company not found",
                "message": "The company you're looking for doesn't exist or has been removed."
            })
        
        # Validate access token (24h link)
        token_info = await _ensure_company_form_token(company, force_refresh=False)
        if not token or token != token_info["token"] or token_info["expires"] <= datetime.utcnow():
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Invalid or Expired Link",
                "message": "This assessment link has expired. Please request a new link from the administrator."
            }, status_code=403)
        
        # Get managers for this company
        company_managers = await async_managers.find(
            {"company_id": company["id"]},
            {"manager_name": 1, "department": 1, "email": 1}
        ).to_list(length=100)
        
        # Generate session ID for this form submission
        session_id = str(uuid.uuid4())
        
        # Get randomized questions
        randomized_questions = get_randomized_questions()
        
        return templates.TemplateResponse("assessment_form.html", {
            "request": request,
            "company": company,
            "managers": company_managers,
            "questions": randomized_questions,
            "session_id": session_id,
            "total_questions": 36,
            "form_token": token
        })
        
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Server Error",
            "message": str(e)
        })

@app.get("/api/form/questions/{company_slug}")
async def get_form_questions(company_slug: str):
    """Get randomized questions for a company form"""
    try:
        # Verify company exists
        company = await async_companies.find_one({"slug": company_slug})
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Get randomized questions
        randomized_questions = get_randomized_questions()
        
        # Get managers for dropdown
        company_managers = await async_managers.find(
            {"company_id": company["id"]},
            {"manager_name": 1, "department": 1}
        ).to_list(length=100)
        
        return {
            "success": True,
            "company": {
                "id": company["id"],
                "name": company["name"],
                "slug": company["slug"]
            },
            "managers": company_managers,
            "questions": randomized_questions,
            "session_id": str(uuid.uuid4()),
            "total_questions": 36
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== FORM SUBMISSION ENDPOINT ====================
@app.post("/api/submit-assessment")
async def submit_assessment(
    request: Request,
    background_tasks: BackgroundTasks
):
    """Handle assessment form submission (Supports 1000+ parallel requests)"""
    try:
        data = await request.json()
        
        company_slug = data.get("company_slug")
        manager_name = data.get("manager_name")
        reporting_to = data.get("reporting_to", "")
        respondent_email = data.get("respondent_email", "")
        respondent_role = data.get("respondent_role", "anonymous")
        answers = data.get("answers", {})
        session_id = data.get("session_id", str(uuid.uuid4()))
        form_token = data.get("form_token", "")
        
        # Validate required fields
        if not manager_name:
            raise HTTPException(status_code=400, detail="Manager name is required")
        
        # Get company
        company = await async_companies.find_one({"slug": company_slug})
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        # Validate link token
        token_info = await _ensure_company_form_token(company, force_refresh=False)
        if not form_token or form_token != token_info["token"] or token_info["expires"] <= datetime.utcnow():
            raise HTTPException(status_code=403, detail="Assessment link expired or invalid")
        
        # Check for duplicate submission (prevent spam)
        existing_response = await async_assessments.find_one({
            "company_id": company["id"],
            "session_id": session_id
        })
        
        if existing_response:
            raise HTTPException(status_code=400, detail="Duplicate submission detected")
        
        # Calculate scores based on answers
        category_scores = {"trusting": 0, "tasking": 0, "tending": 0}
        question_count = {"trusting": 0, "tasking": 0, "tending": 0}
        subcategory_keys = get_subcategory_keys()
        subcategory_scores, subcategory_counts = ({k: 0 for k in subcategory_keys}, {k: 0 for k in subcategory_keys})
        
        for question_id, answer in answers.items():
            # Determine category from question ID
            if question_id.startswith("STR"):
                category = "trusting"
            elif question_id.startswith("STA"):
                category = "tasking"
            elif question_id.startswith("STE"):
                category = "tending"
            else:
                continue
            
            # Find the question to get scoring rules
            question = None
            for cat_questions in ASSESSMENT_QUESTIONS.values():
                for q in cat_questions:
                    if q["id"] == question_id:
                        question = q
                        break
                if question:
                    break
            
            if question:
                score = question["scores"].get(answer, 0)
                category_scores[category] += score
                question_count[category] += 1
                behavior = question.get("behavior", "")
                if behavior in subcategory_scores:
                    subcategory_scores[behavior] += score
                    subcategory_counts[behavior] += 1
        
        # Category marks are kept as raw obtained marks (max 36 per category).
        category_averages = {}
        for category in ["trusting", "tasking", "tending"]:
            if question_count[category] > 0:
                category_averages[category] = round(float(category_scores[category]), 2)
            else:
                category_averages[category] = 0.0
        subcategory_averages = compute_subcategory_averages(subcategory_scores, subcategory_counts)
        subcategory_remarks = build_subcategory_remark_context(subcategory_averages)
        
        # Calculate overall score (0-100)
        max_score_per_category = 3 * 12  # 3 points per question * 12 questions
        total_score = sum(category_scores.values())
        max_total_score = max_score_per_category * 3
        overall_score = round((total_score / max_total_score) * 100, 2) if max_total_score > 0 else 0
        
        # Store response
        response_id = str(uuid.uuid4())
        response_data = {
            "id": response_id,
            "company_id": company["id"],
            "company_slug": company_slug,
            "manager_name": manager_name,
            "reporting_to": reporting_to,
            "respondent_email": respondent_email,
            "respondent_role": respondent_role,
            "answers": answers,
            "category_scores": category_scores,
            "category_averages": category_averages,
            "subcategory_scores": subcategory_scores,
            "subcategory_averages": subcategory_averages,
            "subcategory_remarks": subcategory_remarks,
            "overall_score": overall_score,
            "submission_time": datetime.utcnow(),
            "session_id": session_id,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        await async_assessments.insert_one(response_data)
        
        # Track form submission
        await async_form_submissions.insert_one({
            "id": str(uuid.uuid4()),
            "company_slug": company_slug,
            "manager_name": manager_name,
            "respondent_email": respondent_email,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "status": "completed",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        
        # Update manager aggregation in background
        background_tasks.add_task(update_manager_aggregation_saas, company["id"], manager_name)
        
        return {
            "success": True,
            "message": "Assessment submitted successfully",
            "response_id": response_id,
            "scores": category_averages,
            "subcategory_averages": subcategory_averages,
            "overall_score": overall_score,
            "submission_time": datetime.utcnow().isoformat(),
            "thank_you_url": f"/form/{company_slug}/thank-you?session={session_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"âŒ Error submitting assessment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/form/{company_slug}/thank-you")
async def thank_you_page(company_slug: str, request: Request, session: str = Query(None)):
    """Thank you page after form submission"""
    try:
        company = await async_companies.find_one({"slug": company_slug})
        if not company:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Company not found"
            })
        
        return templates.TemplateResponse("thank_you.html", {
            "request": request,
            "company": company,
            "session_id": session
        })
        
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": str(e)
        })

# ==================== MANAGER AGGREGATION (SAAS) ====================
async def update_manager_aggregation_saas(company_id: str, manager_name: str):
    """Update manager's aggregated scores for SaaS"""
    try:
        # Get all responses for this manager
        pipeline = [
            {"$match": {
                "company_id": company_id,
                "manager_name": manager_name
            }},
            {"$group": {
                "_id": None,
                "total_assessments": {"$sum": 1},
                "trusting_sum": {"$sum": "$category_scores.trusting"},
                "tasking_sum": {"$sum": "$category_scores.tasking"},
                "tending_sum": {"$sum": "$category_scores.tending"},
                "first_assessment": {"$min": "$submission_time"},
                "last_assessment": {"$max": "$submission_time"}
            }}
        ]
        
        result = await async_assessments.aggregate(pipeline).to_list(length=1)
        
        if result:
            agg = result[0]
            total_assessments = agg["total_assessments"]
            latest_assessment = await async_assessments.find_one(
                {"company_id": company_id, "manager_name": manager_name},
                sort=[("submission_time", -1)]
            )
            reporting_to = ""
            if latest_assessment:
                reporting_to = latest_assessment.get("reporting_to", "")
            
            # Calculate category totals
            category_totals = {
                "trusting": agg["trusting_sum"],
                "tasking": agg["tasking_sum"],
                "tending": agg["tending_sum"]
            }

            # Calculate confidence score based on number of assessments
            confidence_score = min(total_assessments * 5, 100)

            subcategory_keys = get_subcategory_keys()
            subcategory_totals = {k: 0 for k in subcategory_keys}
            subcategory_average_sums = {k: 0.0 for k in subcategory_keys}
            assessment_docs = await async_assessments.find(
                {"company_id": company_id, "manager_name": manager_name},
                {"id": 1, "submission_time": 1, "category_scores": 1, "subcategory_scores": 1, "overall_score": 1}
            ).sort("submission_time", 1).to_list(length=10000)
            assessment_summaries = []
            for index, assessment in enumerate(assessment_docs, start=1):
                assessment_subcategory_scores = assessment.get("subcategory_scores", {}) or {}
                assessment_category_scores = assessment.get("category_scores", {}) or {}
                for behavior in subcategory_totals.keys():
                    subcategory_totals[behavior] += assessment_subcategory_scores.get(behavior, 0)
                    # Average each behavior by assessment count (raw 0-9 marks).
                    subcategory_average_sums[behavior] += float(assessment_subcategory_scores.get(behavior, 0) or 0)
                assessment_summaries.append({
                    "sequence": index,
                    "response_id": assessment.get("id", ""),
                    "submitted_at": assessment.get("submission_time"),
                    # Explicit per-response marks for DB cross-check
                    "category_marks": assessment_category_scores,
                    "subcategory_marks": assessment_subcategory_scores,
                    # Backward-compatible aliases
                    "category_totals": assessment_category_scores,
                    "subcategory_totals": assessment_subcategory_scores,
                    "overall_score": assessment.get("overall_score", 0)
                })
            subcategory_averages = {
                behavior: round(total / total_assessments, 2) if total_assessments else 0.0
                for behavior, total in subcategory_average_sums.items()
            }
            category_averages = {
                "trusting": round(sum(subcategory_averages.get(b, 0.0) for b in SUBCATEGORY_ORDER["trusting"]), 2),
                "tasking": round(sum(subcategory_averages.get(b, 0.0) for b in SUBCATEGORY_ORDER["tasking"]), 2),
                "tending": round(sum(subcategory_averages.get(b, 0.0) for b in SUBCATEGORY_ORDER["tending"]), 2),
            }
            subcategory_remarks = build_subcategory_remark_context(subcategory_averages)
            
            # Update or create manager record
            manager_data = {
                "company_id": company_id,
                "manager_name": manager_name,
                "reporting_to": reporting_to,
                "total_assessments": total_assessments,
                "category_averages": category_averages,
                "category_totals": category_totals,
                "subcategory_averages": subcategory_averages,
                "subcategory_totals": subcategory_totals,
                "subcategory_remarks": subcategory_remarks,
                "assessment_summaries": assessment_summaries,
                "confidence_score": confidence_score,
                "first_assessment": agg["first_assessment"],
                "last_assessment": agg["last_assessment"],
                "last_updated": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Check if manager exists
            existing_manager = await async_managers.find_one({
                "company_id": company_id,
                "manager_name": manager_name
            })
            
            if existing_manager:
                await async_managers.update_one(
                    {"company_id": company_id, "manager_name": manager_name},
                    {"$set": manager_data}
                )
            else:
                manager_data["id"] = str(uuid.uuid4())
                manager_data["created_at"] = datetime.utcnow()
                await async_managers.insert_one(manager_data)
            
            print(f"âœ… Updated manager aggregation: {manager_name} ({total_assessments} assessments)")
            
    except Exception as e:
        print(f"âŒ Error updating manager aggregation: {e}")

# ==================== LEGACY ENDPOINTS ====================
@app.post("/webhooks/google-form")
async def google_form_webhook(
    request: Request, 
    x_form_secret: str = Header(default=""),
    background_tasks: BackgroundTasks = None
):
    """Handle Google Form submissions (legacy support)"""
    if x_form_secret != FORM_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        raw = await request.json()
        answers = raw.get("answers", {})
        
        # Process scoring using existing processor
        processed = process_form_answers(answers)
        
        # Extract manager info
        manager_info = processed.get("manager_info", {})
        manager_name = manager_info.get("manager_name", "").strip()
        reporting_to = manager_info.get("reporting_to", "").strip()
        
        if not manager_name:
            raise HTTPException(status_code=400, detail="Manager name not found in form")
        
        # Store raw response
        doc = {
            "formId": raw.get("formId"),
            "submittedAt": raw.get("submittedAt"),
            "manager_name": manager_name,
            "reporting_to": reporting_to,
            "raw_manager_name": manager_info.get("raw_manager_name", ""),
            "raw_reporting_to": manager_info.get("raw_reporting_to", ""),
            "raw_answers": answers,
            "processed": processed,
            "created_at": datetime.utcnow(),
            "processed_at": datetime.utcnow().isoformat()
        }
        
        result = raw_responses.insert_one(doc)
        
        # REAL-TIME AGGREGATION in background
        background_tasks.add_task(update_manager_aggregation, manager_name)
        
        return {
            "ok": True,
            "message": "Form processed successfully",
            "response_id": str(result.inserted_id),
            "manager": manager_name,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"âŒ Error processing Google Form: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== VISUALIZATION FUNCTIONS ====================
def create_triangular_chart(manager_data: dict, company_avg: dict = None) -> str:
    """Create triangular radar chart for manager's scores"""
    categories = ['Trusting', 'Tasking', 'Tending']
    
    # Get manager scores
    trusting = min(manager_data.get("category_averages", {}).get("trusting", 0), 10)
    tasking = min(manager_data.get("category_averages", {}).get("tasking", 0), 10)
    tending = min(manager_data.get("category_averages", {}).get("tending", 0), 10)
    
    # Create triangular radar chart
    fig = go.Figure()
    
    # Manager trace
    fig.add_trace(go.Scatterpolar(
        r=[trusting, tasking, tending, trusting],
        theta=categories + [categories[0]],
        fill='toself',
        fillcolor='rgba(102, 126, 234, 0.3)',
        line=dict(color='rgb(102, 126, 234)', width=3),
        name='Manager Scores',
        hovertemplate='<b>%{theta}</b><br>Score: %{r:.1f}/10<extra></extra>'
    ))
    
    # Company average trace (if provided)
    if company_avg:
        fig.add_trace(go.Scatterpolar(
            r=[
                company_avg.get("avg_trusting", 0),
                company_avg.get("avg_tasking", 0),
                company_avg.get("avg_tending", 0),
                company_avg.get("avg_trusting", 0)
            ],
            theta=categories + [categories[0]],
            line=dict(color='rgb(200, 200, 200)', width=2, dash='dash'),
            name='Company Average',
            hovertemplate='<b>%{theta}</b><br>Company Avg: %{r:.1f}/10<extra></extra>'
        ))
    
    # Update layout
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 10],
                tickfont=dict(size=10),
                tickvals=[0, 2, 4, 6, 8, 10],
                ticktext=['0', '2', '4', '6', '8', '10']
            ),
            angularaxis=dict(
                tickfont=dict(size=12),
                rotation=90,
                direction="clockwise"
            ),
            bgcolor='white'
        ),
        title=dict(
            text="360Â° Assessment Triangle",
            font=dict(size=16),
            x=0.5
        ),
        showlegend=True,
        legend=dict(
            x=0.8,
            y=0.1
        ),
        height=400,
        margin=dict(t=50, b=50, l=50, r=50)
    )
    
    return fig.to_json()

# ==================== ERROR HANDLERS ====================
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "error": "Page Not Found",
        "message": "The page you're looking for doesn't exist."
    }, status_code=404)

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "error": "Internal Server Error",
        "message": "An unexpected error occurred. Please try again later."
    }, status_code=500)

# ==================== STARTUP EVENT ====================
@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    print("ðŸš€ 360Â° Manager Assessment SaaS Platform starting up...")
    print(f"ðŸ“Š Database: {raw_responses.database.name}")
    
    # Create indexes
    create_indexes()
    
    # Check database health
    health = await check_database_health()
    if health["status"] == "healthy":
        print("âœ… Database connection: Healthy")
    else:
        print(f"âš ï¸  Database connection: {health.get('error', 'Unknown error')}")
    
    print("âœ… Startup complete. System ready to receive requests.")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload_enabled = os.getenv("DEV_RELOAD", "false").lower() == "true"
    uvicorn.run(app, host=host, port=port, reload=reload_enabled)

