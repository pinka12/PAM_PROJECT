import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "pam")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "google_form_responses")

if not MONGODB_URI:
    raise ValueError("MONGODB_URI is missing in .env")

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]
