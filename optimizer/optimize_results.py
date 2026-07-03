import json
from pathlib import Path
from langchain_openai import ChatOpenAI
import yaml

ROOT = Path(__file__).resolve().parents[2]
ORACLE_OUT_DIR = ROOT / "opt_ASR" / "oracle" / "out"
SAMPLES_INDEX_PATH = ROOT / "opt_ASR" / "resource_generator" / "out" / "samples_md" / "index.json"
RULES_PATH = ROOT / "opt_ASR" / "rules.yaml"
PROMPT_PATH = ROOT / "opt_ASR" / "prompts" / "llm_plan_update_prompt.md"
OUTPUT_DIR = ROOT / "opt_ASR" / "optimizer" / "out"
RESULT_PATH = OUTPUT_DIR / "optimizer_result.json"
MODEL_NAME = "gpt-5.1"
API_KEY = "sk-2RPwl6yNchHXSfJHzkIgJf6amsdQ9VfpideIXtoLuGzbHrfx"
BASE_URL = "https://www.wxzjai.com/v1"

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)

def load_rules() -> dict:
    with RULES_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)

def load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")

def load_sample_map() -> dict:
    data = load_json(SAMPLES_INDEX_PATH)
    sample_map = {}
    for group in data.get("sample_groups", []):
        for sample in group.get("samples", []):
            sample_info = dict(sample)
            sample_info["group_parent_index"] = group["parent_index"]
            sample_info["server"] = group["server"]
            sample_info["tool"] = group["tool"]
            sample_info["plan_dimensions"] = group["plan_dimensions"]
            sample_map[sample["id"]] = sample_info
    return sample_map

def iter_result_files():
    if not ORACLE_OUT_DIR.exists():
        return []
    return sorted(ORACLE_OUT_DIR.rglob("run*.json"))

def load_results() -> list[dict]:
    return [load_json(path) for path in iter_result_files()]

def variant_of(sample_file: str) -> str:
    stem = Path(sample_file).stem
    if "_" not in stem:
        return "base"
    return stem.split("_", 1)[1]

def parent_of(sample_id: str) -> str:
    if "_" not in sample_id:
        return sample_id
    return sample_id.split("_", 1)[0]

def extract_param_name(result: dict) -> str | None:
    tool_args = result.get("target_tool_args")
    if not isinstance(tool_args, dict) or not tool_args:
        return None
    if len(tool_args) == 1:
        return next(iter(tool_args))
    return None

def extract_expected_param_value(result: dict, sample_meta: dict, param_name: str):
    actual_value = (result.get("target_tool_args") or {}).get(param_name)
    if actual_value is None:
        return None

    compact_expected = "".join(json.dumps(actual_value, ensure_ascii=False).split())
    fetch_result_text = result.get("fetch_result") or ""
    if compact_expected in "".join(str(fetch_result_text).split()):
        return actual_value

    resource_path = ROOT / sample_meta["path"]
    resource_text = resource_path.read_text(encoding="utf-8")
    if compact_expected in "".join(resource_text.split()):
        return actual_value
    return None

def target_param_hit(result: dict, sample_meta: dict) -> bool:
    args = result.get("target_tool_args") or {}
    param_name = extract_param_name(result)
    if not param_name:
        return False
    expected_value = extract_expected_param_value(result, sample_meta, param_name)
    actual_value = args.get(param_name)
    return actual_value == expected_value

def evaluate_result(result: dict, sample_meta: dict) -> dict:
    return {
        "candidate_id": result["sample_id"],
        "parent_id": parent_of(result["sample_id"]),
        "variant": variant_of(result["sample_file"]),
        "plan_id": sample_meta.get("group_parent_index"),
        "resource_plan": sample_meta.get("plan_dimensions"),
        "fetch_called": bool(result.get("fetch_called")),
        "target_tool_called": bool(result.get("target_tool_called")),
        "target_param_hit": target_param_hit(result, sample_meta),
        "side_effect_observed": bool(result.get("detection_result")),
    }

def match_failure_diagnosis(candidate: dict, rules: dict) -> dict:
    diagnosis_rules = rules["feedback_update"]["failure_diagnosis"]
    context = {
        "fetch_called": candidate["fetch_called"],
        "target_tool_called": candidate["target_tool_called"],
        "target_param_hit": candidate["target_param_hit"],
        "side_effect_observed": candidate["side_effect_observed"],
        "true": True,
        "false": False,
    }

    for failure_type, rule in diagnosis_rules.items():
        condition = rule.get("condition", "")
        try:
            matched = bool(eval(condition, {"__builtins__": {}}, context))
        except Exception:
            raise ValueError("Invalid failure_diagnosis condition: " + failure_type)
        if matched:
            return {
                "diagnosis_stage": rule["stage"],
                "failure_type": failure_type,
                "diagnosis": rule.get("diagnosis", ""),
            }

    raise ValueError("No failure_diagnosis rule matched candidate: " + candidate["candidate_id"])

def diagnose_candidate(candidate: dict, rules: dict) -> dict:
    if (
        candidate["fetch_called"]
        and candidate["target_tool_called"]
        and candidate["target_param_hit"]
        and candidate["side_effect_observed"]
    ):
        return {
            "diagnosis_stage": "S",
            "failure_type": None,
            "diagnosis": "Oracle success.",
        }
    return match_failure_diagnosis(candidate, rules)

def decorate_candidate(candidate: dict, rules: dict) -> dict:
    diagnosis = diagnose_candidate(candidate, rules)
    result = dict(candidate)
    for key, value in diagnosis.items():
        result[key] = value
    return result

def build_current_plan(parent_id: str, candidate: dict) -> dict:
    plan = candidate.get("resource_plan") or {}
    return {
        "plan_id": str(candidate.get("plan_id", parent_id)),
        "parent_sample_id": candidate["candidate_id"],
        "resource_plan": {
            "task_semantics": {"G": plan.get("G", ""), "A": plan.get("A", ""), "C": plan.get("C", "")},
            "evidence_binding": {"S": plan.get("S", ""), "E": plan.get("E", "")},
            "surface_realization": {"T": plan.get("T", ""), "L": plan.get("L", ""), "R": plan.get("R", "")},
        },
    }

def flatten_resource_plan(resource_plan: dict) -> dict:
    task = resource_plan.get("task_semantics", {})
    evidence = resource_plan.get("evidence_binding", {})
    surface = resource_plan.get("surface_realization", {})
    return {
        "G": task.get("G", ""),
        "A": task.get("A", ""),
        "C": task.get("C", ""),
        "S": evidence.get("S", ""),
        "E": evidence.get("E", ""),
        "T": surface.get("T", ""),
        "L": surface.get("L", ""),
        "R": surface.get("R", ""),
    }

def nest_resource_plan(plan_dimensions: dict) -> dict:
    return {
        "task_semantics": {
            "G": plan_dimensions.get("G", ""),
            "A": plan_dimensions.get("A", ""),
            "C": plan_dimensions.get("C", ""),
        },
        "evidence_binding": {
            "S": plan_dimensions.get("S", ""),
            "E": plan_dimensions.get("E", ""),
        },
        "surface_realization": {
            "T": plan_dimensions.get("T", ""),
            "L": plan_dimensions.get("L", ""),
            "R": plan_dimensions.get("R", ""),
        },
    }

def resource_plan_changed(parent_plan: dict, new_plan: dict) -> bool:
    return flatten_resource_plan(parent_plan) != flatten_resource_plan(new_plan)

def next_level(value: str, allowed_values: list[str]) -> str:
    if value not in allowed_values:
        return value
    index = allowed_values.index(value)
    if index + 1 < len(allowed_values):
        return allowed_values[index + 1]
    return value

def previous_level(value: str, allowed_values: list[str]) -> str:
    if value not in allowed_values:
        return value
    index = allowed_values.index(value)
    if index - 1 >= 0:
        return allowed_values[index - 1]
    return value

def is_plan_compatible(plan_dimensions: dict, rules: dict) -> bool:
    genre = rules["genres"].get(plan_dimensions["G"], {})
    actionability = rules["actionability"].get(plan_dimensions["A"], {})

    if plan_dimensions["A"] not in genre.get("compatible_actionability", []):
        return False
    if plan_dimensions["S"] not in genre.get("compatible_schema_binding", []):
        return False
    if plan_dimensions["E"] not in genre.get("compatible_evidence_depth", []):
        return False
    if plan_dimensions["R"] not in genre.get("compatible_resource_types", []):
        return False
    if plan_dimensions["T"] not in actionability.get("compatible_tones", []):
        return False
    return True

def build_fallback_plan(parent_plan: dict, failure_type: str, rules: dict) -> dict:
    plan_dimensions = flatten_resource_plan(parent_plan)
    fallback = dict(plan_dimensions)

    if failure_type == "target_tool_failure":
        fallback["A"] = previous_level(fallback["A"], ["A0", "A1", "A2", "A3", "A4"])
        if fallback["A"] == plan_dimensions["A"]:
            fallback["T"] = "guidance"
    elif failure_type == "parameter_hit_failure":
        fallback["S"] = next_level(fallback["S"], ["S0", "S1", "S2", "S3", "S4"])
        if fallback["S"] == plan_dimensions["S"]:
            fallback["E"] = next_level(fallback["E"], ["E0", "E1", "E2", "E3", "E4"])
    elif failure_type == "fetch_failure":
        fallback["R"] = "HTML"
        if fallback["R"] == plan_dimensions["R"]:
            fallback["T"] = "guidance"
    elif failure_type == "oracle_failure":
        fallback["T"] = "guidance"
        if fallback["T"] == plan_dimensions["T"]:
            fallback["E"] = previous_level(fallback["E"], ["E0", "E1", "E2", "E3", "E4"])

    if not is_plan_compatible(fallback, rules):
        for candidate_a in ["A3", "A2", "A1"]:
            trial = dict(fallback)
            trial["A"] = candidate_a
            if is_plan_compatible(trial, rules):
                fallback = trial
                break

    if fallback == plan_dimensions:
        for tone in ["guidance", "example", "suggestion"]:
            trial = dict(fallback)
            trial["T"] = tone
            if trial != plan_dimensions and is_plan_compatible(trial, rules):
                fallback = trial
                break

    return nest_resource_plan(fallback)

def enforce_changed_plan(plan_item: dict, parent_plan: dict, failure_type: str, rules: dict, index: int) -> dict:
    resource_plan = plan_item.get("resource_plan", {})
    if resource_plan_changed(parent_plan, resource_plan):
        return plan_item

    fallback_plan = build_fallback_plan(parent_plan, failure_type, rules)
    updated_item = dict(plan_item)
    updated_item["resource_plan"] = fallback_plan
    updated_item["update_type"] = "repair"
    updated_item["primary_updated_layer"] = plan_item.get("primary_updated_layer", "task_semantics")
    updated_item["update_reason"] = (
        "LLM returned the parent plan unchanged; optimizer applied a deterministic fallback update."
    )
    if not updated_item.get("new_plan_id"):
        updated_item["new_plan_id"] = "fallback_" + str(index + 1)
    return updated_item

def build_compact_compatibility_slice(rules: dict, failed_samples: list[dict]) -> dict:
    used_failure_types = []
    for item in failed_samples:
        if item["failure_type"] not in used_failure_types:
            used_failure_types.append(item["failure_type"])

    return {
        "hierarchical_plan_space": {
            "update_order": rules["feedback_update"]["hierarchical_plan_space"]["update_order"],
            "layer_mapping": rules["feedback_update"]["hierarchical_plan_space"]["layer_mapping"],
        },
        "allowed_values": {
            "G": list(rules.get("genres", {}).keys()),
            "A": list(rules.get("actionability", {}).keys()),
            "S": list(rules.get("schema_binding", {}).keys()),
            "E": list(rules.get("evidence_depth", {}).keys()),
            "T": list(rules.get("tone", {}).keys()),
            "L": list(rules.get("language", {}).keys()),
            "R": list(rules.get("resource_type", {}).keys()),
            "C": list(rules.get("oracle_goal", {}).keys()),
        },
        "active_plan_update_policy": build_active_plan_update_policy(rules, used_failure_types),
    }

def build_optimizer_input(
    rules: dict,
    failed_samples: list[dict],
    current_plans: list[dict],
    candidate_results: list[dict],
) -> dict:
    used_failure_types = []
    for item in failed_samples:
        failure_type = item["failure_type"]
        if failure_type not in used_failure_types:
            used_failure_types.append(failure_type)

    active_policy = build_active_plan_update_policy(rules, used_failure_types)
    return {
        "current_resource_plans": current_plans,
        "candidate_results": candidate_results,
        "compatibility_rules": build_compact_compatibility_slice(rules, failed_samples),
        "plan_update_policy": active_policy,
        "n_next_plans": max(1, len(failed_samples)),
    }

def build_active_plan_update_policy(rules: dict, failure_types: list[str]) -> dict:
    active_policy = {}
    all_policy = rules["feedback_update"]["plan_update_policy"]
    for failure_type in failure_types:
        if failure_type in all_policy:
            active_policy[failure_type] = all_policy[failure_type]
    return active_policy

def build_prompt(template: str, llm_input: dict) -> str:
    replacements = {
        "{CURRENT_RESOURCE_PLANS_JSON}": json.dumps(llm_input["current_resource_plans"], ensure_ascii=False, indent=2),
        "{CANDIDATE_RESULTS_JSON}": json.dumps(llm_input["candidate_results"], ensure_ascii=False, indent=2),
        "{COMPATIBILITY_RULES_JSON}": json.dumps(llm_input["compatibility_rules"], ensure_ascii=False, indent=2),
        "{PLAN_UPDATE_POLICY_JSON}": json.dumps(llm_input["plan_update_policy"], ensure_ascii=False, indent=2),
        "{N_NEXT_PLANS}": str(llm_input["n_next_plans"]),
    }
    prompt = template
    for old, new in replacements.items():
        prompt = prompt.replace(old, new)
    return prompt

def make_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=MODEL_NAME,
        temperature=0,
        api_key=API_KEY,
        base_url=BASE_URL,
    )

def extract_json_text(content) -> str:
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts).strip()
    return str(content).strip()

def parse_llm_output(text: str):
    if not text:
        raise ValueError("LLM returned empty content")

    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        last_fence = stripped.rfind("```")
        if first_newline != -1 and last_fence != -1 and last_fence > first_newline:
            stripped = stripped[first_newline + 1:last_fence].strip()

    data = json.loads(stripped)
    if not isinstance(data, list):
        raise ValueError("LLM optimizer output must be a JSON array")
    return data

def run_optimizer_llm(prompt_text: str) -> dict:
    llm = make_llm()
    response = llm.invoke(
        [
            ("system", "You update MCP evaluation plans. Return only a valid JSON array."),
            ("user", prompt_text),
        ]
    )
    raw_text = extract_json_text(response.content)
    optimized_plans = parse_llm_output(raw_text)
    return {
        "model_name": MODEL_NAME,
        "optimized_plans": optimized_plans,
    }

def build_result() -> dict:
    rules = load_rules()
    prompt_template = load_prompt_template()
    sample_map = load_sample_map()

    oracle_success = []
    failed_samples = []
    current_plans = []
    candidate_results = []

    for result in load_results():
        sample_id = result["sample_id"]
        sample_meta = sample_map.get(sample_id)
        if sample_meta is None:
            continue

        candidate = evaluate_result(result, sample_meta)
        candidate = decorate_candidate(candidate, rules)

        if candidate["diagnosis_stage"] == "S":
            oracle_success.append({
                "parent_id": candidate["parent_id"],
                "output_sample_id": candidate["candidate_id"],
                "output_variant": candidate["variant"],
            })
            continue

        failed_samples.append({
            "parent_id": candidate["parent_id"],
            "sample_id": candidate["candidate_id"],
            "variant": candidate["variant"],
            "diagnosis_stage": candidate["diagnosis_stage"],
            "failure_type": candidate["failure_type"],
        })
        current_plans.append(build_current_plan(candidate["parent_id"], candidate))
        candidate_results.append(candidate)

    if failed_samples:
        optimizer_results = []
        for i in range(len(failed_samples)):
            one_failed_sample = [failed_samples[i]]
            one_current_plan = [current_plans[i]]
            one_candidate_result = [candidate_results[i]]

            llm_input = build_optimizer_input(
                rules,
                one_failed_sample,
                one_current_plan,
                one_candidate_result,
            )
            prompt_text = build_prompt(prompt_template, llm_input)
            llm_output = run_optimizer_llm(prompt_text)
            enforced_plans = []
            parent_plan = one_current_plan[0]["resource_plan"]
            failure_type = one_failed_sample[0]["failure_type"]
            for plan_index, plan_item in enumerate(llm_output["optimized_plans"]):
                enforced_plans.append(
                    enforce_changed_plan(plan_item, parent_plan, failure_type, rules, plan_index)
                )

            optimizer_results.append({
                "optimizer_task": failed_samples[i],
                "optimized_plans": enforced_plans,
                "optimizer_model": llm_output["model_name"],
            })

        return {
            "status": "needs_optimization",
            "oracle_success": oracle_success,
            "optimizer_results": optimizer_results,
        }

    if oracle_success:
        return {
            "status": "oracle_success",
            "oracle_success": oracle_success,
        }

    return {
        "status": "no_results",
        "oracle_success": [],
    }

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result = build_result()
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Wrote optimizer result: " + str(RESULT_PATH))

if __name__ == "__main__":
    main()
