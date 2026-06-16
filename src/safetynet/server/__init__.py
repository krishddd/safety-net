"""SafetyNet HTTP gateway (optional ``[server]`` extra).

Run SafetyNet as a reverse proxy in front of a Dockerized agent: it guards the prompt, forwards
to the upstream agent, guards the response, and returns the result (or a refusal). See
``server/app.py`` and ``docs/DEPLOYMENT.md``.
"""
