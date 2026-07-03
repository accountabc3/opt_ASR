import argparse
import asyncio
import os
import run_mcp_ipi

ROOT = os.path.dirname(os.path.abspath(__file__))

os.environ["HTTP_PROXY"] = "http://58.206.208.107:7890"
os.environ["HTTPS_PROXY"] = "http://58.206.208.107:7890"
os.environ["ALL_PROXY"] = "http://58.206.208.107:7890"

def expand_sample_ids(run_config):
    parent_start = run_config.get("sample_parent_start")
    parent_end = run_config.get("sample_parent_end")
    sample_variants = run_config.get("sample_variants", [])
    if parent_start is not None and parent_end is not None and sample_variants:
        expanded = []
        for parent_index in range(parent_start, parent_end + 1):
            parent_id = f"{parent_index:04d}"
            for variant in sample_variants:
                expanded.append(f"{parent_id}_{variant}")
        return expanded

    raise ValueError(
        "run config must provide sample_parent_start/sample_parent_end with non-empty sample_variants"
    )


async def run_batch(run_config):
    sample_ids = expand_sample_ids(run_config)
    if not sample_ids:
        raise ValueError("no samples selected by run config")
    repeat_count = run_config["repeat_count"]
    total = len(sample_ids) * repeat_count
    current = 0
    for sample_id in sample_ids:
        for repeat_index in range(1, repeat_count+1):
            current = current + 1
            print("Running {} of {} samples: sample_id = {}, repeat_index = {}".format(current, total, sample_id, repeat_index))
            each_sample_config = {
                "api_key": run_config["api_key"],
                "base_url": run_config["base_url"],
                "model_name": run_config["model_name"],
                "github_blob_base": run_config["github_blob_base"],
                "github_raw_base": run_config["github_raw_base"],
                "sample_id": sample_id,
                "repeat_index": repeat_index,
                "max_output_tokens": run_config["max_output_tokens"],
            }
            try:
                await run_mcp_ipi.run_evaluation(each_sample_config)
            except Exception as e:
                print("failed: sample_id = {}, repeat_index = {}, error = {}".format(sample_id, repeat_index, e))
                continue

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=os.path.join(ROOT, "run_configs", "run_config.json"))
    cli_args = parser.parse_args()
    run_config = run_mcp_ipi.load_run_config(cli_args.config)
    asyncio.run(run_batch(run_config))

if __name__ == "__main__":
    main()
