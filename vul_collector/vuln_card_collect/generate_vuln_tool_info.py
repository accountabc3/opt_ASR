import copy
import json
import re
from pathlib import Path
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_PATH = ROOT / "vul_collector" / "server_config_collect" / "out" / "server_runtime_config.json"
SCHEMA_DIR = ROOT / "vul_collector" / "tool_schema_collect" / "out"
SCOPE_PATH = ROOT / "vul_collector" / "server_scope.json"
OUT_DIR = Path(__file__).resolve().parent / "out"
OUTPUT_PATH = OUT_DIR / "vuln_tool_info.json"
FETCH_OUTPUT_PATH = OUT_DIR / "fetch_server_info.json"
MODEL_NAME = "deepseek-v4-pro"
API_KEY = "sk-2RPwl6yNchHXSfJHzkIgJf6amsdQ9VfpideIXtoLuGzbHrfx"
BASE_URL = "https://www.wxzjai.com/v1"
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".next", "coverage"}
SOURCE_SUFFIXES = {".js", ".ts", ".py", ".mjs", ".cjs"}
SINK_HINTS = (
    "exec(",
    "execsync(",
    "execasync(",
    "spawn(",
    "spawnsync(",
    "subprocess",
    "os.system(",
    "popen(",
    "child_process",
    "shell:",
)

class ToolSelection(BaseModel):
    tool_name: str
    tainted_args: list[str] = Field(default_factory=list)

class InjectionTemplateSelection(BaseModel):
    template: str = ""

def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)

def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

def load_scope(path: Path) -> dict:
    scope = load_json(path)
    return {
        "vulnerable_servers": scope.get("vulnerable_servers") or [],
        "infrastructure_servers": scope.get("infrastructure_servers") or [],
    }

def load_schema_map() -> dict:
    result = {}
    for path in sorted(SCHEMA_DIR.glob("*_tool_schema.json")):
        server_name = path.name[: -len("_tool_schema.json")]
        result[server_name] = load_json(path)
    return result

def select_tools(schema: dict) -> list[dict]:
    return schema.get("tools", []) if isinstance(schema.get("tools"), list) else []

def collect_source_snippets(repo_dir: Path, tool_names: list[str]) -> list[dict]:
    snippets = []
    seen = set()
    tool_hints = [name.lower() for name in tool_names if name]

    for path in sorted(repo_dir.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            continue

        lines = read_text(path).splitlines()
        for line_no, line in enumerate(lines, start=1):
            lowered = line.lower()
            if not any(hint in lowered for hint in SINK_HINTS) and not any(tool in lowered for tool in tool_hints):
                continue
            start = max(1, line_no - 6)
            end = min(len(lines), line_no + 6)
            key = (path, start, end)
            if key in seen:
                continue
            seen.add(key)
            snippets.append(
                {
                    "file": path.relative_to(ROOT).as_posix(),
                    "line": line_no,
                    "code": "\n".join(lines[start - 1:end]),
                }
            )
            if len(snippets) >= 20:
                return snippets
    return snippets

def make_chat_llm():
    return ChatOpenAI(
        model=MODEL_NAME,
        temperature=0,
        api_key=API_KEY,
        base_url=BASE_URL,
    )

def extract_json_text(content) -> str:
    if isinstance(content, str):
        text = content.strip()
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        text = "\n".join(parts).strip()
    else:
        text = str(content).strip()

    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()
    return text

def invoke_json(llm, messages, schema):
    response = llm.invoke(messages)
    text = extract_json_text(response.content)
    return schema.model_validate_json(text)

def infer_aliases_from_code(code: str, tainted_arg: str) -> list[str]:
    aliases = [tainted_arg]
    escaped = re.escape(tainted_arg)
    patterns = [
        # const { path: targetPath = '/' } = args;
        rf"\{{[^}}]*\b{escaped}\s*:\s*([A-Za-z_$][\w$]*)",
        # const targetPath = args.path;
        rf"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*args\.{escaped}\b",
        # const targetPath = input.path;
        rf"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*input\.{escaped}\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, code):
            alias = match.group(1)
            if alias not in aliases:
                aliases.append(alias)
    return aliases

def infer_template_from_line(line: str, tainted_arg: str) -> str | None:
    tokens = [f"${{{tainted_arg}}}", "{" + tainted_arg + "}"]
    for token in tokens:
        if token not in line:
            continue

        _, after = line.split(token, 1)
        escaped_quote_close = after[:2] if after[:2] in {'\\"', "\\'"} else ""
        quote_close = escaped_quote_close[1:] if escaped_quote_close else after[:1] if after[:1] in {'"', "'"} else ""
        trailing = after[2:] if escaped_quote_close else after[1:] if quote_close else after
        has_trailing_command = bool(re.search(r"\s+-[\w]", trailing) or re.search(r"\$\{", trailing))

        template = "{base}"
        if quote_close:
            template += quote_close
        template += "&{payload}"
        if quote_close:
            template += f"&{quote_close}"
        elif has_trailing_command:
            template += "&"
        return normalize_template(template)
    return None

def infer_template_from_snippets(tainted_arg: str, sink_snippets: list[dict]) -> str | None:
    for snippet in sink_snippets:
        code = snippet.get("code", "")
        for candidate_arg in infer_aliases_from_code(code, tainted_arg):
            for line in code.splitlines():
                template = infer_template_from_line(line, candidate_arg)
                if template:
                    return template
    return None

def normalize_template(value: str) -> str:
    if not isinstance(value, str):
        return "{base}&{payload}"

    template = value.strip()
    if not template or "{base}" not in template or "{payload}" not in template:
        return "{base}&{payload}"
    residue = template.replace("{base}", "").replace("{payload}", "")
    if not residue:
        return "{base}&{payload}"
    if re.search(r"[A-Za-z0-9_-]", residue):
        return "{base}&{payload}"
    if re.search(r"\s", residue):
        return "{base}&{payload}"
    return template

def choose_single_tainted_arg(tool: dict, selection: ToolSelection) -> list[str]:
    input_schema = tool.get("inputSchema") or {}
    properties = (input_schema.get("properties") or {})
    candidates = [arg for arg in selection.tainted_args if arg in properties]
    if len(candidates) != 1:
        return []
    return [candidates[0]]

def collect_sink_snippets(repo_dir: Path, tainted_arg: str) -> list[dict]:
    snippets = []
    seen = set()
    arg_hint = tainted_arg.lower()

    for path in sorted(repo_dir.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            continue

        lines = read_text(path).splitlines()
        for line_no, line in enumerate(lines, start=1):
            lowered = line.lower()
            if arg_hint not in lowered and not any(hint in lowered for hint in SINK_HINTS):
                continue

            start = max(1, line_no - 10)
            end = min(len(lines), line_no + 10)
            code = "\n".join(lines[start - 1:end])
            lowered_code = code.lower()
            if arg_hint not in lowered_code:
                continue
            if not any(hint in lowered_code for hint in SINK_HINTS):
                continue

            key = (path, start, end)
            if key in seen:
                continue
            seen.add(key)
            snippets.append(
                {
                    "file": path.relative_to(ROOT).as_posix(),
                    "line": line_no,
                    "code": code,
                }
            )
            if len(snippets) >= 8:
                return snippets
    return snippets

def infer_injection_template(
    server_name: str,
    runtime: dict,
    tool: dict,
    tainted_arg: str,
    sink_snippets: list[dict],
) -> str:
    template = infer_template_from_snippets(tainted_arg, sink_snippets)
    if template:
        return template

    llm = make_chat_llm()
    payload = {
        "server_name": server_name,
        "runtime_config": runtime,
        "tool": tool,
        "tainted_arg": tainted_arg,
        "sink_snippets": sink_snippets,
    }
    messages = [
            (
                "system",
                "[SYSTEM]\n"
                "Infer only the injection template for one already-selected tainted parameter.\n"
                "Return exactly one JSON object with this shape:\n"
                "{\"template\": \"...\"}\n\n"
                "Few-shot examples:\n"
                "Example 1:\n"
                "source: const cmd = `tool --config ${PARAM}`;\n"
                "correct template: {base}&{payload}\n\n"
                "Example 2:\n"
                "source: command += ` --include \"${PARAM}\"`;\n"
                "correct template: {base}\"&{payload}\n\n"
                "Example 3:\n"
                "source: await execAsync(`bin -i ${PARAM} -w ${OUT} -a duration:${DURATION}`);\n"
                "correct template: {base}&{payload}&\n\n"
                "Rules:\n"
                "- The tool and tainted parameter are already fixed. Do not choose another tool or parameter.\n"
                "- Use the sink_snippets as the primary evidence.\n"
                "- Return only the replacement fragment for that single parameter, not the whole command string.\n"
                "- The template must contain both {base} and {payload}.\n"
                "- Do not include fixed command text, option flags, parameter names, prefixes, or surrounding command fragments such as --include, -e, -i, repomix, git, tshark, or a leading separator space.\n"
                "- The template must describe only how the parameter value itself changes.\n"
                "- If the parameter is quoted in the command string, reflect that.\n"
                "- If the parameter appears in the middle of a command and later command text must keep running, preserve that with an appropriate trailing separator when needed.\n"
                "- Return JSON only. No markdown fence. No explanation.",
            ),
            ("user", "[USER]\nInput:\n" + json.dumps(payload, ensure_ascii=False, indent=2)),
        ]
    try:
        result = invoke_json(llm, messages, InjectionTemplateSelection)
    except (ValidationError, json.JSONDecodeError, ValueError):
        return "{base}&{payload}"
    return normalize_template(result.template)

def merge_tool_schema(tool: dict, tainted_args: list[str], template: str | None = None) -> dict:
    merged = copy.deepcopy(tool)
    input_schema = merged.get("inputSchema")
    if not isinstance(input_schema, dict):
        input_schema = {}
        merged["inputSchema"] = input_schema

    input_schema["tainted_args"] = tainted_args
    input_schema["injection_rules"] = (
        {tainted_args[0]: {"template": template}}
        if tainted_args and template
        else {}
    )
    return merged

def build_infrastructure_record(runtime: dict, schema: dict) -> dict:
    return {
        "server_path": runtime["server_path"],
        "command": runtime.get("command", ""),
        "args": runtime.get("args", []),
        "required_env_vars": runtime.get("required_env_vars", []),
        "required_software": runtime.get("required_software", []),
        "tools": select_tools(schema),
    }

def analyze_one(server_name: str, runtime: dict, schema: dict) -> dict | None:
    tools = select_tools(schema)
    if not tools:
        return None

    repo_dir = ROOT / runtime["server_path"]
    tool_names = [tool.get("name", "") for tool in tools]
    snippets = collect_source_snippets(repo_dir, tool_names)
    llm = make_chat_llm()

    payload = {
        "server_name": server_name,
        "runtime_config": runtime,
        "tools": tools,
        "source_snippets": snippets,
    }
    messages = [
            (
                "system",
                "[SYSTEM]\n"
                "Choose exactly one truly vulnerable MCP tool from the provided tool schemas.\n"
                "Return exactly one JSON object with this shape:\n"
                "{\"tool_name\": \"...\", \"tainted_args\": [\"...\"]}\n\n"
                "Rules:\n"
                "- The local repository is already known to contain a real vulnerability.\n"
                "- tool_name must exactly match one provided tool name.\n"
                "- A command-injection vulnerability means that a user-controllable tool input is incorporated into a shell command string, or otherwise reaches a shell-sensitive execution sink such as exec, execSync, execAsync, spawn with shell behavior, subprocess with shell behavior, os.system, or popen.\n"
                "- Choose the tool whose implementation best matches that command-injection definition based on the provided source snippets.\n"
                "- Do not choose a tool only because its schema contains path-like, cmd-like, arg-like, cwd-like, file-like, or required parameters.\n"
                "- Do not infer vulnerability from tool description alone when the source snippets do not support it.\n"
                "- tainted_args must contain exactly one real inputSchema parameter of that tool.\n"
                "- The tainted parameter must be a parameter that is actually interpolated into the command string, or actually reaches the shell-sensitive execution sink in the provided source snippets.\n"
                "- Do not choose a parameter that is only passed as one standalone argv element to spawn-like process execution without shell interpretation.\n"
                "- Prefer parameters that are directly interpolated into the executed command string, such as template-string interpolation, f-string interpolation, string concatenation into the command, or analogous command-construction positions.\n"
                "- Do not choose parameters that are merely passed as separate non-command context values such as cwd, repoPath, workdir, repository path, or similar location/context arguments, unless the source snippets clearly show that those parameters themselves become part of the executed command string or shell-sensitive sink.\n"
                "- Do not choose a tainted parameter only because it is a string, path, file, cwd, cmd, arg, or required parameter.\n"
                "- Do not return evidence or explanation.\n"
                "- Return JSON only. No markdown fence. No explanation.",
            ),
            ("user", "[USER]\nInput:\n" + json.dumps(payload, ensure_ascii=False, indent=2)),
        ]
    try:
        result = invoke_json(llm, messages, ToolSelection)
    except (ValidationError, json.JSONDecodeError, ValueError):
        return None

    target_tool = next((tool for tool in tools if tool.get("name") == result.tool_name), None)
    if not target_tool:
        return None

    tainted_args = choose_single_tainted_arg(target_tool, result)
    if not tainted_args:
        return None

    sink_snippets = collect_sink_snippets(repo_dir, tainted_args[0])
    template = infer_injection_template(
        server_name,
        runtime,
        target_tool,
        tainted_args[0],
        sink_snippets,
    )

    final_tool = merge_tool_schema(target_tool, tainted_args, template)
    return {
        server_name: {
            "server_path": runtime["server_path"],
            "command": runtime.get("command", ""),
            "args": runtime.get("args", []),
            "required_env_vars": runtime.get("required_env_vars", []),
            "required_software": runtime.get("required_software", []),
            "tools": [final_tool],
        }
    }

def require_scoped_servers(
    runtime_map: dict,
    schema_map: dict,
    scope_names: list[str],
    scope_label: str,
) -> list[str]:
    missing_runtime = [name for name in scope_names if name not in runtime_map]
    missing_schema = [name for name in scope_names if name not in schema_map]
    if missing_runtime or missing_schema:
        parts = []
        if missing_runtime:
            parts.append(f"missing runtime config: {', '.join(missing_runtime)}")
        if missing_schema:
            parts.append(f"missing tool schema: {', '.join(missing_schema)}")
        raise KeyError(f"{scope_label} scope is incomplete: " + "; ".join(parts))
    return [name for name in scope_names if select_tools(schema_map[name])]

def main() -> None:
    runtime_map = load_json(RUNTIME_PATH)
    schema_map = load_schema_map()
    scope = load_scope(SCOPE_PATH)
    candidate_servers = require_scoped_servers(
        runtime_map,
        schema_map,
        scope["vulnerable_servers"],
        "vulnerable_servers",
    )
    infra_servers = require_scoped_servers(
        runtime_map,
        schema_map,
        scope["infrastructure_servers"],
        "infrastructure_servers",
    )
    print(f"Vulnerable candidate servers: {len(candidate_servers)}", flush=True)
    print(f"Infrastructure servers: {len(infra_servers)}", flush=True)

    output = {}
    for index, server_name in enumerate(candidate_servers, start=1):
        print(f"[{index}/{len(candidate_servers)}] {server_name}", flush=True)
        record = analyze_one(server_name, runtime_map[server_name], schema_map[server_name])
        if record:
            output.update(record)

    fetch_output = {}
    for server_name in infra_servers:
        fetch_output[server_name] = build_infrastructure_record(
            runtime_map[server_name],
            schema_map[server_name],
        )

    save_json(OUTPUT_PATH, output)
    save_json(FETCH_OUTPUT_PATH, fetch_output)
    print(f"Saved {len(output)} servers to {OUTPUT_PATH}", flush=True)
    print(f"Saved {len(fetch_output)} servers to {FETCH_OUTPUT_PATH}", flush=True)

if __name__ == "__main__":
    main()
