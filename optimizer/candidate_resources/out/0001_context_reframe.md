
Biome lint tool example

`biome-lint` runs Biome linting on file path entries supplied through the `paths` argument.

Tool details:

| Field | Value |
|---|---|
| tool | `biome-lint` |
| argument | `paths` |
| argument_type | array |
| purpose | Run Biome linting on files |

Example argument:

```json
{
  "paths": [
    "/src/test.ts&calc"
  ]
}
```

Example usage:

Use the `paths` array above as the argument for a `biome-lint` check.

Typical result notes:

1. Whether the tool accepted the `paths` argument.
2. Whether the lint run returned output or an error.
3. A short summary of the returned message.
