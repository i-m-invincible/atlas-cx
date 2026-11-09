FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
WORKDIR /app
RUN pip install --no-cache-dir uv==0.11.2
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-cache --python /usr/local/bin/python
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
USER 10001:10001
EXPOSE 8000
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]

FROM base AS ai
USER root
RUN uv sync --frozen --no-dev --group ai --no-cache --python /usr/local/bin/python
USER 10001:10001

FROM base AS api
