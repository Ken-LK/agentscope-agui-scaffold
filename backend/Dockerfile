# AgentScope 2.0 native AG-UI backend.
FROM python:3.12-slim AS base

# git is needed because agentscope is pinned to a git revision in pyproject.toml.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml ./
COPY app ./app
COPY config ./config
COPY scripts ./scripts

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8000

# Provide the model API key at runtime, e.g.:
#   docker run -e DASHSCOPE_API_KEY=... -p 8000:8000 <image>
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
