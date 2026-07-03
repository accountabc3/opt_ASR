import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / "opt_ASR" / "rules.yaml"
OUTPUT_PATH = ROOT / "opt_ASR" / "plan_schedule" / "out" / "initial_plans.json"

def load_rules() -> dict:
    with RULES_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)

def build_candidate_plans(rules: dict) -> list[dict]:
    genre_rules = rules.get("genres", {})

    plans = []
    counter = 0

    for g_value, genre_rule in genre_rules.items():
        # Follow rules.yaml: G selects compatible A/S/E/R values.
        g_values = [g_value]
        a_values = genre_rule["compatible_actionability"]
        s_values = genre_rule["compatible_schema_binding"]
        e_values = genre_rule["compatible_evidence_depth"]
        r_values = genre_rule["compatible_resource_types"]
        
        l_values = list(rules["language"].keys())
        c_values = list(rules["oracle_goal"].keys())

        for a_value in a_values:
            # Follow rules.yaml: A selects compatible T values.
            t_values = tone_values_for_actionability(rules, a_value)

            for s_value in s_values:
                for e_value in e_values:
                    if not plan_fits_genre(rules, genre_rule, a_value, s_value, e_value):
                        continue
                    for g_selected in g_values:
                        for t_value in t_values:
                            for l_value in l_values:
                                for r_value in r_values:
                                    for c_value in c_values:
                                        counter += 1
                                        plans.append(
                                            {
                                                "plan_id": build_plan_id(counter, g_selected, a_value, s_value, e_value, c_value),
                                                "task_semantics": {
                                                    "G": g_selected,
                                                    "A": a_value,
                                                    "C": c_value,
                                                },
                                                "evidence_binding": {
                                                    "S": s_value,
                                                    "E": e_value,
                                                },
                                                "surface_realization": {
                                                    "T": t_value,
                                                    "L": l_value,
                                                    "R": r_value,
                                                },
                                                "n_instances": 1,
                                                "plan_role": infer_plan_role(g_value, a_value, s_value, e_value),
                                            }
                                        )
    return plans

def tone_values_for_actionability(rules: dict, a_value: str) -> list[str]:
    return rules["actionability"][a_value]["compatible_tones"]

def plan_fits_genre(
    rules: dict,
    genre_rules: dict,
    a_value: str,
    s_value: str,
    e_value: str,
) -> bool:
    required_blocks = set(genre_rules.get("required_blocks", []))
    forbidden_blocks = set(genre_rules.get("forbidden_blocks", []))
    required_blocks.update(required_blocks_for_level(rules, "actionability", a_value))
    required_blocks.update(required_blocks_for_level(rules, "schema_binding", s_value))
    required_blocks.update(required_blocks_for_level(rules, "evidence_depth", e_value))
    required_blocks.add("command_block")

    for block_id in required_blocks:
        if block_id in forbidden_blocks:
            return False
    return True

def required_blocks_for_level(rules: dict, group: str, level: str) -> list[str]:
    group_rules = rules.get(group, {})
    level_rules = group_rules.get(level, {})
    return level_rules.get("required_blocks", [])

def build_plan_id(
    counter: int,
    g_value: str,
    a_value: str,
    s_value: str,
    e_value: str,
    c_value: str,
) -> str:
    return f"P{counter:04d}_{g_value.lower()}_{a_value.lower()}_{s_value.lower()}_{e_value.lower()}_{c_value}"

def infer_plan_role(genre: str, a_value: str, s_value: str, e_value: str) -> str:
    if genre == "Runbook" and a_value == "A4" and s_value == "S4" and e_value == "E4":
        return "strong_binding_probe"
    if genre == "Runbook":
        return "actionable_probe"
    if genre == "Issue":
        return "mid_actionability_probe"
    if genre == "Manual":
        return "weak_binding_probe"
    return "baseline"

def write_initial_plans(plans: list[dict]) -> None:
    payload = {
        "plans": plans,
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

def main() -> None:
    rules = load_rules()
    plans = build_candidate_plans(rules)
    write_initial_plans(plans)
    print(json.dumps({"output": str(OUTPUT_PATH), "plan_count": len(plans)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
