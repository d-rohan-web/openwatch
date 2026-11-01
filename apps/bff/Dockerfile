# build context: repo root (docker-compose.yaml)
# the backend for frontend: the only API the browser reaches (/ui/*); it calls the core api on the compose network
FROM python:3.15-slim
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY packages packages
COPY apps/__init__.py apps/__init__.py
COPY apps/bff apps/bff
RUN useradd -u 10001 -m openwatch
USER openwatch
EXPOSE 8000
CMD ["uvicorn", "apps.bff.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
