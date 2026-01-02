print("🔥🔥 THIS IS THE REQUEST-BASED MAIN.PY 🔥🔥")
import os
from fastapi import FastAPI, Header, HTTPException, Request
from dotenv import load_dotenv

from app.db import collection
from app.processor import process_form_answers

load_dotenv()

app = FastAPI(title="PAM – Google Form → FastAPI → MongoDB")

FORM_SECRET = os.getenv("FORM_SECRET", "")

@app.get("/")
def home():
    return {"message": "PAM API is running. Use /health"}

@app.get("/health")
def health():
    return {"ok": True}


@app.post("/webhooks/google-form")
async def google_form_webhook(request: Request, x_form_secret: str = Header(default="")):
    if x_form_secret != FORM_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    raw = await request.json()
    answers = raw.get("answers", {})

    print("✅ formId =", raw.get("formId"))
    print("✅ answers_count =", len(answers))
    print("✅ Writing to:", collection.database.name, "->", collection.name)

    processed = process_form_answers(answers)

    doc = {
        "formId": raw.get("formId"),
        "submittedAt": raw.get("submittedAt"),
        "raw_answers": answers,
        "processed": processed,
    }

    result = collection.insert_one(doc)
    print("✅ Inserted_id =", result.inserted_id)

    # extra proof: count docs
    print("✅ Collection count =", collection.count_documents({}))

    return {"ok": True}
