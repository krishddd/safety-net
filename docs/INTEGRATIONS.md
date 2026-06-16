# Integrations — guarding external agent frameworks

SafetyNet talks to agents over HTTP. Run the agent as its own Docker container, then point
SafetyNet at it (`UPSTREAM_TYPE` + `UPSTREAM_URL`, or a `clients/` preset in code).

## Framework comparison

| Framework | Core pattern | Native REST/OpenAPI | SafetyNet client | Best fit |
|---|---|---|---|---|
| **NeMo Guardrails** | Routing (Colang rails) | ✅ OpenAI-compatible `/v1/chat/completions` | `nemo_client()` | Philosophical-alignment rails (Deontology vs. Consequentialism) |
| **LangGraph Server** | Stateful graph / state machine | ✅ `/runs`, `/threads`, `/openapi.json` | `langgraph_client()` | Multi-agent workflows (movie-script writers' room) |
| **Dify** | Workflow + tool calling | ✅ per-app REST (`/v1/chat-messages`) | `dify_client()` | Image/video agents, unified tool calling |
| **CrewAI** | Role-based crews | ❌ wrap in FastAPI yourself | `crewai_client()` | Role/backstory modeling for a writers' room |

All four are guarded the same way: SafetyNet runs the PRE gate on the prompt, forwards to the
framework's endpoint, and runs the POST gate on the reply.

## NeMo Guardrails

```bash
docker run -p 8001:8000 -e OPENAI_API_KEY="sk-..." -v ./nemo-config:/config \
  nemoguardrails chat --config=/config
```
```bash
# point SafetyNet at it
UPSTREAM_TYPE=nemo UPSTREAM_URL=http://localhost:8001 docker compose up --build
```
NeMo speaks OpenAI's chat API, so `nemo_client()` / `UPSTREAM_TYPE=nemo` works out of the box.
Write a Colang deontological rail, then use SafetyNet to fire prompt-injection attempts that try
to force a consequentialist override and confirm both layers hold.

## LangGraph Server

```bash
langgraph up --port 8123            # or the langgraph-cli Docker image
```
```bash
UPSTREAM_TYPE=langgraph UPSTREAM_URL=http://localhost:8123 docker compose up --build
```
`langgraph_client()` POSTs to `/runs/wait` with `{assistant_id, input:{messages:[…]}}`; adjust
`assistant_id`/`input_key` to your graph.

## Dify

```bash
git clone https://github.com/langgenius/dify.git && cd dify/docker && docker compose up -d
```
```bash
UPSTREAM_TYPE=dify UPSTREAM_URL=http://localhost UPSTREAM_API_KEY=app-xxx docker compose up --build
```
`dify_client()` POSTs to `/v1/chat-messages` and reads `answer`. Use it to test malicious prompts
aimed at bypassing the agent's native image-safety filters — SafetyNet's `image_moderation`
scanner can re-check returned media.

## CrewAI

CrewAI ships no standalone server. Wrap your crew in a tiny FastAPI app:

```python
from fastapi import FastAPI
from pydantic import BaseModel
app = FastAPI()
class In(BaseModel): prompt: str
@app.post("/kickoff")
def kickoff(b: In): return {"result": my_crew.kickoff(inputs={"prompt": b.prompt})}
```
```bash
UPSTREAM_TYPE=crewai UPSTREAM_URL=http://localhost:8001 docker compose up --build
```
`crewai_client()` POSTs `{prompt}` to `/kickoff` and reads `result` — adjust to your wrapper.

## Custom / any OpenAI-compatible agent

```python
from safetynet.clients.http import OpenAIChatClient
client = OpenAIChatClient("http://my-agent:8000", model="my-model", api_key="…")
```
or generic:
```python
from safetynet.clients.http import HTTPAgentClient
client = HTTPAgentClient(base_url, path, request_builder=..., response_parser=...)
```
