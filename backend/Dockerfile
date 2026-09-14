FROM python:3.13.15-slim-bookworm@sha256:ed86c82274b3c69b52fb5820f358f0bd7df0b603332063cb5c6e32bd220c3e6e AS base
COPY --from=ghcr.io/astral-sh/uv:0.12.13@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home app
COPY pyproject.toml uv.lock ./

FROM base AS runtime
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY alembic.ini ./
RUN uv sync --locked --no-dev --no-editable
USER app
EXPOSE 8000
CMD ["uvicorn", "counterparty.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]

FROM base AS test
ENV RUFF_CACHE_DIR=/tmp/ruff-cache
RUN uv sync --locked --no-install-project
COPY src ./src
COPY alembic.ini ./
COPY tests ./tests
RUN uv sync --locked --no-editable
USER app
CMD ["pytest", "-p", "no:cacheprovider"]
