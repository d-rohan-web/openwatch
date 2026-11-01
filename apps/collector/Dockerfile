# build context: repo root (docker-compose.yaml)
FROM python:3.15-slim
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY packages packages
COPY apps/__init__.py apps/__init__.py
COPY apps/collector apps/collector
RUN useradd -u 10001 -m openwatch && mkdir -p /data && chown openwatch /data
USER openwatch
EXPOSE 9101
CMD ["python", "-m", "apps.collector.main"]
