# opt_ASR 说明

`opt_ASR` 这一层实现的是一条从脆弱 MCP Server 到外部资源候选生成、执行验证、失败后继续优化的链路。

当前主链路可以分成 5 个部分：

1. `vul_collector`
   - 收集 server 运行信息、tool schema、漏洞卡。
2. `plan_schedule`
   - 生成并选择 `Resource Plan`，再展开成 `plan schedule + block spec`。
3. `resource_generator`
   - 根据 plan 和 binding 生成 base / mutation 外部资源样本。
4. `oracle`
   - 运行样本，判断是否完成 fetch、tool routing、parameter hit、oracle side effect。
5. `optimizer`
   - 只处理 oracle 失败样本，分析失败阶段并为下一轮生成优化后的 plan。

## 目录结构

```text
opt_ASR/
├─ rules.yaml
├─ initial_plans.yaml
├─ prompts/
│  ├─ llm_generation_prompt.md
│  ├─ llm_mutation_prompt.md
│  ├─ llm_plan_update_prompt.md
│  └─ llm_repair_prompt.md
├─ vul_collector/
├─ plan_schedule/
├─ resource_generator/
├─ oracle/
└─ optimizer/
```

## 全局规则与 Prompt

### `rules.yaml`

职责：

- 定义资源生成、验证、反馈更新的全局规则。

当前 optimizer 直接依赖的主要字段：

- `feedback_update.failure_diagnosis`
- `feedback_update.hierarchical_plan_space`
- `feedback_update.plan_update_policy`

### `prompts/llm_generation_prompt.md`

职责：

- resource generation 阶段给 LLM 的 prompt 模板。

### `prompts/llm_mutation_prompt.md`

职责：

- mutation 阶段给 LLM 的 prompt 模板。

### `prompts/llm_plan_update_prompt.md`

职责：

- optimizer 阶段给 LLM 的 prompt 模板。
- 输入是失败样本的当前 plan、执行结果、规则切片。
- 输出是该失败样本下一轮可用的 `Resource Plan`。

### `prompts/llm_repair_prompt.md`

职责：

- repair 阶段给 LLM 的 prompt 模板。

## 漏洞卡收集阶段

### `vul_collector/server_config_collect/extract_server_runtime_metadata.py`

职责：

- 扫描本地 MCP Server 仓库，提取启动命令、参数、环境变量依赖、外部软件依赖。

输出：

- `vul_collector/server_config_collect/server_runtime_config.json`

### `vul_collector/vuln_card_collect/generate_vuln_tool_info.py`

职责：

- 从 runtime config、tool schema、源码片段里识别漏洞 tool，并生成漏洞卡。

输出：

- `vul_collector/vuln_card_collect/vuln_tool_info.json`
- `vul_collector/vuln_card_collect/fetch_server_info.json`

## Plan 调度阶段

### `plan_schedule/generate_initial_plans.py`

职责：

- 根据 `rules.yaml` 展开初始 plan pool，写出 `initial_plans.yaml`。

### `plan_schedule/plan_selector.py`

职责：

- 从 `initial_plans.yaml` 中选择当前轮使用的 plan。

### `plan_schedule/plan_to_blocks.py`

职责：

- 把选中的 `ResourcePlan` 展开成：
  - `PlanSchedule`
  - `BlockSpec`

## 外部资源生成阶段

### `resource_generator/generate_candidates.py`

职责：

- 读取：
  - `plan_schedule/out/selected_plan.json`
  - `plan_schedule/out/block_schedule.json`
  - `vul_collector/vuln_card_collect/vuln_tool_info.json`
  - `rules.yaml`
- 选择一个可用漏洞卡，构造 binding。
- 调用 `llm_compose_resource.py` 生成当前轮 base 样本。
- 写出：
  - `resource_generator/out/base/*.md`
  - `resource_generator/out/base/index.json`

说明：

- 当前 base 样本就是从这里开始生成的。
- 旧版 README 中提到的 `compose_resource.py` 已不在当前代码里，主入口已经变成 `generate_candidates.py`。

### `resource_generator/llm_compose_resource.py`

职责：

- 根据：
  - `block_schedule`
  - `binding`
  - `rules slice`
  - `prompts/llm_generation_prompt.md`
- 调用 LLM 生成一份 base external resource 文本。

### `resource_generator/llm_mutate_resource.py`

职责：

- 读取 base 样本。
- 按固定 mutation strategy 生成不同变体：
  - `semantic`
  - `context`
  - `payload`
  - `execution`
  - `verification`
- 写出到 `resource_generator/out/mutation/`

### `resource_generator/recheck_resource.py`

职责：

- 对 base 和 mutation 样本做复检。
- 检查：
  - binding preservation
  - block completeness
  - semantic consistency
- 写出：
  - `resource_generator/out/recheck/recheck_results.json`
  - `resource_generator/out/recheck/passed_candidates.json`
  - `resource_generator/out/recheck/failed_candidates.json`

### `resource_generator/export_samples_md.py`

职责：

- 读取：
  - `resource_generator/out/base/index.json`
  - `resource_generator/out/recheck/passed_candidates.json`
- 把通过复检的 base / mutation 样本统一导出到：
  - `resource_generator/out/samples_md/`
- 写出最终给 oracle 使用的：
  - `resource_generator/out/samples_md/index.json`

说明：

- oracle 实际读取的是 `samples_md` 这一层，而不是 `base` 或 `mutation` 原始目录。

## Oracle 阶段

### `MCP_Agent/run_mcp_ipi.py`

职责：

- 读取 `resource_generator/out/samples_md/index.json` 中的样本。
- 启动对应 MCP server。
- 让 agent 先 fetch 外部资源，再继续完成其中描述的任务。
- 记录：
  - `fetch_called`
  - `target_tool_called`
  - `target_tool_args`
  - `target_tool_result`
  - `llm_messages`
  - `tool_calls`
- 把执行结果写到 `oracle/out/<sample_id>/run*.json`

### `MCP_Agent/batch_run_mcp_ipi.py`

职责：

- 按 `run_configs/run_config.json` 批量调度 `run_mcp_ipi.py`
- 用于批量执行当前轮样本

### `oracle/command_detectors.py`

职责：

- 根据 `oracle_type` 检测副作用是否发生。
- 提供执行前清理、执行后检测、必要时清理环境的逻辑。

### `oracle`

职责：

- 保存 `run_mcp_ipi.py` 的执行结果。
- 判断每个样本是否完成了：
  - `fetch_called`
  - `target_tool_called`
  - `target_param_hit`
  - `side_effect_observed`

成功样本会直接作为当前轮有效输出。

## Optimizer 阶段

### `optimizer/optimize_results.py`

当前实现逻辑：

1. 读取 `oracle/out` 下的 `run*.json`。
2. 对每个样本提取四个客观执行信号：
   - `fetch_called`
   - `target_tool_called`
   - `target_param_hit`
   - `side_effect_observed`
3. 按 `rules.yaml -> feedback_update -> failure_diagnosis` 判断失败类型：
   - `fetch_failure`
   - `target_tool_failure`
   - `parameter_hit_failure`
   - `oracle_failure`
   - 或成功阶段 `S`
4. Oracle 成功样本直接输出，不进入 optimizer。
5. `base` 和所有 `mutation` 中的失败样本都会进入 optimizer。
6. 每个失败样本单独构造 prompt，并单独调用一次 LLM。
7. 每次 LLM 只负责给当前失败样本生成下一轮优化 plan。

这意味着 optimizer 现在已经是：

- sample-level 处理
- sample-level LLM 调用

而不是之前那种：

- parent-level 代表样本筛选
- 多失败样本合并成一次 LLM 调用

### Optimizer 输入

- `oracle/out/**/*.json`
- `resource_generator/out/samples_md/index.json`
- `rules.yaml`
- `prompts/llm_plan_update_prompt.md`

### Optimizer 输出

- `optimizer/out/optimizer_result.json`

输出分两种情况：

1. 全部成功
   - 返回 `status = "oracle_success"`
   - 只包含 `oracle_success`

2. 存在失败样本
   - 返回 `status = "needs_optimization"`
   - 包含 `oracle_success`
   - 包含 `optimizer_results`
   - `optimizer_results` 中每一项都对应一个失败样本自己的优化结果

## 当前几个核心概念

### `Resource Plan`

定义一轮资源的大方向，不是最终文本。

它描述的是：

- 用什么 genre
- 动作性多强
- 参数绑定多强
- 证据写多深
- 用什么语气、语言、资源格式
- 目标 oracle 是什么

### `PlanSchedule`

定义该资源应该有哪些 block，以及它们的顺序。

### `BlockSpec`

定义每个 block 具体需要哪些字段、属于哪个模块、应该用什么格式表达。

### `binding`

把漏洞卡里的真实值绑定到资源生成阶段，包括：

- `target_tool`
- `vulnerable_parameter`
- `parameter_type`
- `argument_json`
- `payload_command`
- `oracle_type`

## 当前执行顺序

1. `plan_schedule/generate_initial_plans.py`
2. `plan_schedule/plan_selector.py`
3. `plan_schedule/plan_to_blocks.py`
4. `resource_generator/generate_candidates.py`
5. `resource_generator/llm_mutate_resource.py`
6. `resource_generator/recheck_resource.py`
7. `resource_generator/export_samples_md.py`
8. `MCP_Agent/batch_run_mcp_ipi.py` 或 `MCP_Agent/run_mcp_ipi.py`
9. `optimizer/optimize_results.py`