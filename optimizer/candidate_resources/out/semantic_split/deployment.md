# Deployment review report

Summarize the lint review with:

- The biome-lint arguments submitted.
- Whether the check completed.
- Reported errors and warnings.
- Unresolved findings and recommended follow-up.

If the check failed to run, describe the failure instead of reporting the
review as passing.

When reporting the checked scope, record the arguments that were submitted to
biome-lint. Do not replace the configured arguments with an inferred or
normalized path in the report.

Conclude with what this review establishes and what remains unchecked. A clean
lint result covers this configured lint invocation only; it does not verify the
build, integration tests, or deployment configuration.