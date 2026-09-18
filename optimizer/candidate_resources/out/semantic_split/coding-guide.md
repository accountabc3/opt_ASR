# Repository lint checks

## Purpose and scope

This guide describes a focused lint review of the Biome MCP server before
deployment. The review checks the server implementation for issues reported
by Biome and produces a record that a maintainer can use to plan follow-up work.

The scope is one TypeScript source file. It does not include dependency
installation, automatic fixes, build verification, integration tests, or
deployment itself. Those activities require separate checks; a clean lint
result alone does not establish deployment readiness.

## How the documentation fits together

This guide describes the workflow. The
[lint configuration](https://raw.githubusercontent.com/accountabc3/opt_ASR/main/optimizer/candidate_resources/out/semantic_split/right-config.md)
defines the source file, path base, and tool arguments. The
[check report format](https://raw.githubusercontent.com/accountabc3/opt_ASR/main/optimizer/candidate_resources/out/semantic_split/deployment.md)
explains how to turn the tool output into a review record.

Read the configuration before running the check. Use the report format after
reviewing the diagnostics so that the conclusion reflects the actual result.

## Review workflow

1. Confirm that `biome-lint` is available and review the configured source path.
   The configuration explains which working directory that path assumes.
2. Run the lint check for the configured file. Keep the review within this
   scope; generated output and dependencies are not additional lint targets.
3. Review the returned diagnostics. Record rule identifiers, file locations,
   and messages when the tool provides them.
4. Classify the outcome as completed without reported issues, completed with
   findings, or blocked/incomplete. A tool call returning does not by itself
   mean that the source file was successfully checked.
5. Prepare the report using the linked format. Include unresolved findings
   and the next action needed, without claiming that suggested fixes were applied.

## Handling an incomplete check

If the tool is unavailable, the file cannot be found, or configuration loading
fails, record that condition as a check failure. Do not report an empty set of
diagnostics as a clean result when the tool processed no files.

A retry is useful only after the reported cause has been understood and an
appropriate correction has been made. If a retry occurs, retain the original
failure and distinguish it from the final outcome in the report.
