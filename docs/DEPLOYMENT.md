# Deployment

SafetyNet ships as a small FastAPI gateway you put **in front of** your agent container. Clients
talk to SafetyNet; SafetyNet guards and forwards to the upstream agent.

## Quick start (stub upstream)

```bash
docker compose up --build      # SafetyNet on :8000, guarding a built-in echo agent
curl localhost:8000/health
```

With `UPSTREAM_TYPE=stub` (the default) no external agent is needed — ideal for testing the
security pipeline (injection, IP, harmful content) on its own.

## Configuration (environment variables)

| Var | Default | Meaning |
|---|---|---|
| `POLICY_PATH` | bundled `policies/default.yaml` | Policy YAML to enforce |
| `UPSTREAM_TYPE` | `stub` | `stub` \| `nemo` \| `openai` \| `langgraph` \| `dify` \| `crewai` |
| `UPSTREAM_URL` | — | Base URL of the agent container |
| `UPSTREAM_MODEL` | `gpt-3.5-turbo` | Model name for OpenAI-compatible upstreams |
| `UPSTREAM_API_KEY` | — | Bearer token for the upstream, if required |

Mount your own policy:

```yaml
# docker-compose override
services:
  safetynet:
    volumes:
      - ./my-policy.yaml:/app/policies/default.yaml:ro
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + active `policy_hash` + upstream type |
| POST | `/guard` | Check-only: evaluate `{prompt}`, return the decision (no forwarding) |
| POST | `/v1/chat/completions` | OpenAI-compatible proxy: guard → forward → guard |

`/v1/chat/completions` returns a standard chat-completion object. When SafetyNet blocks, the
choice's `finish_reason` is `content_filter` and a `safetynet` object reports
`{allowed, blocked_stage, halt_reason, run_id, audit_path}`.

## Observability

- **Audit** — every decision is appended to `output/audit-<run_id>.jsonl` (mount `/app/output`
  to persist). Records carry `policy_hash` + sha256 content hashes for reconstructable review.
- **Tracing** — set a `LangfuseTracer` on the `GuardedAgent` (or extend the server) to stream
  spans to Langfuse (`pip install '.[langfuse]'`).

## Scaling notes

- The gateway is stateless per request (breaker state is per `run_id`), so run multiple replicas
  behind a load balancer.
- Real scanner backends (transformers/embeddings) load models at process start — bake the
  `[guard]`/`[embeddings]` extras into the image and pre-warm, or keep them in a sidecar.
