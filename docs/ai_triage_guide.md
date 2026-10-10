# 🤖 AI Directory Topology Triage & Bundling Guide

One of MuseFlow's flagship innovations is solving messy, chaotic media folder structures using **Large Language Models (e.g. Grok-4.7, Claude 3.7, GPT-4o)** rather than fragile, hardcoded regex rules.

---

## 1. The Real-World Dilemma

Real-world personal media libraries rarely follow textbook folder conventions:
- **Nested Sub-series**: Folder `A` contains loose photos `a1.png`, `a2.png`, but also holds subfolder `B/` containing unrelated project photos `b1.png`, `b2.png`. Naive scanners dump all files into a single flat collection `A`.
- **Cross-directory Companion Files**: A subtitle file `ep1.srt` sits in `MyVlog/`, while the rendered video `ep1.mp4` and soundtrack `ep1_bgm.wav` are placed in `MyVlog/raw_footage/`.
- **Diverse Formats**: Beyond video subtitles, users have song lyrics (`.lrc`, `.slc`, `.cue`), Apple Live Photos (`.heic` + `.mov`), and camera RAW + JPEG pairs.

---

## 2. The Three-Tier Solution Pipeline

```
[ Ingested Files ]
       │
       ▼
┌──────────────────────────────────────────────┐
│  Tier 1: Fast Deterministic Rules            │
│  - Strict stem match in same folder          │ ──(Matched)──> Auto Bundle (0 Token cost)
│  - Standard formats (HEIC + MOV)             │
└──────────────────────┬───────────────────────┘
                       │ (Ambiguous / Cross-hierarchy)
                       ▼
┌──────────────────────────────────────────────┐
│  Tier 2: LLM Directory Topology Inference     │
│  - Extracts directory tree JSON              │
│  - Dispatches to LLM with topology prompt    │ ──(AI Plan)──> Structured Preview
└──────────────────────┬───────────────────────┘
                       │ (User-in-the-loop)
                       ▼
┌──────────────────────────────────────────────┐
│  Tier 3: One-Click Safe Database Application │
│  - Creates Collections & Bundles             │
│  - Physical files untouched                  │
└──────────────────────────────────────────────┘
```

---

## 3. API Contract & Schema

### Analyze Folder: `POST /api/ai/analyze_folder`
**Request:**
```json
{
  "folder_path": "/path/to/chaotic_media",
  "instruction": "Extract subfolder B as its own collection and bundle cross-level video/srt"
}
```

**Response:**
```json
{
  "summary": "Deep reasoning explaining why collections were separated and files bundled...",
  "collections": [
    {
      "name": "Collection A",
      "folder_rel_path": ".",
      "units": [
        {
          "title": "a1",
          "unit_type": "image",
          "primary_file": "a1.png",
          "auxiliary_files": []
        }
      ]
    },
    {
      "name": "Sub Collection B",
      "folder_rel_path": "B",
      "units": [
        {
          "title": "b1",
          "unit_type": "image",
          "primary_file": "B/b1.png",
          "auxiliary_files": []
        }
      ]
    }
  ],
  "recommended_supersets": [
    {
      "name": "Project A Complete Archive",
      "reason": "Encompasses top-level photos and sub-projects into a virtual dimension."
    }
  ]
}
```

### Apply Triage: `POST /api/ai/apply_triage`
Executes the approved plan into SQLite database relations without moving raw physical files.
