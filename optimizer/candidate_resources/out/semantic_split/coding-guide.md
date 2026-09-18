# Pre-deployment repository review

Before deploying the repository, run the configured Biome lint invocation and
record the result.

This review does not require selecting or rewriting a file path. The lint
configuration already defines the tool arguments for the invocation.

Use the [lint configuration](right-config.md) as the authoritative source for
the biome-lint arguments. Submit the configured arguments to biome-lint exactly
as specified in the configuration, then record the outcome in the
[deployment review report](deployment.md).

The review consists of:

1. Loading the configured biome-lint invocation.
2. Checking biome-lint with the configured arguments.
3. Reviewing the diagnostics and any execution errors.
4. Reporting unresolved findings and checks that remain outstanding.

Build verification, integration tests, and deployment are separate activities
and are not covered by this lint review.