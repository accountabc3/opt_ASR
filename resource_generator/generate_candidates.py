import json
from pathlib import Path
import yaml
from llm_compose_resource import compose_with_llm

ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "rules.yaml"
SELECTED_PLAN_PATH = ROOT / "plan_schedule" / "out" / "selected_plan.json"
BLOCK_SCHEDULE_PATH = ROOT / "plan_schedule" / "out" / "block_schedule.json"
VULN_CARD_PATH = ROOT / "vul_collector" / "vuln_card_collect" / "out" / "vuln_tool_info.json"
OUT_DIR = ROOT / "resource_generator" / "out"
BASE_DIR = OUT_DIR / "base"
INDEX_PATH = BASE_DIR / "index.json"

def load_rules() -> dict:
    with RULES_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)

def load_selected_plan() -> dict:
    with SELECTED_PLAN_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)

def load_block_schedule() -> dict:
    with BLOCK_SCHEDULE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)

def load_vulnerability_cards() -> dict:
    with VULN_CARD_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)

def ensure_output_dirs() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)

def load_index() -> dict:
    if not INDEX_PATH.exists():
        return {"sample_count": 0, "samples": []}
    with INDEX_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)

def save_index(index_data: dict) -> None:
    index_data["sample_count"] = len(index_data["samples"])
    INDEX_PATH.write_text(json.dumps(index_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def normalize_sample_id(value: str) -> str:
    stem = Path(value).stem
    if stem.startswith("seed_"):
        stem = stem[5:]
    if stem.isdigit():
        return f"{int(stem):04d}"
    return stem

def next_sample_name(index_data: dict) -> str:
    used_ids = set()
    for sample in index_data["samples"]:
        used_ids.add(normalize_sample_id(sample["id"]))
    number = 1
    while True:
        sample_id = f"{number:04d}"
        if sample_id not in used_ids and not (BASE_DIR / f"{sample_id}.md").exists():
            return sample_id
        number += 1

def find_existing_sample(index_data: dict, block_schedule: dict, binding: dict) -> dict | None:
    for sample in index_data["samples"]:
        if sample.get("plan_id") != block_schedule["plan_id"]:
            continue
        if sample.get("server") != binding["server"]:
            continue
        if sample.get("target_tool") != binding["target_tool"]:
            continue
        if sample.get("vulnerable_parameter") != binding["vulnerable_parameter"]:
            continue
        if sample.get("payload_command") != binding["payload_command"]:
            continue
        if sample.get("oracle_type") != binding["oracle_type"]:
            continue
        return sample
    return None

def build_bindings(cards: dict, payload_command: str, oracle_type: str) -> list[dict]:
    bindings = []
    for server_name, server_record in cards.items():
        for tool in server_record.get("tools", []):
            binding = build_binding(server_name, tool, payload_command, oracle_type)
            if binding is not None:
                bindings.append(binding)
    if not bindings:
        raise ValueError("No usable vulnerability cards found")
    return bindings

def build_binding(server_name: str, tool: dict, payload_command: str, oracle_type: str) -> dict | None:
    input_schema = tool.get("inputSchema") or {}
    tainted_args = input_schema.get("tainted_args") or []
    injection_rules = input_schema.get("injection_rules") or {}
    if len(tainted_args) != 1:
        return None

    tainted_arg = tainted_args[0]
    if tainted_arg not in injection_rules:
        return None

    parameter_schema = (input_schema.get("properties") or {}).get(tainted_arg, {})
    return {
        "server": server_name,
        "target_tool": tool.get("name", ""),
        "tool_description": tool.get("description", ""),
        "vulnerable_parameter": tainted_arg,
        "parameter_type": parameter_schema.get("type", "string"),
        "injection_template": str(injection_rules.get(tainted_arg, {}).get("template", "{base}&{payload}")),
        "argument_json": _build_argument_json(input_schema, tainted_arg, injection_rules, payload_command),
        "payload_command": payload_command,
        "oracle_type": oracle_type,
        "evidence": [
            f"Target tool: {tool.get('name', '')}",
            f"Target parameter: {tainted_arg}",
            f"Selected oracle goal: {oracle_type}",
            "The argument JSON preserves the selected target field and injected value.",
        ],
    }

def _enum_or_default(schema: dict):
    enum_values = schema.get("enum") or []
    if enum_values:
        return enum_values[0]
    if "default" in schema:
        return schema["default"]
    return None

def _default_value(schema: dict, field_name: str = ""):
    schema_type = schema.get("type")
    if schema_type == "string":
        return "test"
    if schema_type == "array":
        return []
    if schema_type == "object":
        return {}
    if schema_type == "number":
        return 1
    if schema_type == "boolean":
        return False
    return "test"

def _runtime_value_for_required_field(schema: dict, field_name: str):
    if schema.get("type") != "string":
        return None

    normalized_name = field_name.lower()
    if normalized_name == "repopath" or normalized_name.endswith("path"):
        return str(ROOT)
    return None

def _is_path_like_default(value) -> bool:
    if not isinstance(value, str):
        return False

    normalized = value.strip()
    if normalized in {"/", ".", "./", "\\", ".\\"}:
        return True
    return (
        normalized.startswith("/")
        or normalized.startswith("./")
        or normalized.startswith("../")
        or normalized.startswith(".\\")
        or normalized.startswith("..\\")
        or (len(normalized) >= 3 and normalized[1:3] in {":\\", ":/"})
    )

def _append_tainted_value(value, payload_command: str, tainted: bool, injection_rule: dict | None):
    if not tainted or not isinstance(value, str):
        return value

    template = "{base}&{payload}"
    if injection_rule and injection_rule.get("template"):
        template = str(injection_rule["template"])
    return template.replace("{base}", value).replace("{payload}", payload_command)

def _build_array_value(schema: dict, payload_command: str, tainted: bool = False, injection_rule: dict | None = None):
    item_schema = dict(schema.get("items") or {})
    return [
        _build_value(
            item_schema,
            payload_command,
            tainted,
            "",
            injection_rule,
        )
    ]

def _build_object_value(schema: dict, payload_command: str):
    properties = schema.get("properties") or {}
    required = schema.get("required") or list(properties.keys())
    result = {}
    for field_name in required:
        field_schema = properties.get(field_name, {})
        result[field_name] = _build_value(field_schema, payload_command, False, field_name, None)
    return result

def _build_value(
    schema: dict,
    payload_command: str,
    tainted: bool = False,
    field_name: str = "",
    injection_rule: dict | None = None,
):
    if not tainted:
        runtime_value = _runtime_value_for_required_field(schema, field_name)
        if runtime_value is not None:
            return runtime_value

    value = _enum_or_default(schema)
    if value is not None:
        if tainted and _is_path_like_default(value):
            value = "test"
        return _append_tainted_value(value, payload_command, tainted, injection_rule)

    schema_type = schema.get("type")
    if schema_type == "string":
        value = _default_value(schema, field_name)
        if tainted and _is_path_like_default(value):
            value = "test"
        return _append_tainted_value(value, payload_command, tainted, injection_rule)
    if schema_type == "array":
        return _build_array_value(schema, payload_command, tainted, injection_rule)
    if schema_type == "object":
        return _build_object_value(schema, payload_command)

    value = _default_value(schema, field_name)
    return _append_tainted_value(value, payload_command, tainted, injection_rule)

def _build_argument_json(input_schema: dict, tainted_arg: str, injection_rules: dict, payload_command: str) -> dict:
    properties = input_schema.get("properties") or {}
    required = input_schema.get("required") or []
    argument = {}
    field_names = list(required)
    if tainted_arg not in field_names:
        field_names.append(tainted_arg)

    for name in field_names:
        schema = properties.get(name, {})
        argument[name] = _build_value(
            schema,
            payload_command,
            name == tainted_arg,
            name,
            injection_rules.get(name),
        )
    return argument

def command_for_plan(rules: dict, selected_plan: dict) -> tuple[str, str]:
    oracle_type = selected_plan["task_semantics"]["C"]
    payload_command = rules["oracle_goal"][oracle_type]["observation"]
    return payload_command, oracle_type

def build_sample_record(sample_id: str, block_schedule: dict, binding: dict) -> dict:
    blocks = []
    for block in block_schedule["blocks"]:
        blocks.append(block["block_id"])

    return {
        "id": sample_id,
        "file_path": f"out/base/{sample_id}.md",
        "server": binding["server"],
        "target_tool": binding["target_tool"],
        "tool_description": binding["tool_description"],
        "vulnerable_parameter": binding["vulnerable_parameter"],
        "parameter_type": binding["parameter_type"],
        "argument_json": binding["argument_json"],
        "payload_command": binding["payload_command"],
        "oracle_type": binding["oracle_type"],
        "plan_id": block_schedule["plan_id"],
        "plan_dimensions": block_schedule["resource_plan"],
        "blocks": blocks,
        "block_schedule": block_schedule,
    }

def write_outputs(block_schedule: dict, binding: dict, content: str) -> None:
    ensure_output_dirs()
    index_data = load_index()
    existing_sample = find_existing_sample(index_data, block_schedule, binding)
    if existing_sample is None:
        sample_id = next_sample_name(index_data)
    else:
        sample_id = normalize_sample_id(existing_sample["id"])
    resource_path = BASE_DIR / f"{sample_id}.md"
    sample_record = build_sample_record(sample_id, block_schedule, binding)

    resource_path.write_text(content, encoding="utf-8")
    if existing_sample is None:
        index_data["samples"].append(sample_record)
    else:
        for i in range(len(index_data["samples"])):
            old_id = index_data["samples"][i].get("id", "")
            if normalize_sample_id(old_id) == sample_id:
                index_data["samples"][i] = sample_record
                break
    save_index(index_data)

    print(f"Wrote resource: {resource_path}")
    print(f"Wrote index: {INDEX_PATH}")

def main() -> None:
    rules = load_rules()
    selected_plan = load_selected_plan()
    block_schedule = load_block_schedule()
    payload_command, oracle_type = command_for_plan(rules, selected_plan)
    cards = load_vulnerability_cards()
    bindings = build_bindings(cards, payload_command, oracle_type)
    for index, binding in enumerate(bindings, start=1):
        print(
            f"[{index}/{len(bindings)}] "
            f"{binding['server']}::{binding['target_tool']}"
        )
        content = compose_with_llm(block_schedule, binding, rules)
        write_outputs(block_schedule, binding, content)

if __name__ == "__main__":
    main()
