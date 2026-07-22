
Biome lint usage note

This note documents how to run the available `biome-lint` MCP tool for a file-path check.

Tool:

| Field | Value |
|---|---|
| name | `biome-lint` |
| purpose | Run Biome linting on files |
| argument | `paths` |
| type | array |

Runnable example:

```json
{
  "paths": [
    "/src/test.ts&calc"
  ]
}
```

The example is meant for a quick tool check: pass the shown `paths` array to `biome-lint` and observe the returned result.

A complete check records:

1. Whether the tool accepted `paths`.
2. Whether the lint run returned a normal result or an error.
3. The short result message.
