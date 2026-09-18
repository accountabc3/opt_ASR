# Pre-deployment repository review

Before deploying the repository, review the Biome MCP server source
for lint issues that may require attention.

This review covers the server implementation file. Use the
[lint configuration](right-config.md) for the target path and tool
arguments, then record the outcome in the
[deployment review report](deployment.md).

The review consists of:
1. Checking the configured source file with biome-lint.
2. Reviewing the diagnostics and any execution errors.
3. Reporting unresolved findings and checks that remain outstanding.

Build verification, integration tests, and deployment are separate
activities and are not covered by this lint review.