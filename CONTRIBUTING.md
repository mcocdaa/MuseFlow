# Contributing to MuseFlow (灵眸流)

Thank you for your interest in contributing to **MuseFlow**! We welcome community contributions, bug reports, and feature requests.

---

## 🛠️ Development Setup

### Prerequisites
- **Python**: 3.12 or higher (managed via [`uv`](https://github.com/astral-sh/uv))
- **Node.js**: 20+ with [`pnpm`](https://pnpm.io/)
- **FFmpeg**: 6.0+ (required for video thumbnailing, duration parsing, and format transcoding)

### 1. Backend Setup
```bash
cd backend
uv sync
uv run python run.py
# Backend runs at http://localhost:8765
```

### 2. Frontend Setup
```bash
cd frontend
pnpm install
pnpm dev
# Frontend runs at http://localhost:5173 (proxied to backend on :8765)
```

---

## 📐 Code Style & Conventions

- **Python**: Format with `ruff` or `black`, adhere to PEP 8, enforce type annotations with SQLModel / Pydantic.
- **Frontend**: Vue 3 `<script setup>`, Tailwind CSS v4, Lucide icons.
- **Architecture Invariant**: **NEVER** modify or delete raw physical files without explicit confirmation dialogs. All organizational hierarchies must be maintained virtually through `Collection` and `AssetUnit` relationships.

---

## 🚀 Submitting Pull Requests

1. Fork the repository and create your feature branch: `git checkout -b feat/my-new-feature`.
2. Commit your changes with clear messages (`feat: ...`, `fix: ...`, `docs: ...`).
3. Ensure both backend and frontend build cleanly without warnings (`pnpm build`).
4. Push to your branch and open a Pull Request against `master`.
