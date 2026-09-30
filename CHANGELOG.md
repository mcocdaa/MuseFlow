# Changelog (更新日志)

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Desktop native wrapper (.exe / macOS DMG) with system tray support.
- Local LLM backend support via Ollama / vLLM.
- AI smart auto-cropping for portrait thumbnails using OpenCV & saliency detection.
- WebDAV / SMB network share direct mounting.

---

## [0.1.0] - 2026-09-30

### Added
- **Core Architecture & Non-Destructive Ingestion**:
  - Implemented local-first non-destructive physical indexing engine (`backend/app/services/scanner.py`).
  - Added SQLModel + SQLite storage layer with `Collection`, `AssetUnit`, `AssetFile`, and `Superset` relational entities.
  - Implemented multi-tier Virtual Supersets (超集) allowing arbitrary cross-collection media grouping.
- **Atomic Bundle Detector (`mp4+srt+wav` / `mp3+lrc`)**:
  - Auto-detection and packaging of multi-track media bundles into unified `AssetUnit` particles.
  - Media stream processor with FFmpeg video thumbnail extraction and Mutagen audio ID3 album art parsing.
- **LLM Directory Topology Triage Engine**:
  - Deep-reasoning topology triage powered by Grok-4.7 (`backend/app/services/ai_organizer.py`).
  - Capable of resolving scattered files, multi-tier sub-collections (e.g. isolating subfolder `B` from `A`), and cross-folder subtitle/audio pairing.
  - Interactive AI reorganization preview modal with 1-click confirmation before virtual database mutation.
- **Dual-Mode Consumption Experience**:
  - **Workplace Mode**: Folder tree navigation, virtual supersets management, media topology inspector, and native OS folder highlighting (`explorer.exe /select`, `open -R`, `xdg-open`).
  - **Stream Feed Mode**: Xiaohongshu/Bilibili-style waterfall cards, 5-star rating, instant favorite toggle, and duration badges.
- **Integrated Immersive Media Players**:
  - **TikTok-style Swipe Reel Modal**: Fullscreen vertical video stream with up/down navigation, spacebar pause, and on-the-fly WebVTT subtitle tracks.
  - **Floating Audio Player Bar**: Spotify-grade floating player with persistent playback, visual progress bar, volume controls, and configurable sleep timer.
  - **Zoomable Lightbox Modal**: High-res image inspection with aspect-ratio preservation.
- **Pluggable Recommender Framework**:
  - Plugin registry supporting multiple simultaneous algorithms: `discover` (blended freshness & rating), `flashback` (rediscover forgotten archives), `affinity` (category-focused).
  - Telemetry pipeline with anti-hang dwell cap (`min(dwell, 180s)`) to safeguard recommendation vectors.
- **Theme Design System**:
  - 7 curated design themes: Cyber Dark, OLED Pure Black, Sakura Pink, Cyberpunk Neon, Forest Emerald, Sunset Amber, Studio Light.
  - Instant theme switching without reload with `localStorage` persistence.
- **Production & Containerization Readiness**:
  - Docker multi-stage build (`Dockerfile`) and Docker Compose service manifest (`compose.yaml`).
  - Automation scripts for local development (`scripts/dev.sh`), build (`scripts/build.sh`), and testing (`scripts/test.sh`).
  - Bilingual documentation in English and Simplified Chinese (`README.md` and `README_CN.md`).
