FROM python:3.13-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /bin/uv

WORKDIR /app

ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"

FROM base AS test
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen
CMD ["pytest", "-q"]

FROM base AS runtime
CMD ["sanitas"]