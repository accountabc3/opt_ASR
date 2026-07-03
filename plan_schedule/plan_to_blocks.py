import json
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from opt_ASR.plan_schedule.block_spec import get_block_definition

RULES_PATH = ROOT / "opt_ASR" / "rules.yaml"
PLAN_PATH = ROOT / "opt_ASR" / "plan_schedule" / "out" / "selected_plan.json"
OUTPUT_PATH = ROOT / "opt_ASR" / "plan_schedule" / "out" / "block_schedule.json"
MODULE_ORDER = [
    "context_block",
    "payload_block",
    "execution_block",
    "verification_block",
]

def load_rules() -> dict:
    with RULES_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)

def load_selected_plan() -> dict:
    with PLAN_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)

def flatten_plan(plan: dict) -> dict:
    return {
        "G": plan["task_semantics"]["G"],
        "A": plan["task_semantics"]["A"],
        "C": plan["task_semantics"]["C"],
        "S": plan["evidence_binding"]["S"],
        "E": plan["evidence_binding"]["E"],
        "T": plan["surface_realization"]["T"],
        "L": plan["surface_realization"]["L"],
        "R": plan["surface_realization"]["R"],
    }

def collect_required_blocks(rules: dict, values: dict) -> list[str]:
    block_ids = []

    add_blocks(block_ids, rules["genres"][values["G"]]["required_blocks"])
    add_blocks(block_ids, rules["actionability"][values["A"]]["required_blocks"])
    add_blocks(block_ids, rules["schema_binding"][values["S"]]["required_blocks"])
    add_blocks(block_ids, rules["evidence_depth"][values["E"]]["required_blocks"])
    add_blocks(block_ids, ["command_block"])

    return sort_block_ids(block_ids)

def collect_required_fields(rules: dict, values: dict) -> list[str]:
    field_names = []

    add_blocks(field_names, rules["schema_binding"][values["S"]].get("must_include_fields", []))

    if values["E"] in ["E3", "E4"]:
        add_blocks(field_names, ["tool_description", "parameter_type"])
    if values["E"] == "E4":
        add_blocks(field_names, ["evidence"])
    if values["A"] == "A4":
        add_blocks(field_names, ["oracle_type"])

    return field_names

def build_block_schedule(plan: dict, rules: dict) -> dict:
    values = flatten_plan(plan)
    block_ids = collect_required_blocks(rules, values)
    required_fields = collect_required_fields(rules, values)

    blocks = []
    for block_id in block_ids:
        definition = get_block_definition(block_id)
        block_fields = []
        for field_name in definition["allowed_fields"]:
            if field_name in required_fields:
                block_fields.append(field_name)

        blocks.append(
            {
                "module_id": definition["module_id"],
                "module_description": definition["module_description"],
                "block_id": block_id,
                "role": definition["role"],
                "required": True,
                "description": definition["description"],
                "format": definition["format"],
                "required_fields": block_fields,
            }
        )

    return {
        "plan_id": plan["plan_id"],
        "resource_plan": values,
        "resource_type": values["R"],
        "blocks": blocks,
    }

def add_blocks(target: list[str], source: list[str]) -> None:
    for item in source:
        if item not in target:
            target.append(item)

def sort_block_ids(block_ids: list[str]) -> list[str]:
    ordered = []
    for module_id in MODULE_ORDER:
        for block_id in block_ids:
            definition = get_block_definition(block_id)
            if definition["module_id"] == module_id and block_id not in ordered:
                ordered.append(block_id)
    return ordered

def save_block_schedule(block_schedule: dict) -> None:
    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(block_schedule, handle, ensure_ascii=False, indent=2)

def main() -> None:
    rules = load_rules()
    plan = load_selected_plan()
    block_schedule = build_block_schedule(plan, rules)
    save_block_schedule(block_schedule)
    print(json.dumps(block_schedule, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
