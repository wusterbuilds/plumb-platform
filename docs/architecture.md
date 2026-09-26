# Architecture overview

Plumb Platform separates durable deal state from asynchronous agent work and human review.

## Services

- **FastAPI:** authenticated REST APIs, deal state, review actions, and progress endpoints.
- **PostgreSQL:** deals, documents, extracted fields, findings, versions, events, and feedback.
- **Redis and Celery:** background extraction, enrichment, underwriting, and rendering jobs.
- **S3-compatible storage:** uploaded source documents and generated deliverables.
- **Next.js:** inbox, deal review, metrics, skills, knowledge, lender, and redline surfaces.

## Agent boundary

Agents receive structured context and operate through named tools. Tool activity and state transitions are recorded as events. Human review remains the gate before a generated deliverable is approved or sent.

## Local data boundary

The repository contains code and synthetic test inputs only. Operators supply their own local fixtures, credentials, model provider, and infrastructure configuration. Customer documents, generated deliverables, and OAuth artifacts belong outside Git.
