# API and worker image. Build context is the repository root.
FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/pyproject.toml
COPY grader/pyproject.toml grader/pyproject.toml
COPY backend/src backend/src
COPY grader/src grader/src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm
# The worker drives the host's Docker daemon to start sandboxes (through a socket-proxy in
# production; see docs/adr/0010).
COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=build /app/.venv /app/.venv
WORKDIR /app
COPY backend/alembic.ini backend/alembic.ini
COPY backend/alembic backend/alembic
COPY content content
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 LATTICE_CONTENT_DIR=/app/content
RUN useradd --uid 10002 --no-create-home --shell /usr/sbin/nologin app
USER app
EXPOSE 8000
CMD ["uvicorn", "lattice.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
