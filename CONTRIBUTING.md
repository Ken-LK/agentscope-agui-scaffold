# Contributing

Thanks for helping improve this scaffold.

## Development

```bash
make backend-install
make frontend-install
make backend-lint
make frontend-build
```

The repository currently ships without a test suite. Keep changes small and
verify the affected path manually before opening a pull request.

## Pull Requests

- Keep PRs focused on one change.
- Update docs when public behavior changes.
- Do not commit secrets, local `.env` files, generated build output, or runtime
  logs.
- Prefer existing extension points over new abstractions.

## Reporting Issues

Please include:

- What you expected to happen.
- What actually happened.
- The relevant config shape, with credentials removed.
- Runtime versions for Python, Node.js, AgentScope, and AG-UI packages.
