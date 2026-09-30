# ==========================================
# Stage 1: Build Frontend (Vue 3 + Vite)
# ==========================================
FROM node:22-alpine AS frontend-builder

WORKDIR /build/frontend

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Cache dependencies
COPY frontend/package.json ./
RUN pnpm install --frozen-lockfile || pnpm install

# Copy source and build
COPY frontend/ ./
RUN pnpm build

# ==========================================
# Stage 2: Runtime Container (Python + FFmpeg)
# ==========================================
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies (FFmpeg for media processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment defaults
ENV PYTHONUNBUFFERED=1 \
    MUSEFLOW_HOST=0.0.0.0 \
    MUSEFLOW_PORT=8765 \
    MUSEFLOW_DATA_DIR=/data \
    MUSEFLOW_FRONTEND_DIST=/app/frontend/dist

# Install Python dependencies
COPY backend/pyproject.toml ./backend/
WORKDIR /app/backend
RUN uv pip install --system -r <(uv pip compile pyproject.toml) || uv pip install --system fastapi uvicorn[standard] sqlmodel aiofiles mutagen pillow python-multipart httpx watchfiles

# Copy backend code
COPY backend/ /app/backend/

# Copy compiled frontend from Stage 1
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

# Create storage mounts
RUN mkdir -p /data/db /data/thumbnails /media

VOLUME ["/data", "/media"]

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8765/api/health || exit 1

CMD ["python", "run.py"]
