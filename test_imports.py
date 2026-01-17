import sys
print("Python version:", sys.version)

print("\nTesting imports...")

try:
    from fastapi import FastAPI
    print("✓ FastAPI imported")
except ImportError as e:
    print(f"✗ FastAPI import error: {e}")

try:
    from dotenv import load_dotenv
    print("✓ python-dotenv imported")
    load_dotenv()
    print("✓ .env file loaded")
    mongodb_uri = os.getenv("MONGODB_URI")
    print(f"✓ MONGODB_URI from .env: {mongodb_uri[:30]}..." if mongodb_uri else "✗ MONGODB_URI not found")
except ImportError as e:
    print(f"✗ dotenv import error: {e}")
except Exception as e:
    print(f"✗ Error: {e}")

try:
    from app.db import raw_responses
    print("✓ MongoDB connection successful")
except ImportError as e:
    print(f"✗ app.db import error: {e}")
except Exception as e:
    print(f"✗ MongoDB error: {e}")