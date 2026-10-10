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

## [0.2.0] - 2026-10-15

### Added
- **Object-Oriented Multi-Dimensional Tag Taxonomy (`TagClass` & `Tag`)**:
  - Orthogonal faceted classification (`TagClass`), single-inheritance trees within each facet (`parent_id`), and polymorphic virtual hypergraph links (`AssetUnitTagLink`) decoupled from single-anchor physical landing (`is_primary_landing`).
  - Dynamic domain preset templates (`backend/app/core/taxonomy_presets.py` — HiFi Music, Podcast & Audiobook, Photography & Visual Arts, Video & Film Studio, Clean Core) with non-destructive 1-click import (`POST /api/tags/presets/{preset_id}/apply`).
  - Full-screen Taxonomy Workspace (`TaxonomyWorkspaceView.vue`) and modal manager (`TagManagerModal.vue`) with visual tree navigation, batch reparenting, tag merge/synonym operations, and orphan tag cleanup.
- **Customizable Virtual-to-Physical Projection Pipeline Engine (`projection_dsl.py`)**:
  - Multi-stage path projection DSL (`ProjectionPipeline`) supporting custom folder templates, conditional workflow routing, dry-run diff previews, conflict warnings, and transactional rollback safety (`PipelineBuilderModal.vue`).
- **Externalized User Rules Engine (`user_rules.py` & `rules.example.json`)**:
  - Complete decoupling of the generic core indexing/tagging engine from personal or domain-specific creator aliases, honorific suffix stripping, domain mappings, and path filters via external `backend/data/config/user_rules.json`.
- **Series vs. Unit Dual-Topology Feed & Immersive Media Players**:
  - Smart series rollup (`is_series`, `media_breakdown`, `unit_count`) that prevents single-file folders from masquerading as multi-episode collections while accurately grouping multi-part works.
  - Dedicated `AudioImmersiveModal.vue` with synchronized LRC/WebVTT lyrics display, multi-track playlist drawer, and cover art ambient blur.
  - Enhanced `VideoPlayerModal.vue` with episode playlist drawer, dynamic subtitle track switcher, and continuous episode playback.
- **Streamlined UI/UX & Accessibility**:
  - Redesigned minimalist `Navbar.vue` with icon-first navigation, responsive 3-column `Workplace.vue` with integrated filter pills (`untagged` / `conflict`), and human-friendly terminology across all views.

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
