# SafetyNet security gateway image.
# Builds a REST service that guards prompts/responses and proxies to an upstream agent container.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POLICY_PATH=/app/policies/default.yaml \
    UPSTREAM_TYPE=stub

WORKDIR /app

# Install the package with the gateway extras first (better layer caching).
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[server]"

# Runtime config the server reads by default.
COPY policies ./policies

EXPOSE 8000
CMD ["uvicorn", "safetynet.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
