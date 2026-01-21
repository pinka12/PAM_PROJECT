from datetime import datetime, timezone
from typing import Dict, Any
import statistics
from collections import defaultdict

# -------------------------------------------------------
# NAME NORMALIZATION FUNCTION
# -------------------------------------------------------
def normalize_name(name: str) -> str:
    """
    Normalize names for consistency:
    - Trim whitespace
    - Convert to title case
    - Remove extra spaces
    - Handle empty/null values
    """
    if not name:
        return ""
    
    # Convert to string, strip, title case
    name_str = str(name).strip()
    
    # Split by spaces, title case each word, join back
    words = [word.title() for word in name_str.split() if word.strip()]
    
    return " ".join(words) if words else ""

# -------------------------------------------------------
# 1. QUESTION SCHEMA (updated with categories)
# -------------------------------------------------------
QUESTION_SCHEMA = {
    # STR – Trusting (Honesty, Dependability & Fairness)
    "STR_1": {"segment": "STR", "type": "direct", "category": "trusting"},
    "STR_2": {"segment": "STR", "type": "reconfirmation", "category": "trusting"},
    "STR_3": {"segment": "STR", "type": "reverse", "category": "trusting"},
    "STR_4": {"segment": "STR", "type": "direct", "category": "trusting"},
    "STR_5": {"segment": "STR", "type": "reconfirmation", "category": "trusting"},
    "STR_6": {"segment": "STR", "type": "reverse", "category": "trusting"},
    "STR_7": {"segment": "STR", "type": "direct", "category": "trusting"},
    "STR_8": {"segment": "STR", "type": "reconfirmation", "category": "trusting"},
    "STR_9": {"segment": "STR", "type": "reverse", "category": "trusting"},
    "STR_10": {"segment": "STR", "type": "direct", "category": "trusting"},
    "STR_11": {"segment": "STR", "type": "reconfirmation", "category": "trusting"},
    "STR_12": {"segment": "STR", "type": "reverse", "category": "trusting"},

    # STA – Tasking (Structure, Planning, Prioritisation)
    "STA_1": {"segment": "STA", "type": "direct", "category": "tasking"},
    "STA_2": {"segment": "STA", "type": "reconfirmation", "category": "tasking"},
    "STA_3": {"segment": "STA", "type": "reverse", "category": "tasking"},
    "STA_4": {"segment": "STA", "type": "direct", "category": "tasking"},
    "STA_5": {"segment": "STA", "type": "reconfirmation", "category": "tasking"},
    "STA_6": {"segment": "STA", "type": "reverse", "category": "tasking"},
    "STA_7": {"segment": "STA", "type": "direct", "category": "tasking"},
    "STA_8": {"segment": "STA", "type": "reconfirmation", "category": "tasking"},
    "STA_9": {"segment": "STA", "type": "reverse", "category": "tasking"},
    "STA_10": {"segment": "STA", "type": "direct", "category": "tasking"},
    "STA_11": {"segment": "STA", "type": "reconfirmation", "category": "tasking"},
    "STA_12": {"segment": "STA", "type": "reverse", "category": "tasking"},

    # STE – Tending (Enablement, Collaboration, Recognition)
    "STE_1": {"segment": "STE", "type": "direct", "category": "tending"},
    "STE_2": {"segment": "STE", "type": "reconfirmation", "category": "tending"},
    "STE_3": {"segment": "STE", "type": "reverse", "category": "tending"},
    "STE_4": {"segment": "STE", "type": "direct", "category": "tending"},
    "STE_5": {"segment": "STE", "type": "reconfirmation", "category": "tending"},
    "STE_6": {"segment": "STE", "type": "reverse", "category": "tending"},
    "STE_7": {"segment": "STE", "type": "direct", "category": "tending"},
    "STE_8": {"segment": "STE", "type": "reconfirmation", "category": "tending"},
    "STE_9": {"segment": "STE", "type": "reverse", "category": "tending"},
    "STE_10": {"segment": "STE", "type": "direct", "category": "tending"},
    "STE_11": {"segment": "STE", "type": "reconfirmation", "category": "tending"},
    "STE_12": {"segment": "STE", "type": "reverse", "category": "tending"},
}

# -------------------------------------------------------
# 2. SCORING MAP
# -------------------------------------------------------
SCORE_MAP = {
    "direct": {"Never": 1, "Sometimes": 2, "Always": 3},
    "reconfirmation": {"Never": 1, "Sometimes": 2, "Always": 3},
    "reverse": {"Never": 3, "Sometimes": 2, "Always": 1},
}

# -------------------------------------------------------
# 3. MANAGER INFO EXTRACTION
# -------------------------------------------------------
def extract_manager_info(raw_answers: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract and normalize manager information from Google Form answers
    """
    manager_info = {
        "manager_name": "",
        "reporting_to": "",
        "timestamp": "",
        "raw_manager_name": "",  # Store original for reference
        "raw_reporting_to": ""   # Store original for reference
    }
    
    for full_question, answer_list in raw_answers.items():
        if not answer_list:
            continue
        
        answer = answer_list[0].strip()
        
        # Extract manager name
        if "manager's full name" in full_question.lower():
            manager_info["raw_manager_name"] = answer
            manager_info["manager_name"] = normalize_name(answer)
        
        # Extract reporting manager
        elif "manager report to" in full_question.lower():
            manager_info["raw_reporting_to"] = answer
            manager_info["reporting_to"] = normalize_name(answer)
        
        # Extract timestamp
        elif "timestamp" in full_question.lower():
            manager_info["timestamp"] = answer
    
    return manager_info

# -------------------------------------------------------
# 4. MAIN PROCESSING FUNCTION
# -------------------------------------------------------
def process_form_answers(raw_answers: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process individual form response with new category mapping
    """
    # Extract manager info
    manager_info = extract_manager_info(raw_answers)
    
    # Process scoring
    per_question_scores = {}
    segment_totals = {"STR": 0, "STA": 0, "STE": 0}
    category_totals = {"trusting": 0, "tasking": 0, "tending": 0}
    answered_questions = set()
    
    for full_question, answer_list in raw_answers.items():
        if not answer_list:
            continue
        
        answer = answer_list[0].strip()
        
        # Skip non-question fields (manager name, reporting, timestamp)
        question_lower = full_question.lower()
        if any(keyword in question_lower for keyword in ["manager", "report", "timestamp"]):
            continue
        
        # Extract question code (first word before space)
        parts = full_question.split()
        if not parts:
            continue
        
        question_code = parts[0].strip()
        
        if question_code not in QUESTION_SCHEMA:
            continue
        
        schema = QUESTION_SCHEMA[question_code]
        segment = schema["segment"]
        q_type = schema["type"]
        category = schema["category"]
        
        score = SCORE_MAP[q_type].get(answer)
        
        if score is None:
            continue
        
        per_question_scores[question_code] = {
            "answer": answer,
            "score": score,
            "type": q_type,
            "segment": segment,
            "category": category,
        }
        
        segment_totals[segment] += score
        category_totals[category] += score
        answered_questions.add(question_code)
    
    overall_score = sum(segment_totals.values())
    missing_questions = sorted(set(QUESTION_SCHEMA.keys()) - answered_questions)
    manager_fields_present = sum(
        1 for key in ["manager_name", "reporting_to"] if manager_info.get(key)
    )
    is_complete_response = (
        len(answered_questions) == len(QUESTION_SCHEMA) and manager_fields_present == 2
    )
    
    return {
        "manager_info": manager_info,
        "per_question_scores": per_question_scores,
        "segment_totals": segment_totals,
        "category_totals": category_totals,
        "overall_score": overall_score,
        "meta": {
            "schema_version": "PAM_v1",
            "max_per_question": 3,
            "total_questions": len(QUESTION_SCHEMA),
            "answered_questions": len(answered_questions),
            "missing_questions": missing_questions,
            "expected_response_fields": len(QUESTION_SCHEMA) + 2,
            "manager_fields_present": manager_fields_present,
            "is_complete_response": is_complete_response,
            "raw_response_fields": len(raw_answers),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        },
    }

# -------------------------------------------------------
# 5. AGGREGATION FUNCTION (for batch processing if needed)
# -------------------------------------------------------
def aggregate_manager_scores(assessments: list) -> Dict[str, Any]:
    """
    Aggregate multiple assessments for the same manager
    """
    if not assessments:
        return None
    
    # Collect all scores
    category_totals = {"trusting": 0, "tasking": 0, "tending": 0}
    category_scores_list = {"trusting": [], "tasking": [], "tending": []}
    all_timestamps = []
    
    for assessment in assessments:
        processed = assessment.get("processed", {})
        categories = processed.get("category_totals", {})
        timestamp = assessment.get("submittedAt") or assessment.get("created_at")
        
        if timestamp:
            all_timestamps.append(timestamp)
        
        # Sum category totals
        for category in ["trusting", "tasking", "tending"]:
            score = categories.get(category, 0)
            category_totals[category] += score
            category_scores_list[category].append(score)
    
    # Get manager info from latest assessment
    latest_assessment = assessments[-1]
    processed = latest_assessment.get("processed", {})
    manager_info = processed.get("manager_info", {})
    
    # Calculate statistics
    total_assessments = len(assessments)
    aggregated = {
        "manager_name": manager_info.get("manager_name", ""),
        "reporting_to": manager_info.get("reporting_to", ""),
        "raw_manager_name": manager_info.get("raw_manager_name", ""),
        "raw_reporting_to": manager_info.get("raw_reporting_to", ""),
        
        "total_assessments": total_assessments,
        "first_assessment": min(all_timestamps) if all_timestamps else "",
        "last_assessment": max(all_timestamps) if all_timestamps else "",
        
        # Category aggregations
        "category_totals": category_totals,
        
        "category_averages": {
            "trusting": round(category_totals["trusting"] / total_assessments, 2) if total_assessments else 0,
            "tasking": round(category_totals["tasking"] / total_assessments, 2) if total_assessments else 0,
            "tending": round(category_totals["tending"] / total_assessments, 2) if total_assessments else 0
        },
        
        # Score distribution
        "score_distribution": {
            "trusting": {
                "min": min(category_scores_list["trusting"]) if category_scores_list["trusting"] else 0,
                "max": max(category_scores_list["trusting"]) if category_scores_list["trusting"] else 0,
                "std": statistics.stdev(category_scores_list["trusting"]) if len(category_scores_list["trusting"]) > 1 else 0
            },
            "tasking": {
                "min": min(category_scores_list["tasking"]) if category_scores_list["tasking"] else 0,
                "max": max(category_scores_list["tasking"]) if category_scores_list["tasking"] else 0,
                "std": statistics.stdev(category_scores_list["tasking"]) if len(category_scores_list["tasking"]) > 1 else 0
            },
            "tending": {
                "min": min(category_scores_list["tending"]) if category_scores_list["tending"] else 0,
                "max": max(category_scores_list["tending"]) if category_scores_list["tending"] else 0,
                "std": statistics.stdev(category_scores_list["tending"]) if len(category_scores_list["tending"]) > 1 else 0
            }
        },
        
        "confidence_score": min(100, len(assessments) * 10),
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
    
    return aggregated
