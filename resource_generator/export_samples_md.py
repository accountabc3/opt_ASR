import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "opt_ASR" / "resource_generator" / "out"
BASE_INDEX_PATH = OUT_DIR / "base" / "index.json"
PASSED_PATH = OUT_DIR / "recheck" / "passed_candidates.json"
SAMPLES_DIR = OUT_DIR / "samples_md"
INDEX_PATH = SAMPLES_DIR / "index.json"

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)

def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def reset_output_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)

def resource_identity(resource_file: str) -> tuple[str, str]:
    parts = Path(resource_file).stem.split(".")
    base_id = parts[0]
    if len(parts) == 1:
        return base_id, "base"
    return base_id, parts[1]

def load_base_map() -> dict:
    data = load_json(BASE_INDEX_PATH)
    result = {}
    for sample in data.get("samples", []):
        result[str(sample["id"])] = sample
    return result

def strategy_order(strategy: str) -> int:
    order = {
        "base": 0,
        "semantic": 1,
        "context": 2,
        "payload": 3,
        "execution": 4,
        "verification": 5,
    }
    return order.get(strategy, 99)

def build_entry(sample_id: str, file_name: str, candidate: dict) -> dict:
    _, variant = resource_identity(candidate["resource_file"])
    return {
        "id": sample_id,
        "variant": variant,
        "file_name": file_name,
        "path": f"samples_md/{file_name}",
    }

def build_group(parent_index: int, base_sample: dict) -> dict:
    return {
        "parent_index": parent_index,
        "server": base_sample["server"],
        "tool": base_sample["target_tool"],
        "plan_dimensions": base_sample["plan_dimensions"],
        "samples": [],
    }

def export_samples() -> None:
    passed_candidates = load_json(PASSED_PATH)
    base_map = load_base_map()
    reset_output_dir(SAMPLES_DIR)

    sample_groups = []
    current_group = None
    current_parent_index = None
    ordered = sorted(
        passed_candidates,
        key=lambda item: (
            resource_identity(item["resource_file"])[0],
            strategy_order(item["mutation_strategy"]),
            item["resource_file"],
        ),
    )

    for candidate in ordered:
        source_path = Path(candidate["resource_path"])
        base_id, _ = resource_identity(candidate["resource_file"])
        mutation_strategy = candidate["mutation_strategy"]
        sample_id = f"{base_id}_{mutation_strategy}"
        file_name = f"{sample_id}.md"
        target_path = SAMPLES_DIR / file_name
        base_sample = base_map[base_id]
        parent_index = int(base_id)

        target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        if current_parent_index != parent_index:
            current_group = build_group(parent_index, base_sample)
            sample_groups.append(current_group)
            current_parent_index = parent_index
        current_group["samples"].append(build_entry(sample_id, file_name, candidate))

    index_data = {
        "sample_count": len(ordered),
        "sample_groups": sample_groups,
    }
    write_json(INDEX_PATH, index_data)
    print(f"Exported {len(ordered)} samples to {SAMPLES_DIR}")
    print(f"Wrote index: {INDEX_PATH}")

if __name__ == "__main__":
    export_samples()
