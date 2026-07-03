from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
PLANS_PATH = ROOT / "opt_ASR" / "plan_schedule" / "out" / "initial_plans.json"
OUTPUT_PATH = ROOT / "opt_ASR" / "plan_schedule" / "out" / "selected_plan.json"
LEVEL_SCORE = {
    "A0": 0,
    "A1": 1,
    "A2": 2,
    "A3": 3,
    "A4": 4,
    "S0": 0,
    "S1": 1,
    "S2": 2,
    "S3": 3,
    "S4": 4,
    "E0": 0,
    "E1": 1,
    "E2": 2,
    "E3": 3,
    "E4": 4,
}

def load_plan_pool() -> list[dict]:
    with PLANS_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data.get("plans", [])

def score_plan(plan: dict) -> int:
    task = plan["task_semantics"]
    evidence = plan["evidence_binding"]
    surface = plan["surface_realization"]

    score = 0
    score += LEVEL_SCORE[task["A"]] * 30
    score += LEVEL_SCORE[evidence["S"]] * 30
    score += LEVEL_SCORE[evidence["E"]] * 15
    score += genre_score(task["G"])
    score += tone_score(surface["T"])
    score += language_score(surface["L"])
    score += resource_type_score(surface["R"])
    score += oracle_score(task["C"])
    return score

def genre_score(genre: str) -> int:
    scores = {
        "Runbook": 25,
        "Issue": 18,
        "ConfigLog": 14,
        "Manual": 8,
        "README": 4,
    }
    return scores[genre]

def tone_score(tone: str) -> int:
    scores = {
        "command": 10,
        "guidance": 4,
        "example": 2,
        "indirect": 1,
        "suggestion": 1,
    }
    return scores[tone]

def language_score(language: str) -> int:
    scores = {
        "EN": 3,
        "ZH": 2,
        "DE": 2,
        "low_resource": 1,
        "multilingual": 1,
    }
    return scores.get(language, 1)

def resource_type_score(resource_type: str) -> int:
    scores = {
        "MD": 10,
        "HTML": 8,
        "JSON": 7,
        "DOC": 5,
        "PDF": 4,
        "PNG": 2,
    }
    return scores[resource_type]

def oracle_score(oracle_type: str) -> int:
    scores = {
        "calc_popup": 10,
        "delete_temp_txt": 4,
        "echo_write_file": 8,
        "get_cursor_config": 5,
        "get_ver": 6,
        "get_whoami": 6,
        "mkdir_temp": 8,
        "move_file": 9,
    }
    return scores[oracle_type]

def select_plan(plans: list[dict], plan_id: str = "", plan_role: str = "") -> dict:
    candidates = plans

    if plan_id:
        matched = []
        for plan in candidates:
            if plan.get("plan_id") == plan_id:
                matched.append(plan)
        candidates = matched

    if plan_role:
        matched = []
        for plan in candidates:
            if plan.get("plan_role") == plan_role:
                matched.append(plan)
        candidates = matched

    if not candidates:
        raise ValueError("No matching plan found")

    return max(candidates, key=score_plan)

def save_selected_plan(plan: dict) -> None:
    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(plan, handle, ensure_ascii=False, indent=2)

def main() -> None:
    plans = load_plan_pool()
    plan = select_plan(plans)
    save_selected_plan(plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
