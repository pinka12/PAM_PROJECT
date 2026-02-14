from datetime import datetime, timezone
from typing import Dict, Any, Tuple
import statistics

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

    name_str = str(name).strip()
    words = [word.title() for word in name_str.split() if word.strip()]
    return " ".join(words) if words else ""


# -------------------------------------------------------
# 1. QUESTION SCHEMA (updated with categories + subcategories)
# -------------------------------------------------------
QUESTION_SCHEMA = {
    # STR - Trusting
    "STR_1": {"segment": "STR", "type": "direct", "category": "trusting", "behavior": "Honesty, Dependability & Fairness"},
    "STR_2": {"segment": "STR", "type": "reconfirmation", "category": "trusting", "behavior": "Honesty, Dependability & Fairness"},
    "STR_3": {"segment": "STR", "type": "reverse", "category": "trusting", "behavior": "Honesty, Dependability & Fairness"},
    "STR_4": {"segment": "STR", "type": "direct", "category": "trusting", "behavior": "Task Delegation Without Bias"},
    "STR_5": {"segment": "STR", "type": "reconfirmation", "category": "trusting", "behavior": "Task Delegation Without Bias"},
    "STR_6": {"segment": "STR", "type": "reverse", "category": "trusting", "behavior": "Task Delegation Without Bias"},
    "STR_7": {"segment": "STR", "type": "direct", "category": "trusting", "behavior": "Providing Necessary Support"},
    "STR_8": {"segment": "STR", "type": "reconfirmation", "category": "trusting", "behavior": "Providing Necessary Support"},
    "STR_9": {"segment": "STR", "type": "reverse", "category": "trusting", "behavior": "Providing Necessary Support"},
    "STR_10": {"segment": "STR", "type": "direct", "category": "trusting", "behavior": "Encouraging Open Communication"},
    "STR_11": {"segment": "STR", "type": "reconfirmation", "category": "trusting", "behavior": "Encouraging Open Communication"},
    "STR_12": {"segment": "STR", "type": "reverse", "category": "trusting", "behavior": "Encouraging Open Communication"},

    # STA - Tasking
    "STA_1": {"segment": "STA", "type": "direct", "category": "tasking", "behavior": "Defining Roles & Responsibilities"},
    "STA_2": {"segment": "STA", "type": "reconfirmation", "category": "tasking", "behavior": "Defining Roles & Responsibilities"},
    "STA_3": {"segment": "STA", "type": "reverse", "category": "tasking", "behavior": "Defining Roles & Responsibilities"},
    "STA_4": {"segment": "STA", "type": "direct", "category": "tasking", "behavior": "Planning & Organizing"},
    "STA_5": {"segment": "STA", "type": "reconfirmation", "category": "tasking", "behavior": "Planning & Organizing"},
    "STA_6": {"segment": "STA", "type": "reverse", "category": "tasking", "behavior": "Planning & Organizing"},
    "STA_7": {"segment": "STA", "type": "direct", "category": "tasking", "behavior": "Prioritising Tasks"},
    "STA_8": {"segment": "STA", "type": "reconfirmation", "category": "tasking", "behavior": "Prioritising Tasks"},
    "STA_9": {"segment": "STA", "type": "reverse", "category": "tasking", "behavior": "Prioritising Tasks"},
    "STA_10": {"segment": "STA", "type": "direct", "category": "tasking", "behavior": "Monitoring Progress & Providing Assistance"},
    "STA_11": {"segment": "STA", "type": "reconfirmation", "category": "tasking", "behavior": "Monitoring Progress & Providing Assistance"},
    "STA_12": {"segment": "STA", "type": "reverse", "category": "tasking", "behavior": "Monitoring Progress & Providing Assistance"},

    # STE - Tending
    "STE_1": {"segment": "STE", "type": "direct", "category": "tending", "behavior": "Helping Team Members Learn & Improve"},
    "STE_2": {"segment": "STE", "type": "reconfirmation", "category": "tending", "behavior": "Helping Team Members Learn & Improve"},
    "STE_3": {"segment": "STE", "type": "reverse", "category": "tending", "behavior": "Helping Team Members Learn & Improve"},
    "STE_4": {"segment": "STE", "type": "direct", "category": "tending", "behavior": "Creating a Collaborative Environment"},
    "STE_5": {"segment": "STE", "type": "reconfirmation", "category": "tending", "behavior": "Creating a Collaborative Environment"},
    "STE_6": {"segment": "STE", "type": "reverse", "category": "tending", "behavior": "Creating a Collaborative Environment"},
    "STE_7": {"segment": "STE", "type": "direct", "category": "tending", "behavior": "Resolving Conflicts & Fostering Camaraderie"},
    "STE_8": {"segment": "STE", "type": "reconfirmation", "category": "tending", "behavior": "Resolving Conflicts & Fostering Camaraderie"},
    "STE_9": {"segment": "STE", "type": "reverse", "category": "tending", "behavior": "Resolving Conflicts & Fostering Camaraderie"},
    "STE_10": {"segment": "STE", "type": "direct", "category": "tending", "behavior": "Recognising & Rewarding Achievement"},
    "STE_11": {"segment": "STE", "type": "reconfirmation", "category": "tending", "behavior": "Recognising & Rewarding Achievement"},
    "STE_12": {"segment": "STE", "type": "reverse", "category": "tending", "behavior": "Recognising & Rewarding Achievement"},
}

SUBCATEGORY_ORDER = {
    "trusting": [
        "Honesty, Dependability & Fairness",
        "Task Delegation Without Bias",
        "Providing Necessary Support",
        "Encouraging Open Communication",
    ],
    "tasking": [
        "Defining Roles & Responsibilities",
        "Planning & Organizing",
        "Prioritising Tasks",
        "Monitoring Progress & Providing Assistance",
    ],
    "tending": [
        "Helping Team Members Learn & Improve",
        "Creating a Collaborative Environment",
        "Resolving Conflicts & Fostering Camaraderie",
        "Recognising & Rewarding Achievement",
    ],
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
# 2A. SUBCATEGORY REMARKS (RED/AMBER/GREEN)
# -------------------------------------------------------
SUBCATEGORY_REMARKS = {
    "trusting": {
        "Honesty, Dependability & Fairness": {
            "red": "You are currently experienced as inconsistent in how commitments are honoured and decisions are applied. This creates hesitation and second-guessing within the team, as people are unsure whether expectations and responses will remain stable across situations.",
            "amber": "Your intent to be fair and dependable is visible; however, consistency weakens under pressure. While expectations are usually clear, the team is not always confident that commitments and decisions will hold uniformly across similar situations.",
            "green": "You are experienced as dependable and fair, with commitments and decisions remaining consistent even under pressure. This reliability builds confidence, reduces ambiguity, and allows the team to operate without second-guessing leadership intent.",
        },
        "Task Delegation Without Bias": {
            "red": "Work allocation is experienced as uneven, raising concerns about favouritism or unclear rationale. This limits trust, reduces engagement, and restricts equitable development opportunities across the team.",
            "amber": "Delegation decisions are generally well-intended, but the underlying rationale is not always visible. As a result, team members are sometimes unsure whether work is assigned based on skill, development needs, or convenience.",
            "green": "Delegation is experienced as fair, transparent, and capability-based. Team members understand why work is assigned as it is, which strengthens trust and supports balanced development across the group.",
        },
        "Providing Necessary Support": {
            "red": "Support is experienced as reactive or inconsistent, particularly during roadblocks. This creates delays, increases frustration, and leaves team members feeling they must navigate challenges largely on their own.",
            "amber": "Support is available, but not always anticipatory. While help is provided when asked, the team is not consistently confident that obstacles will be identified and addressed early.",
            "green": "Support is timely and dependable. Obstacles are anticipated and addressed early, enabling momentum and reinforcing the team's confidence in leadership availability.",
        },
        "Encouraging Open Communication": {
            "red": "Team members hesitate to speak openly due to uncertainty about how concerns or differing views will be received. This restricts information flow and increases the risk of unresolved issues surfacing later.",
            "amber": "You encourage openness, but signals under pressure can make psychological safety feel conditional. As a result, some conversations are delayed or softened rather than addressed directly.",
            "green": "You consistently create a safe environment for open dialogue. Team members feel comfortable raising concerns, sharing ideas, and engaging in difficult conversations without fear of negative repercussions.",
        },
    },
    "tasking": {
        "Defining Roles & Responsibilities": {
            "red": "Role clarity is insufficient, leading to confusion about ownership and expectations. This results in rework, delays, and misaligned accountability.",
            "amber": "Roles and expectations are defined, but not always reinforced at key milestones. This creates occasional ambiguity during execution, particularly when priorities shift.",
            "green": "Roles and responsibilities are consistently clear and reinforced. This enables accountability, reduces rework, and supports smooth execution across changing contexts.",
        },
        "Planning & Organizing": {
            "red": "Planning is largely reactive, resulting in last-minute changes and avoidable disruption. This places unnecessary strain on the team and reduces execution stability.",
            "amber": "Basic planning structures exist, but foresight and buffers are inconsistent. While plans usually hold, pressure situations expose gaps in preparation.",
            "green": "Planning is structured, forward-looking, and resilient. Anticipated risks are built into plans, enabling predictable execution even under changing conditions.",
        },
        "Prioritising Tasks": {
            "red": "Priorities are unclear or frequently shifting, causing low-value work to consume time and attention. This dilutes focus on what matters most.",
            "amber": "Priorities are generally set, but the reasoning behind them is not always explicit. This can create confusion when trade-offs are required.",
            "green": "Priorities are consistently clear and aligned with business impact. The team understands not just what to focus on, but why certain tasks take precedence.",
        },
        "Monitoring Progress & Providing Assistance": {
            "red": "Progress issues are often identified late, increasing escalation and recovery effort. This raises delivery risk and dependency on firefighting.",
            "amber": "Progress is monitored, but early warning signals are not always acted upon decisively. Risks are recognised, though intervention can be delayed.",
            "green": "Progress is tracked proactively, with early intervention when risks emerge. This reduces escalation, stabilises delivery, and sustains momentum.",
        },
    },
    "tending": {
        "Helping Team Members Learn & Improve": {
            "red": "Development is largely left to individuals, resulting in uneven capability growth. Learning happens incidentally rather than intentionally.",
            "amber": "Learning and development are encouraged, but not consistently embedded into day-to-day work. Growth depends more on individual initiative than structured guidance.",
            "green": "You actively support learning and skill development. Growth conversations are regular, intentional, and aligned with both individual and organisational needs.",
        },
        "Creating a Collaborative Environment": {
            "red": "Silos or cliques limit collaboration and shared ownership. Teamwork suffers as issues are addressed in isolation rather than collectively.",
            "amber": "Collaboration exists, but often requires deliberate prompting. Cooperation is present, though not yet habitual across the team.",
            "green": "You foster a strong sense of shared ownership. Collaboration is natural, respectful, and embedded in how the team operates.",
        },
        "Resolving Conflicts & Fostering Camaraderie": {
            "red": "Conflicts are either avoided or insufficiently resolved, allowing tension to resurface. This weakens trust and working relationships over time.",
            "amber": "Conflicts are addressed, but closure is not always complete. While issues are discussed, emotional resolution can remain partial.",
            "green": "Conflicts are handled constructively and brought to clear resolution. This strengthens trust, reinforces respect, and sustains positive working relationships.",
        },
        "Recognising & Rewarding Achievement": {
            "red": "Effort and contribution often go unnoticed, reducing motivation and discretionary effort. Recognition feels inconsistent or absent.",
            "amber": "Recognition occurs, but lacks regularity or personal relevance. While achievements are acknowledged, impact is uneven.",
            "green": "Recognition is timely, meaningful, and aligned with effort and outcomes. This reinforces positive behaviour and sustains engagement.",
        },
    },
}


def get_subcategory_keys() -> Dict[str, str]:
    keys: Dict[str, str] = {}
    for tripod, behaviors in SUBCATEGORY_ORDER.items():
        for behavior in behaviors:
            keys[behavior] = tripod
    return keys


def init_subcategory_scores() -> Tuple[Dict[str, int], Dict[str, int]]:
    keys = get_subcategory_keys()
    return {behavior: 0 for behavior in keys}, {behavior: 0 for behavior in keys}


def compute_subcategory_averages(
    subcategory_scores: Dict[str, int],
    subcategory_counts: Dict[str, int],
) -> Dict[str, float]:
    averages: Dict[str, float] = {}
    for behavior, total in subcategory_scores.items():
        answered = subcategory_counts.get(behavior, 0)
        if answered > 0:
            # Keep raw behavior marks on a 0-9 scale:
            # each behavior has 3 questions, each question max score 3.
            averages[behavior] = round((total / answered) * 3, 2)
        else:
            averages[behavior] = 0.0
    return averages


def _score_band(score: float) -> str:
    if score >= 8:
        return "green"
    if score >= 6:
        return "amber"
    return "red"


def get_subcategory_remark(behavior: str, score: float, tripod: str = "") -> Dict[str, Any]:
    tripod_key = (tripod or get_subcategory_keys().get(behavior, "")).lower()
    behavior_remarks = SUBCATEGORY_REMARKS.get(tripod_key, {}).get(behavior, {})
    band = _score_band(score)
    return {
        "tripod": tripod_key,
        "behavior": behavior,
        "score": round(score, 1),
        "band": band,
        "remark": behavior_remarks.get(band, ""),
    }


def build_subcategory_remark_context(subcategory_averages: Dict[str, float]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for tripod, behaviors in SUBCATEGORY_ORDER.items():
        result[tripod] = {}
        for behavior in behaviors:
            score = float(subcategory_averages.get(behavior, 0))
            result[tripod][behavior] = get_subcategory_remark(behavior, score, tripod)
    return result


def build_subcategory_prompt_block(subcategory_averages: Dict[str, float]) -> str:
    remark_context = build_subcategory_remark_context(subcategory_averages)
    lines = ["Subcategory Evaluation Context:"]
    for tripod, behaviors in remark_context.items():
        lines.append(f"{tripod.upper()}:")
        for behavior, data in behaviors.items():
            lines.append(
                f"- {behavior} | score: {data['score']} | band: {data['band'].upper()} | remark: {data['remark']}"
            )
    return "\n".join(lines)


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
        "raw_manager_name": "",
        "raw_reporting_to": "",
    }

    for full_question, answer_list in raw_answers.items():
        if not answer_list:
            continue

        answer = answer_list[0].strip()

        if "manager's full name" in full_question.lower():
            manager_info["raw_manager_name"] = answer
            manager_info["manager_name"] = normalize_name(answer)
        elif "manager report to" in full_question.lower():
            manager_info["raw_reporting_to"] = answer
            manager_info["reporting_to"] = normalize_name(answer)
        elif "timestamp" in full_question.lower():
            manager_info["timestamp"] = answer

    return manager_info


# -------------------------------------------------------
# 4. MAIN PROCESSING FUNCTION
# -------------------------------------------------------
def process_form_answers(raw_answers: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process individual form response with category and subcategory mapping
    """
    manager_info = extract_manager_info(raw_answers)

    per_question_scores = {}
    segment_totals = {"STR": 0, "STA": 0, "STE": 0}
    category_totals = {"trusting": 0, "tasking": 0, "tending": 0}
    subcategory_scores, subcategory_counts = init_subcategory_scores()
    answered_questions = set()

    for full_question, answer_list in raw_answers.items():
        if not answer_list:
            continue

        answer = answer_list[0].strip()

        question_lower = full_question.lower()
        if any(keyword in question_lower for keyword in ["manager", "report", "timestamp"]):
            continue

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
        behavior = schema["behavior"]

        score = SCORE_MAP[q_type].get(answer)
        if score is None:
            continue

        per_question_scores[question_code] = {
            "answer": answer,
            "score": score,
            "type": q_type,
            "segment": segment,
            "category": category,
            "behavior": behavior,
        }

        segment_totals[segment] += score
        category_totals[category] += score
        subcategory_scores[behavior] += score
        subcategory_counts[behavior] += 1
        answered_questions.add(question_code)

    overall_score = sum(segment_totals.values())
    missing_questions = sorted(set(QUESTION_SCHEMA.keys()) - answered_questions)
    manager_fields_present = sum(1 for key in ["manager_name", "reporting_to"] if manager_info.get(key))
    is_complete_response = len(answered_questions) == len(QUESTION_SCHEMA) and manager_fields_present == 2

    subcategory_averages = compute_subcategory_averages(subcategory_scores, subcategory_counts)
    subcategory_remarks = build_subcategory_remark_context(subcategory_averages)

    return {
        "manager_info": manager_info,
        "per_question_scores": per_question_scores,
        "segment_totals": segment_totals,
        "category_totals": category_totals,
        "subcategory_totals": subcategory_scores,
        "subcategory_averages": subcategory_averages,
        "subcategory_remarks": subcategory_remarks,
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

    category_totals = {"trusting": 0, "tasking": 0, "tending": 0}
    category_scores_list = {"trusting": [], "tasking": [], "tending": []}
    subcategory_totals, _ = init_subcategory_scores()
    all_timestamps = []

    for assessment in assessments:
        processed = assessment.get("processed", {})
        categories = processed.get("category_totals", {})
        subcategories = processed.get("subcategory_totals", {})
        timestamp = assessment.get("submittedAt") or assessment.get("created_at")

        if timestamp:
            all_timestamps.append(timestamp)

        for category in ["trusting", "tasking", "tending"]:
            score = categories.get(category, 0)
            category_totals[category] += score
            category_scores_list[category].append(score)

        for behavior, score in subcategories.items():
            if behavior in subcategory_totals:
                subcategory_totals[behavior] += score

    latest_assessment = assessments[-1]
    processed = latest_assessment.get("processed", {})
    manager_info = processed.get("manager_info", {})

    total_assessments = len(assessments)
    subcategory_averages = {
        behavior: round(total / total_assessments, 2) if total_assessments else 0.0
        for behavior, total in subcategory_totals.items()
    }
    category_from_subcategories = {
        "trusting": round(sum(subcategory_averages.get(b, 0.0) for b in SUBCATEGORY_ORDER["trusting"]), 2),
        "tasking": round(sum(subcategory_averages.get(b, 0.0) for b in SUBCATEGORY_ORDER["tasking"]), 2),
        "tending": round(sum(subcategory_averages.get(b, 0.0) for b in SUBCATEGORY_ORDER["tending"]), 2),
    }
    subcategory_remarks = build_subcategory_remark_context(subcategory_averages)

    aggregated = {
        "manager_name": manager_info.get("manager_name", ""),
        "reporting_to": manager_info.get("reporting_to", ""),
        "raw_manager_name": manager_info.get("raw_manager_name", ""),
        "raw_reporting_to": manager_info.get("raw_reporting_to", ""),
        "total_assessments": total_assessments,
        "first_assessment": min(all_timestamps) if all_timestamps else "",
        "last_assessment": max(all_timestamps) if all_timestamps else "",
        "category_totals": category_totals,
        "category_averages": category_from_subcategories,
        "subcategory_totals": subcategory_totals,
        "subcategory_averages": subcategory_averages,
        "subcategory_remarks": subcategory_remarks,
        "score_distribution": {
            "trusting": {
                "min": min(category_scores_list["trusting"]) if category_scores_list["trusting"] else 0,
                "max": max(category_scores_list["trusting"]) if category_scores_list["trusting"] else 0,
                "std": statistics.stdev(category_scores_list["trusting"]) if len(category_scores_list["trusting"]) > 1 else 0,
            },
            "tasking": {
                "min": min(category_scores_list["tasking"]) if category_scores_list["tasking"] else 0,
                "max": max(category_scores_list["tasking"]) if category_scores_list["tasking"] else 0,
                "std": statistics.stdev(category_scores_list["tasking"]) if len(category_scores_list["tasking"]) > 1 else 0,
            },
            "tending": {
                "min": min(category_scores_list["tending"]) if category_scores_list["tending"] else 0,
                "max": max(category_scores_list["tending"]) if category_scores_list["tending"] else 0,
                "std": statistics.stdev(category_scores_list["tending"]) if len(category_scores_list["tending"]) > 1 else 0,
            },
        },
        "confidence_score": min(100, len(assessments) * 10),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    return aggregated

