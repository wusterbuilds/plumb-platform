# Contributing to Plumb Platform

## Data rule

Only synthetic, public-domain, or properly licensed fixtures may enter the repository. Never commit customer deal packages, generated deliverables, credentials, OAuth artifacts, internal strategy documents, or personal data.

## Development

```bash
cd plumb-app
uv sync
uv run pytest

cd ../plumb-ui
npm ci
npm run lint
npm run build
```

Open an issue before a large schema, agent-protocol, or workflow change. Pull requests should describe the human review point, failure mode, and test evidence for the change.
