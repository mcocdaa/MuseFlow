import json
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from datetime import datetime, timezone
from sqlmodel import Session, select
from app.core.config import (
    LLM_BASE_URL,
    LLM_API_KEY,
    LLM_MODEL,
    ALL_MEDIA_EXTS,
    SUPPORTED_VIDEO_EXTS,
    SUPPORTED_AUDIO_EXTS,
    SUPPORTED_IMAGE_EXTS,
    SUPPORTED_SUBTITLE_EXTS,
)
from app.models.entities import Collection, AssetUnit, AssetFile
from app.services.media_processor import get_media_dimensions_and_duration, get_or_create_unit_thumbnail

def gather_folder_file_tree(folder_path: Path) -> List[Dict[str, Any]]:
    """递归收集文件夹下的所有媒体物理文件及其元数据，生成用于 LLM 分析的树状结构"""
    file_list = []
    for p in folder_path.rglob("*"):
        if p.is_file() and p.suffix.lower() in ALL_MEDIA_EXTS:
            try:
                rel = str(p.relative_to(folder_path)).replace("\\", "/")
                ext = p.suffix.lower()
                m_type = "unknown"
                if ext in SUPPORTED_VIDEO_EXTS:
                    m_type = "video"
                elif ext in SUPPORTED_AUDIO_EXTS:
                    m_type = "audio"
                elif ext in SUPPORTED_IMAGE_EXTS:
                    m_type = "image"
                elif ext in SUPPORTED_SUBTITLE_EXTS:
                    m_type = "subtitle_or_lyrics"

                file_list.append({
                    "relative_path": rel,
                    "file_name": p.name,
                    "extension": ext,
                    "media_type": m_type,
                    "size_bytes": p.stat().st_size,
                })
            except Exception:
                continue
    return file_list

def request_ai_triage(
    folder_path_str: str,
    custom_instruction: str = "",
    base_url: str = LLM_BASE_URL,
    api_key: str = LLM_API_KEY,
    model: str = LLM_MODEL
) -> Dict[str, Any]:
    """
    调用大语言模型 (grok-4.7) 深入分析混乱文件夹拓扑：
    1. 识别并提取应独立出来的子系列/子文件夹 (如 A/a1.png, A/B/b1.png -> 将 B 提升为独立系列)
    2. 解决跨层级/同名/语义关联的复合工程包 (如 A/ep1.srt 与 A/raw/ep1.mp4 绑为单一复合单元)
    3. 支持音乐伴侣 (lrc/slc/cue) 与视频伴侣 (srt/vtt/wav)
    """
    target_path = Path(folder_path_str).resolve()
    if not target_path.exists():
        raise ValueError(f"Directory {folder_path_str} does not exist")

    files = gather_folder_file_tree(target_path)
    if not files:
        return {
            "status": "empty",
            "message": "该目录下未扫描到任何受支持的多媒体文件",
            "folder": str(target_path),
            "suggested_collections": []
        }

    system_prompt = """你是一个世界顶级的个人数字资产管理与媒体架构 AI。
用户的本地文件夹非常混乱，存在以下常见情况：
1. 嵌套子系列：例如主文件夹叫 A，A 根目录下有 a1.png、a2.png，但里面有个子文件夹 B 存有 b1.png、b2.png。此时子文件夹 B 应该被识别为一个【独立的子系列 (Sub-Collection)】提取出来，而不能和 A 的顶层图片混在一起！
2. 跨目录或分散的复合包：例如跨目录存放的视频与字幕（如 Cross_Vlog/ep1.srt 与 Cross_Vlog/raw_footage/ep1.mp4、ep1_bgm.wav），它们本质上是属于同一作品的复合包（bundle），必须合并为同一个原子消费单元（AssetUnit），由 ep1.mp4 担任 primary，字幕和音轨担任 auxiliary。
3. 伴侣文件识别：不仅有 mp4+srt，还包括 mp3/flac 搭配 lrc/slc 歌词、cue 分轨、或者照片伴侣文件。
4. 独立文件：散落的照片、独立短视频应归类为独立的原子单元。

请深入分析文件路径拓扑与命名语义，返回且仅返回符合以下 JSON 格式的方案：
{
  "summary": "详细分析说明：为什么要把某些子文件夹提取为独立系列，为什么要把哪些跨目录文件打包为复合单元",
  "collections": [
    {
      "name": "系列/集合名称 (例如: 'A 主系列' 或 'B 子工程')",
      "folder_rel_path": "相对主目录的路径 (如 '.' 或 'Sub_Project_B')",
      "description": "系列描述",
      "units": [
        {
          "title": "单元标题 (如 '东京 Vlog 第一期')",
          "unit_type": "bundle" | "video" | "image" | "audio",
          "primary_file": "主要文件的相对路径 (如 'Cross_Folder_Vlog/raw_footage/ep1.mp4')",
          "auxiliary_files": [
            {
              "path": "附属文件相对路径 (如 'Cross_Folder_Vlog/ep1.srt')",
              "role": "subtitle" | "audio" | "lyrics" | "companion"
            }
          ],
          "reason": "打包/拆分原因"
        }
      ]
    }
  ],
  "recommended_supersets": [
    {
      "name": "超集建议名称 (如 '2024精选' 或 '某人专集')",
      "reason": "建议理由"
    }
  ]
}
注意：请务必确保每一个扫描到的媒体文件都被合理分配，不要遗漏，且直接输出纯 JSON，不要包含任何 markdown 代码块标记。"""

    user_prompt = f"""待分析的目标根目录：{target_path.name}
物理文件列表（共 {len(files)} 个文件）：
{json.dumps(files, ensure_ascii=False, indent=2)}

用户补充指令：{custom_instruction or '请智能分析，将独立的子文件夹剥离为独立系列，并将跨目录同名或配对音画字幕打包为一个单元。'}"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 4000
    }

    url = f"{base_url.rstrip('/')}/chat/completions"
    
    last_err = None
    # Try direct first with 120s timeout, then try proxy if available
    clients_to_try = [
        httpx.Client(timeout=120.0),
        httpx.Client(proxy="http://127.0.0.1:7897", timeout=120.0),
    ]

    raw_content = None
    for client in clients_to_try:
        try:
            with client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                resp_json = response.json()
                raw_content = resp_json["choices"][0]["message"]["content"].strip()
                break
        except Exception as e:
            last_err = e
            continue

    if not raw_content:
        raise RuntimeError(f"Failed to communicate with AI API after attempts: {last_err}")

    # Clean markdown codeblocks if model returned ```json ... ```
    if raw_content.startswith("```"):
        lines = raw_content.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw_content = "\n".join(lines).strip()

    plan = json.loads(raw_content)
    plan["target_folder"] = str(target_path)
    plan["total_scanned_files"] = len(files)
    return plan

def apply_ai_triage_plan(session: Session, folder_path_str: str, plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据 AI 给出的拓扑与重组方案，安全地在 MuseFlow 数据库中构建或更新系列 (Collection) 与复合包 (AssetUnit)。
    保持底层物理文件不动（零破坏风险）。
    """
    target_path = Path(folder_path_str).resolve()
    collections_data = plan.get("collections", [])
    
    created_collections_count = 0
    created_units_count = 0

    for col_data in collections_data:
        col_name = col_data.get("name", "未命名系列")
        col_rel = col_data.get("folder_rel_path", ".")
        col_abs = target_path / col_rel if col_rel != "." else target_path

        # Find or create collection
        col = session.exec(select(Collection).where(Collection.folder_path == str(col_abs))).first()
        if not col:
            col = Collection(
                name=col_name,
                folder_path=str(col_abs),
                description=col_data.get("description", "")
            )
            session.add(col)
            session.commit()
            session.refresh(col)
            created_collections_count += 1
        else:
            col.name = col_name
            col.description = col_data.get("description", col.description)
            session.add(col)
            session.commit()

        # Process units inside collection
        for u_info in col_data.get("units", []):
            title = u_info.get("title", "未命名单元")
            unit_type = u_info.get("unit_type", "bundle")
            primary_rel = u_info.get("primary_file")
            if not primary_rel:
                continue

            primary_abs = target_path / primary_rel
            if not primary_abs.exists():
                continue

            # Check if this primary file is already mapped
            existing_file = session.exec(
                select(AssetFile).where(AssetFile.file_path == str(primary_abs.resolve()))
            ).first()

            unit = None
            if existing_file and existing_file.asset_unit_id:
                unit = session.get(AssetUnit, existing_file.asset_unit_id)

            w, h, dur = get_media_dimensions_and_duration(primary_abs)

            if not unit:
                unit = AssetUnit(
                    title=title,
                    unit_type=unit_type,
                    collection_id=col.id,
                    duration_seconds=dur,
                    width=w,
                    height=h
                )
                session.add(unit)
                session.commit()
                session.refresh(unit)
                created_units_count += 1
            else:
                unit.title = title
                unit.unit_type = unit_type
                unit.collection_id = col.id
                session.add(unit)
                session.commit()

            # Link primary file
            if not existing_file:
                stat = primary_abs.stat()
                mime, _ = mimetypes.guess_type(str(primary_abs))
                existing_file = AssetFile(
                    file_path=str(primary_abs.resolve()),
                    file_name=primary_abs.name,
                    extension=primary_abs.suffix.lower(),
                    mime_type=mime or "application/octet-stream",
                    file_size=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                    asset_unit_id=unit.id,
                    role="primary"
                )
                session.add(existing_file)
                session.commit()
                session.refresh(existing_file)

            unit.cover_file_id = existing_file.id
            if not col.cover_asset_id:
                col.cover_asset_id = unit.id
                session.add(col)

            # Link auxiliary files (subtitles, audio, companion)
            for aux in u_info.get("auxiliary_files", []):
                aux_rel = aux.get("path")
                role = aux.get("role", "auxiliary")
                if not aux_rel:
                    continue
                aux_abs = target_path / aux_rel
                if not aux_abs.exists():
                    continue

                aux_file = session.exec(
                    select(AssetFile).where(AssetFile.file_path == str(aux_abs.resolve()))
                ).first()

                if not aux_file:
                    stat = aux_abs.stat()
                    mime, _ = mimetypes.guess_type(str(aux_abs))
                    aux_file = AssetFile(
                        file_path=str(aux_abs.resolve()),
                        file_name=aux_abs.name,
                        extension=aux_abs.suffix.lower(),
                        mime_type=mime or "text/plain",
                        file_size=stat.st_size,
                        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                        asset_unit_id=unit.id,
                        role=role
                    )
                    session.add(aux_file)
                else:
                    aux_file.asset_unit_id = unit.id
                    aux_file.role = role
                    session.add(aux_file)

            session.commit()

            # Generate thumbnail
            try:
                get_or_create_unit_thumbnail(unit.id, str(primary_abs), unit.unit_type)
            except Exception as e:
                print(f"Thumbnail error: {e}")

    return {
        "status": "success",
        "collections_created": created_collections_count,
        "units_created": created_units_count,
        "summary": plan.get("summary", "")
    }
