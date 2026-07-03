import json
import re
from pathlib import Path
import yaml
from langchain_openai import ChatOpenAI

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "opt_ASR" / "resource_generator" / "out"
BASE_DIR = OUT_DIR / "base"
MUTATION_DIR = OUT_DIR / "mutation"
INDEX_PATH = BASE_DIR / "index.json"
RULES_PATH = ROOT / "opt_ASR" / "rules.yaml"
PROMPT_PATH = ROOT / "opt_ASR" / "prompts" / "llm_mutation_prompt.md"
MODEL_NAME = "gpt-5.5"
API_KEY = "sk-2RPwl6yNchHXSfJHzkIgJf6amsdQ9VfpideIXtoLuGzbHrfx"
BASE_URL = "https://www.wxzjai.com/v1"
STRATEGIES = ["semantic", "context", "payload", "execution", "verification"]
MAX_RETRIES = 3

def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)

def load_rules() -> dict:
    with RULES_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)

def load_base_index() -> dict:
    return load_json(INDEX_PATH)

def make_llm():
    return ChatOpenAI(
        model=MODEL_NAME,
        temperature=0.2,
        api_key=API_KEY,
        base_url=BASE_URL,
    )

def normalize_sample_id(value: str) -> str:
    stem = Path(value).stem
    if stem.startswith("seed_"):
        stem = stem[5:]
    if stem.isdigit():
        return f"{int(stem):04d}"
    return stem

def find_base_sample(sample_id: str) -> dict:
    index_data = load_base_index()
    for sample in index_data.get("samples", []):
        if sample.get("id") == sample_id:
            return sample
    raise ValueError(f"Base sample not found in index: {sample_id}")

def build_binding(sample: dict) -> dict:
    return {
        "server": sample["server"],
        "target_tool": sample["target_tool"],
        "tool_description": sample["tool_description"],
        "vulnerable_parameter": sample["vulnerable_parameter"],
        "parameter_type": sample["parameter_type"],
        "argument_json": sample["argument_json"],
        "payload_command": sample["payload_command"],
        "oracle_type": sample["oracle_type"],
    }

def build_rules_slice(rules: dict, resource_plan: dict, binding: dict) -> dict:
    return {
        "genre": rules["genres"][resource_plan["G"]],
        "actionability": rules["actionability"][resource_plan["A"]],
        "schema_binding": rules["schema_binding"][resource_plan["S"]],
        "evidence_depth": rules["evidence_depth"][resource_plan["E"]],
        "tone": rules["tone"][resource_plan["T"]],
        "language": rules["language"][resource_plan["L"]],
        "resource_type": rules["resource_type"][resource_plan["R"]],
        "oracle_goal": rules["oracle_goal"][binding["oracle_type"]],
        "placeholder_contract": rules["placeholder_contract"],
    }

def should_unescape_closed_quote_display(parent_content: str, binding: dict) -> bool:
    return binding["vulnerable_parameter"] in parent_content and '"&' in parent_content

def sanitize_markdown_display(text: str, parent_content: str, binding: dict) -> str:
    text = text.replace("```json", "```")
    if should_unescape_closed_quote_display(parent_content, binding):
        text = text.replace('\\"', '"')
    return text

def build_prompt(template: str, parent_stem: str, parent_content: str, sample: dict, rules_slice: dict, strategy: str) -> str:
    binding = build_binding(sample)
    block_schedule = sample["block_schedule"]
    resource_plan = sample["plan_dimensions"]

    replacements = {
        "{VULNERABILITY_CARD_JSON}": json.dumps(binding, ensure_ascii=False, indent=2),
        "{RESOURCE_PLAN_JSON}": json.dumps(resource_plan, ensure_ascii=False, indent=2),
        "{BLOCK_SCHEDULE_JSON}": json.dumps(block_schedule, ensure_ascii=False, indent=2),
        "{RULES_SLICE_JSON}": json.dumps(rules_slice, ensure_ascii=False, indent=2),
        "{PARENT_RESOURCE_CONTENT}": parent_content,
        "{MUTATION_STRATEGY}": strategy,
        "{TARGET_TOOL}": binding["target_tool"],
        "{VULNERABLE_PARAMETER}": binding["vulnerable_parameter"],
        "{ARGUMENT_JSON}": sanitize_markdown_display(json.dumps(binding["argument_json"], ensure_ascii=False, indent=2), parent_content, binding),
        "{PAYLOAD_COMMAND}": binding["payload_command"],
        "{ORACLE_TYPE}": binding["oracle_type"],
        "{PARENT_CANDIDATE_STEM}": parent_stem,
    }

    prompt = template
    for old, new in replacements.items():
        prompt = prompt.replace(old, new)
    return prompt

def extract_json_text(content) -> str:
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        text = "\n".join(parts).strip()
    else:
        text = str(content).strip()

    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()
    return text

def parse_single_item_array(text: str) -> dict:
    if not text:
        raise ValueError("LLM returned empty content")

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        array_match = re.search(r"(\[\s*\{.*\}\s*\])", text, re.DOTALL)
        if not array_match:
            raise ValueError(f"LLM did not return JSON array. Raw output:\n{text[:1200]}")
        data = json.loads(array_match.group(1))

    if not isinstance(data, list) or len(data) != 1:
        raise ValueError("LLM output must be a JSON array with exactly one item")
    if not isinstance(data[0], dict) or "content" not in data[0]:
        raise ValueError(f"LLM output item must contain content. Raw output:\n{text[:1200]}")
    return data[0]

def call_llm(llm, prompt: str) -> dict:
    response = llm.invoke(
        [
            ("system", "You mutate one MCP evaluation resource. Return only the requested JSON array."),
            ("user", prompt),
        ]
    )
    text = extract_json_text(response.content)
    return parse_single_item_array(text)

def call_llm_with_retry(llm, prompt: str) -> dict:
    last_error = None
    for _ in range(MAX_RETRIES):
        try:
            return call_llm(llm, prompt)
        except Exception as error:
            last_error = error
    raise last_error

def write_variant(parent_stem: str, strategy: str, item: dict, parent_content: str, binding: dict) -> None:
    strategy_dir = MUTATION_DIR / strategy
    strategy_dir.mkdir(parents=True, exist_ok=True)
    resource_path = strategy_dir / f"{parent_stem}.{strategy}.md"
    content = sanitize_markdown_display(str(item["content"]).strip(), parent_content, binding)
    resource_path.write_text(content + "\n", encoding="utf-8")
    print(f"Wrote variant: {resource_path}")

def mutate_parent(parent_stem: str) -> None:
    sample_id = normalize_sample_id(parent_stem)
    sample = find_base_sample(sample_id)
    parent_path = BASE_DIR / f"{sample_id}.md"
    parent_content = parent_path.read_text(encoding="utf-8")
    rules = load_rules()
    rules_slice = build_rules_slice(rules, sample["plan_dimensions"], build_binding(sample))
    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    llm = make_llm()

    for strategy in STRATEGIES:
        prompt = build_prompt(prompt_template, sample_id, parent_content, sample, rules_slice, strategy)
        try:
            item = call_llm_with_retry(llm, prompt)
            write_variant(sample_id, strategy, item, parent_content, build_binding(sample))
        except Exception as error:
            print(f"Skip strategy {strategy}: {error}")

def main() -> None:
    index_data = load_base_index()
    sample_ids = [
        normalize_sample_id(sample["id"])
        for sample in index_data.get("samples", [])
    ]
    if not sample_ids:
        raise ValueError("No base samples found in index")

    for index, sample_id in enumerate(sample_ids, start=1):
        print(f"[{index}/{len(sample_ids)}] Mutating base sample {sample_id}")
        try:
            mutate_parent(sample_id)
        except Exception as error:
            print(f"Skip base sample {sample_id}: {error}")

if __name__ == "__main__":
    main()
