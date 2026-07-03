import json
from pathlib import Path
import tomllib
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
SERVERS_DIR = ROOT / "servers"
OUT_DIR = Path(__file__).resolve().parent / "out"
OUTPUT_PATH = OUT_DIR / "server_runtime_config.json"
MODEL_NAME = "gpt-5.4-mini"
API_KEY = "sk-2RPwl6yNchHXSfJHzkIgJf6amsdQ9VfpideIXtoLuGzbHrfx"
BASE_URL = "https://www.wxzjai.com/v1"
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".next", "coverage"}
TEXT_SUFFIXES = {".md", ".toml", ".json", ".yaml", ".yml", ".js", ".ts", ".py"}
SERVER_MARKERS = (
    "StdioServerTransport",
    "McpServer",
    "server.connect(",
    "setRequestHandler",
    "ListToolsRequestSchema",
    "CallToolRequestSchema",
    "server.tool(",
    "FastMCP(",
    "@mcp.tool",
    "@server.tool"
)

class RuntimeConfig(BaseModel):
    server_path: str
    command: str
    args: list[str] = []
    required_env_vars: list[str] = []
    required_software: list[str] = []

def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")

def load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)

def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()

def looks_like_server_entry(path: Path) -> bool:
    if not path.exists() or path.suffix.lower() not in {".js", ".ts", ".py"}:
        return False
    text = read_text(path)
    for marker in SERVER_MARKERS:
        if marker in text:
            return True
    return False

def build_local_command(executable: str, script_path: Path, repo_dir: Path) -> str:
    relative_path = script_path.relative_to(repo_dir)
    relative_path_text = relative_path.as_posix()
    command = executable + " " + relative_path_text
    return command

def iter_context_files(repo_dir: Path):
    for path in repo_dir.rglob("*"):
        if not path.is_file():
            continue
        skip_file = False
        for part in path.parts:
            if part in SKIP_DIRS:
                skip_file = True
                break
        if skip_file:
            continue
        if path.name in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}:
            continue
        if path.name.startswith("README"):
            yield path
            continue
        suffix = path.suffix.lower()
        if suffix in TEXT_SUFFIXES:
            yield path

def collect_start_candidates(repo_dir: Path) -> list[dict]:
    candidates = []
    seen_values = set()

    def add_candidate(entry_type: str, value: str, file_path: Path, text: str) -> None:
        key = (
            entry_type,
            value,
            rel(file_path),
        )
        if key not in seen_values:
            seen_values.add(key)
            candidates.append(
                {
                    "entry_type": entry_type,
                    "value": value,
                    "file": rel(file_path),
                    "text": text,
                }
            )
            
    package_path = repo_dir / "package.json"
    if package_path.exists():
        data = json.loads(read_text(package_path))
        scripts = data.get("scripts") or {}
        for key in ["start", "dev"]:
            value = scripts.get(key)
            if isinstance(value, str):
                add_candidate(
                    "launch",
                    value,
                    package_path,
                    f"scripts.{key} = {value}",
                )
        bin_value = data.get("bin")
        if isinstance(bin_value, str):
            add_candidate("entry", bin_value, package_path, f"bin = {bin_value}")
        elif isinstance(bin_value, dict):
            for _, value in bin_value.items():
                if isinstance(value, str):
                    add_candidate("entry", value, package_path, f"bin = {value}")
        main_value = data.get("main")
        if isinstance(main_value, str):
            add_candidate("entry", main_value, package_path, f"main = {main_value}")

    pyproject_path = repo_dir / "pyproject.toml"
    if pyproject_path.exists():
        data = load_toml(pyproject_path)
        scripts = data.get("project", {}).get("scripts", {})
        for name, value in scripts.items():
            if isinstance(value, str):
                add_candidate(
                    "python_script",
                    f"{name} = {value}",
                    pyproject_path,
                    f"project.scripts.{name} = {value}",
                )

    for path in sorted(repo_dir.rglob("*")):
        if not path.is_file():
            continue
        skip_file = False
        for part in path.parts:
            if part in SKIP_DIRS:
                skip_file = True
                break
        if skip_file:
            continue
        if not looks_like_server_entry(path):
            continue
        if path.suffix == ".js":
            command = build_local_command("node", path, repo_dir)
            add_candidate("launch", command, path, f"compiled server entry = {path.relative_to(repo_dir).as_posix()}")
        elif path.suffix == ".ts":
            compiled_dist = repo_dir / "dist" / f"{path.stem}.js"
            compiled_build = repo_dir / "build" / f"{path.stem}.js"
            if compiled_dist.exists():
                command = build_local_command("node", compiled_dist, repo_dir)
                add_candidate("launch", command, compiled_dist, f"compiled server entry = {compiled_dist.relative_to(repo_dir).as_posix()}")
            elif compiled_build.exists():
                command = build_local_command("node", compiled_build, repo_dir)
                add_candidate("launch", command, compiled_build, f"compiled server entry = {compiled_build.relative_to(repo_dir).as_posix()}")
            else:
                command = build_local_command("tsx", path, repo_dir)
                add_candidate("launch", command, path, f"source server entry = {path.relative_to(repo_dir).as_posix()}")
        elif path.suffix == ".py":
            command = build_local_command("python", path, repo_dir)
            add_candidate("launch", command, path, f"python server entry = {path.relative_to(repo_dir).as_posix()}")
    return candidates

def collect_context(repo_dir: Path) -> dict:
    context = {}
    for file_path in iter_context_files(repo_dir):
        if file_path.name.startswith("README"):
            context[rel(file_path)] = read_text(file_path)[:12000]
        elif file_path.name == "package.json":
            context[rel(file_path)] = read_text(file_path)
        elif file_path.name == "pyproject.toml":
            context[rel(file_path)] = read_text(file_path)
    return context

def build_system_prompt() -> str:
    return (
        "You are a senior software security research assistant specializing in MCP server runtime analysis.\n\n"
        "Your task is to infer the real startup command for running one checked-out local MCP server repository, "
        "and identify its required environment variables and required external software.\n\n"
        "Rules:\n"
        "1. Choose exactly one startup command.\n"
        "2. Prefer commands that actually run the checked-out local server source tree.\n"
        "3. Do not choose install, test, smoke, benchmark, or client/demo commands.\n"
        "4. Prefer stdio server startup commands when multiple commands exist.\n"
        "5. Reject startup commands that reference a local script path which does not actually exist in the checked-out repository.\n"
        "6. If both compiled artifacts and source-level dev commands exist, prefer compiled local startup commands such as node dist/*.js or node build/*.js over tsx or ts-node.\n"
        "7. If README examples use placeholder paths such as /path/to/the/cloned/repo, interpret them using the actual local repository path provided in the input.\n"
        "8. If both packaged CLI and source-level commands exist, prefer the one more suitable for running the local checked-out source tree.\n"
        "9. required_env_vars should include only environment variables genuinely required for startup or main functionality.\n"
        "10. required_software should include only software or CLI tools that must already be installed outside the repository, "
        "such as node, python, uv, docker, git, nmap, biome, or tshark.\n"
        "11. Do not include optional debug variables.\n"
        "12. In args, use repository-relative paths under server_path whenever possible, such as dist/index.js or build/index.js.\n"
        "13. Do not output absolute filesystem paths in args.\n"
        "14. Return only structured JSON with fields: server_path, command, args, required_env_vars, required_software.\n"
    )

def build_user_prompt(repo_dir: Path, start_candidates: list[dict], context: dict) -> str:
    payload = {
        "server_path": rel(repo_dir),
        "local_repo_path": str(repo_dir.resolve()),
        "start_candidates": start_candidates,
        "context_files": context,
    }
    return (
        "Analyze the following MCP server repository and return the final normalized runtime configuration.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

def make_llm():
    llm = ChatOpenAI(
        model=MODEL_NAME,
        temperature=0,
        api_key=API_KEY,
        base_url=BASE_URL,
    )
    return llm.with_structured_output(RuntimeConfig)

def analyze_repo(llm, repo_dir: Path) -> dict:
    start_candidates = collect_start_candidates(repo_dir)
    context = collect_context(repo_dir)
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(repo_dir, start_candidates, context)
    result = llm.invoke(
        [
            ("system", system_prompt),
            ("user", user_prompt),
        ]
    )
    return result.model_dump()

def main() -> None:
    llm = make_llm()
    output = {}
    repo_dirs = []
    for repo_dir in sorted(SERVERS_DIR.iterdir()):
        if repo_dir.is_dir():
            repo_dirs.append(repo_dir)
    for index, repo_dir in enumerate(repo_dirs, start=1):
        print(f"[{index}/{len(repo_dirs)}] {repo_dir.name}")
        output[repo_dir.name] = analyze_repo(llm, repo_dir)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Saved {len(output)} servers to {OUTPUT_PATH.name}")

if __name__ == "__main__":
    main()
