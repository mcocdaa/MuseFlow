# 🏛️ MuseFlow Architecture & Domain Modeling

This document details the architectural principles, domain abstractions, streaming protocol, and non-destructive indexing pipeline behind **MuseFlow (灵眸流)**.

---

## 1. Design Philosophy: The Dual-Mode Paradigm

Traditional media software forces a binary choice:
1. **Desktop DAM Tools (Eagle, Billfish, DigiKam)**: Superior at taxonomy and manual tagging, but lack passive, algorithmic immersion. Consuming content feels like working in an archive.
2. **Media Servers (Plex, Jellyfin, Immich)**: Polished streaming frontends, but rigid regarding folder structures. Complex composite packages (e.g. `video.mp4` accompanied by separate multi-channel `.wav` tracks and `.srt` subtitles) are fractured into disconnected orphan files.

**MuseFlow unifies both into a single system**:
- **Workplace Mode (管理态)**: Tree-based explorer, virtual tag topology, and AI-assisted reorganization without modifying original files.
- **Immersion Feed Mode (消费态)**: Social-media-inspired consumption (Xiaohongshu-style waterfall cards, TikTok-style vertical reels, Spotify-grade floating audio player).

---

## 2. Core Domain Entity Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    Virtual Superset (虚拟超集)                  │
│             (Cross-cutting query: e.g. "Friend Alice", "2024")  │
└────────────────────────────────┬────────────────────────────────┘
                                 │ Many-to-Many Dynamic Link
┌────────────────────────────────▼────────────────────────────────┐
│                       Collection (系列 / 集合)                   │
│               (Folder or Semantic Group: "Kyoto Trip 2024")     │
└────────────────────────────────┬────────────────────────────────┘
                                 │ 1-to-Many
┌────────────────────────────────▼────────────────────────────────┐
│               AssetUnit (原子消费单元 / 最小消费实体)              │
│       - Standalone Image (独立图片)                             │
│       - Standalone Video (独立视频)                             │
│       - Standalone Audio (独立音频)                             │
│       - Composite Bundle (复合包: mp4 + srt + wav / mp3 + lrc)  │
└────────────────────────────────┬────────────────────────────────┘
                                 │ 1-to-Many (Role-assigned)
┌────────────────────────────────▼────────────────────────────────┐
│                    AssetFile (物理磁盘映射文件)                 │
│         Roles: primary, video, audio, subtitle, lyrics          │
└─────────────────────────────────────────────────────────────────┘
```

### Key Invariants:
1. **AssetUnit as the Fundamental Consumption Particle**:
   - Recommendation engines and streaming feeds **only recommend `AssetUnit`s**, never orphan subtitle files or raw audio stems.
   - For a `bundle`, the primary video file drives the playback timeline, while companion files (subtitles, audio stems) are mounted as synchronized tracks.
2. **Non-destructive Indexing**:
   - Files are indexed by absolute path, SHA metadata, and filesystem stats.
   - Files are never renamed, relocated, or encrypted into proprietary containers without explicit user consent.

---

## 3. Media Processing & Streaming Pipeline

### 3.1 HTTP 206 Partial Content (Byte-Range Streaming)
Video and audio files are served via `GET /api/stream/file/{file_id}` with full support for the HTTP `Range` request header:
- Clients can seek instantaneously to any frame of a multi-gigabyte 4K video.
- Reduces memory footprint on mobile devices and Web clients.

### 3.2 Dynamic WebVTT Conversion
Browser `<video>` elements require WebVTT formatted subtitles (`.vtt`). MuseFlow includes an on-the-fly streaming converter (`GET /api/stream/subtitle/{file_id}`) that converts `.srt`, `.ass`, or `.sub` files to standard WebVTT with UTF-8 normalization.

### 3.3 Thumbnail Generation & Metadata Extraction
- **Videos**: FFmpeg captures a high-resolution frame at offset `00:00:01` scaled to 800px width.
- **Images**: Pillow generates Lanczos-downscaled JPEG previews.
- **Audio**: Mutagen extracts embedded ID3 APIC / FLAC PICTURE artwork.
