import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "pam")

if not MONGODB_URI:
    raise ValueError("MONGODB_URI is missing in .env")

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

# Collections - using your existing collection names
raw_responses = db["google_form_responses"]  # Existing Google Form data
managers = db["manager"]                     # Your manager collection
reports = db["reports"]                      # For AI reports

async_client = AsyncIOMotorClient(MONGODB_URI)
async_db = async_client[DB_NAME]  # This is what's missing!

# Async versions for legacy collections
async_raw_responses = async_db["google_form_responses"]
async_managers = async_db["manager"]
async_reports = async_db["reports"]

# ==================== NEW SAAS COLLECTIONS ====================
# Users collection for authentication
users = db["users"]
async_users = async_db["users"]

# Companies collection
companies = db["companies"]
async_companies = async_db["companies"]

# Assessment responses (new, for web form submissions)
assessments = db["assessments"]
async_assessments = async_db["assessments"]

# Form submissions tracking
form_submissions = db["form_submissions"]
async_form_submissions = async_db["form_submissions"]

# SaaS manager reports (AI-generated)
saas_reports = db["saas_reports"]
async_saas_reports = async_db["saas_reports"]

# ==================== CREATE INDEXES ====================
def create_indexes():
    """Create all necessary database indexes"""
    print("📊 Creating database indexes...")
    
    # Legacy indexes (your existing)
    raw_responses.create_index([("manager_name", ASCENDING), ("submittedAt", DESCENDING)])
    raw_responses.create_index([("reporting_to", ASCENDING)])
    raw_responses.create_index([("submittedAt", DESCENDING)])
    raw_responses.create_index([("created_at", DESCENDING)])
    
    managers.create_index([("manager_name", ASCENDING)], unique=True)
    managers.create_index([("reporting_to", ASCENDING)])
    managers.create_index([("last_updated", DESCENDING)])
    
    reports.create_index([("manager_name", ASCENDING)], unique=True)
    reports.create_index([("created_at", DESCENDING)])
    
    # New SaaS indexes
    users.create_index([("email", ASCENDING)], unique=True)
    users.create_index([("company_id", ASCENDING)])
    
    companies.create_index([("slug", ASCENDING)], unique=True)
    companies.create_index([("created_by", ASCENDING)])
    companies.create_index([("created_at", DESCENDING)])
    
    # New managers index with company_id
    managers.create_index([("company_id", ASCENDING), ("manager_name", ASCENDING)], unique=True)
    
    assessments.create_index([("company_id", ASCENDING), ("manager_name", ASCENDING)])
    assessments.create_index([("session_id", ASCENDING)], unique=True)
    assessments.create_index([("submission_time", DESCENDING)])
    
    form_submissions.create_index([("company_slug", ASCENDING)])
    form_submissions.create_index([("created_at", DESCENDING)])

    saas_reports.create_index([("company_id", ASCENDING), ("manager_name", ASCENDING)], unique=True)
    saas_reports.create_index([("created_at", DESCENDING)])
    
    print("✅ All indexes created successfully")

# ==================== DATABASE INITIALIZATION ====================
async def init_database():
    """Initialize database with required setup"""
    try:
        # Check if we have existing data to migrate
        legacy_count = raw_responses.count_documents({})
        new_count = assessments.count_documents({})
        
        print(f"📊 Database Status:")
        print(f"   Legacy responses: {legacy_count}")
        print(f"   New assessments: {new_count}")
        print(f"   Total managers: {managers.count_documents({})}")
        
        # Create indexes
        create_indexes()
        # Create or update admin user
        admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip().lower()
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

        if admin_email:
            from app.auth import get_password_hash
            admin_user = {
                "id": "admin_001",
                "email": admin_email,
                "full_name": "System Administrator",
                "hashed_password": get_password_hash(admin_password),
                "role": "admin",
                "is_active": True,
                "created_at": os.getenv("DATETIME_NOW", "2024-01-01T00:00:00Z"),
                "updated_at": os.getenv("DATETIME_NOW", "2024-01-01T00:00:00Z")
            }
            existing_email_user = users.find_one({"email": admin_email})
            if existing_email_user:
                users.update_one({"_id": existing_email_user["_id"]}, {"$set": admin_user})
            else:
                users.delete_one({"id": "admin_001"})
                users.update_one({"email": admin_email}, {"$set": admin_user}, upsert=True)
            print(f"Admin ensured (email: {admin_email})")
        
            print(f"✅ Database '{DB_NAME}' initialized successfully")
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        raise

# ==================== DATABASE HEALTH CHECK ====================
async def check_database_health():
    """Check database connection and collections"""
    try:
        # Test connection
        client.admin.command('ping')
        
        collections = {
            "Legacy": ["google_form_responses", "manager", "reports"],
            "SaaS": ["users", "companies", "assessments", "form_submissions"]
        }
        
        health_report = {
            "status": "healthy",
            "database": DB_NAME,
            "collections": {},
            "counts": {}
        }
        
        # Check each collection
        for category, coll_list in collections.items():
            for coll_name in coll_list:
                coll = db[coll_name]
                count = coll.count_documents({})
                health_report["collections"][coll_name] = {
                    "exists": True,
                    "count": count,
                    "category": category
                }
        
        return health_report
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

# ==================== DATA MIGRATION HELPERS ====================
async def migrate_legacy_data():
    """
    Migrate data from legacy collections to new structure
    This preserves your existing Google Form data
    """
    try:
        print("🔄 Migrating legacy data to new structure...")
        
        # Count legacy data
        legacy_count = raw_responses.count_documents({})
        if legacy_count == 0:
            print("📭 No legacy data to migrate")
            return {"migrated": 0, "message": "No legacy data found"}
        
        # Create a default company for legacy data
        default_company = {
            "id": "legacy_company",
            "name": "Legacy Company (Migrated)",
            "slug": "legacy-company",
            "description": "Company created from legacy Google Form data",
            "industry": "Various",
            "employee_count": 0,
            "manager_count": 0,
            "created_by": "system",
            "created_at": os.getenv("DATETIME_NOW", "2024-01-01T00:00:00Z"),
            "updated_at": os.getenv("DATETIME_NOW", "2024-01-01T00:00:00Z")
        }
        
        # Insert default company if not exists
        if companies.count_documents({"id": "legacy_company"}) == 0:
            companies.insert_one(default_company)
        
        # Migrate managers
        migrated_managers = 0
        legacy_managers = managers.find({})
        
        for manager in legacy_managers:
            # Add company_id to existing manager
            managers.update_one(
                {"_id": manager["_id"]},
                {"$set": {"company_id": "legacy_company"}}
            )
            migrated_managers += 1
        
        print(f"✅ Migrated {migrated_managers} managers to new structure")
        print(f"✅ Legacy data preserved in 'legacy_company'")
        
        return {
            "success": True,
            "migrated_managers": migrated_managers,
            "company_id": "legacy_company",
            "message": f"Migrated {migrated_managers} managers to new structure"
        }
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        return {"success": False, "error": str(e)}

# ==================== EXPORT COLLECTIONS ====================
print(f"✅ Connected to MongoDB: {DB_NAME}")
print(f"📁 Collections available:")
print(f"   Legacy: google_form_responses, manager, reports")
print(f"   SaaS: users, companies, assessments, form_submissions")

# Call init on import
import asyncio
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    asyncio.run(init_database())
else:
    loop.create_task(init_database())
