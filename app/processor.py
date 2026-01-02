from datetime import datetime, timezone
from typing import Dict, Any

# -------------------------------------------------------
# 1. QUESTION SCHEMA (from your shared scoring sheet)
# -------------------------------------------------------

QUESTION_SCHEMA = {
    # STR – Honesty, Dependability & Fairness / Delegation / Support / Communication
    "STR_1": {"segment": "STR", "type": "direct"},
    "STR_2": {"segment": "STR", "type": "reconfirmation"},
    "STR_3": {"segment": "STR", "type": "reverse"},

    "STR_4": {"segment": "STR", "type": "direct"},
    "STR_5": {"segment": "STR", "type": "reconfirmation"},
    "STR_6": {"segment": "STR", "type": "reverse"},

    "STR_7": {"segment": "STR", "type": "direct"},
    "STR_8": {"segment": "STR", "type": "reconfirmation"},
    "STR_9": {"segment": "STR", "type": "reverse"},

    "STR_10": {"segment": "STR", "type": "direct"},
    "STR_11": {"segment": "STR", "type": "reconfirmation"},
    "STR_12": {"segment": "STR", "type": "reverse"},

    # STA – Structure, Planning, Prioritisation, Monitoring
    "STA_1": {"segment": "STA", "type": "direct"},
    "STA_2": {"segment": "STA", "type": "reconfirmation"},
    "STA_3": {"segment": "STA", "type": "reverse"},

    "STA_4": {"segment": "STA", "type": "direct"},
    "STA_5": {"segment": "STA", "type": "reconfirmation"},
    "STA_6": {"segment": "STA", "type": "reverse"},

    "STA_7": {"segment": "STA", "type": "direct"},
    "STA_8": {"segment": "STA", "type": "reconfirmation"},
    "STA_9": {"segment": "STA", "type": "reverse"},

    "STA_10": {"segment": "STA", "type": "direct"},
    "STA_11": {"segment": "STA", "type": "reconfirmation"},
    "STA_12": {"segment": "STA", "type": "reverse"},

    # STE – Enablement, Collaboration, Conflict, Recognition
    "STE_1": {"segment": "STE", "type": "direct"},
    "STE_2": {"segment": "STE", "type": "reconfirmation"},
    "STE_3": {"segment": "STE", "type": "reverse"},

    "STE_4": {"segment": "STE", "type": "direct"},
    "STE_5": {"segment": "STE", "type": "reconfirmation"},
    "STE_6": {"segment": "STE", "type": "reverse"},

    "STE_7": {"segment": "STE", "type": "direct"},
    "STE_8": {"segment": "STE", "type": "reconfirmation"},
    "STE_9": {"segment": "STE", "type": "reverse"},

    "STE_10": {"segment": "STE", "type": "direct"},
    "STE_11": {"segment": "STE", "type": "reconfirmation"},
    "STE_12": {"segment": "STE", "type": "reverse"},
}

# -------------------------------------------------------
# 2. SCORING MAP
# -------------------------------------------------------

SCORE_MAP = {
    "direct": {
        "Never": 1,
        "Sometimes": 2,
        "Always": 3,
    },
    "reconfirmation": {
        "Never": 1,
        "Sometimes": 2,
        "Always": 3,
    },
    "reverse": {
        "Never": 3,
        "Sometimes": 2,
        "Always": 1,
    },
}

# -------------------------------------------------------
# 3. MAIN PROCESSING FUNCTION
# -------------------------------------------------------

def process_form_answers(raw_answers: Dict[str, Any]) -> Dict[str, Any]:
    """
    - Extract question code from Google Form key
    - Apply scoring based on question type
    - Compute per-question scores
    - Compute segment totals + overall total
    """

    per_question_scores = {}
    segment_totals = {"STR": 0, "STA": 0, "STE": 0}

    for full_question, answer_list in raw_answers.items():
        if not answer_list:
            continue

        answer = answer_list[0].strip()

        # Extract question code (before |)
        question_code = full_question.split("|")[0].strip()

        if question_code not in QUESTION_SCHEMA:
            # Unknown question → skip safely
            continue

        schema = QUESTION_SCHEMA[question_code]
        segment = schema["segment"]
        q_type = schema["type"]

        score = SCORE_MAP[q_type].get(answer)

        if score is None:
            continue

        per_question_scores[question_code] = {
            "answer": answer,
            "score": score,
            "type": q_type,
            "segment": segment,
        }

        segment_totals[segment] += score

    overall_score = sum(segment_totals.values())

    return {
        "per_question_scores": per_question_scores,
        "segment_totals": segment_totals,
        "overall_score": overall_score,
        "meta": {
            "schema_version": "PAM_v1",
            "max_per_question": 3,
            "total_questions": len(QUESTION_SCHEMA),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        },
    }

