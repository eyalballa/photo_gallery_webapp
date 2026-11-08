# Stage 1: build the React wall
FROM node:24-slim AS web
RUN npm install -g pnpm@12.16.1
WORKDIR /web
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# Frontend tests (CI: docker build --target web-test .); `pnpm build` above already type-checked
FROM web AS web-test
RUN pnpm test

# Stage 2: the Python server, with the MediaPipe model baked in (backend/models/)
FROM python:3.12-slim AS app
# MediaPipe (EGL/GLES) and the full OpenCV it pulls in (X11/GL) load these even when headless
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libegl1 libgles2 libglib2.0-0 libxcb1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/wall ./wall
COPY backend/assets ./assets
COPY backend/models ./models
COPY --from=web /web/dist /app/frontend/dist
ENV PATH=/app/backend/.venv/bin:$PATH
# config.yaml and data/ are mounted at /app/backend (see docker-compose.yml)
EXPOSE 8000
# loopback only: Tailscale Serve (same network namespace) is the one way in
CMD ["python", "-m", "wall", "serve", "--host", "127.0.0.1"]

# Backend tests against the runtime image plus dev dependencies (CI: docker build --target test .)
FROM app AS test
RUN uv sync --frozen --no-install-project
COPY backend/tests ./tests
RUN pytest -q

# The default target: the runtime image
FROM app
