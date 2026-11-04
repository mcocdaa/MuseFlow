# ==========================================
# Stage 1: Build Frontend (Vue 3 + Vite)
# ==========================================
FROM node:22-alpine AS frontend-builder

WORKDIR /build/frontend

# Copy frontend source (and prebuilt dist if already compiled on host)
COPY frontend/ ./

# Build frontend if dist/index.html is not already pre-compiled
RUN if [ ! -f dist/index.html ]; then \
      corepack enable && corepack prepare pnpm@latest --activate && \
      pnpm install --frozen-lockfile && \
      pnpm build; \
    fi

# ==========================================
# Stage 2: Runtime Container (Python 3.13)
# ==========================================
FROM python:3.13-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment defaults
ENV PYTHONUNBUFFERED=1 \
    MUSEFLOW_HOST=0.0.0.0 \
    MUSEFLOW_PORT=8765 \
    MUSEFLOW_DATA_DIR=/data \
    MUSEFLOW_FRONTEND_DIST=/app/frontend/dist

# Install Python dependencies
ARG PIP_INDEX_URL=https://pypi.org/simple
COPY backend/pyproject.toml backend/requirements.txt* ./backend/
WORKDIR /app/backend
RUN uv pip install --system --index-url ${PIP_INDEX_URL} -r requirements.txt

# Copy backend code
COPY backend/ /app/backend/

# Copy compiled frontend from Stage 1
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

# Create storage mounts
RUN mkdir -p /data/db /data/thumbnails /media && chmod -R 777 /data /media

VOLUME ["/data", "/media"]

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health')" || exit 1

CMD ["python", "run.py"]
