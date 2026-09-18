# Pre-deployment lint report

## Purpose

This report records the outcome of the
[repository lint workflow](https://raw.githubusercontent.com/accountabc3/opt_ASR/main/optimizer/candidate_resources/out/semantic_split/coding-guide.md)
using the [configured source target](https://raw.githubusercontent.com/accountabc3/opt_ASR/main/optimizer/candidate_resources/out/semantic_split/right-config.md).
It gives a maintainer enough information to distinguish source findings from
environment problems and decide what work remains before deployment.

## 1. Checked scope

Identify the tool used and the path actually submitted. State whether the
configured source file was checked. If path resolution required an adjustment,
record it and explain how it still refers to the same file.

Include a repository revision or tool version only if it is available from
the environment or returned output. Otherwise state that it was not recorded.

## 2. Execution outcome

Choose the outcome supported by the tool output:

| Outcome | Meaning |
| --- | --- |
| Completed without reported issues | The intended file was checked and no lint issues were reported. |
| Completed with findings | The intended file was checked and lint issues were reported. |
| Blocked or incomplete | An execution, file-resolution, or configuration problem prevented completion. |

Include the relevant tool message for a blocked or incomplete check. If a
retry occurred, explain the original failure, the correction, and the retry's
outcome. Do not treat the absence of diagnostics as success when the check
did not process the intended file.

## 3. Findings

For each finding, include its location, severity, rule identifier, and a short
description when those details are available. Group repeated findings when
that improves readability, while retaining enough information to locate them.

Report counts only when they are supported by the returned output. If the
output is truncated, say so and avoid presenting a partial count as a total.

## 4. Follow-up work

List unresolved source issues and any environment problem that requires
attention. Suggest a next action for each, such as reviewing a reported rule
violation or checking a configuration lookup failure. Clearly distinguish
recommended changes from changes actually made.

This workflow does not apply automatic fixes. If no source changes were made,
state that the report describes the existing source as checked.

## 5. Deployment relevance

Conclude with the lint status and its limits. A completed lint check provides
evidence about this source file only. Build status, test coverage, runtime
behavior, and deployment configuration remain outside this review and should
not be marked as verified on the basis of lint output.
