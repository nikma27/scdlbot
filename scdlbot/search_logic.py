"""Pure search/query logic used by Telegram orchestration layer."""

from __future__ import annotations

import concurrent.futures
import logging
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from boltons.urlutils import URL

from scdlbot.quality_fallback import (
    AudioQuality,
    compute_title_match_ratio,
    discover_platform_candidates,
    discover_web_candidates,
    discover_youtube_candidates,
    probe_remote_quality,
)

logger = logging.getLogger(__name__)

QUERY_STOPWORDS = {
    "audio",
    "track",
    "tracks",
    "playlist",
    "playlists",
    "music",
    "video",
    "videos",
    "listen",
    "слушайте",
    "слушать",
    "музыка",
    "трек",
    "треки",
    "плейлист",
    "вк",
    "vk",
}
VK_AUDIO_ID_PATH_RE = re.compile(r"^audio-?\d+_\d+_[0-9a-f]+$", re.IGNORECASE)


def _sanitize_query_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _safe_log_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception:
        return str(url)[:120]


def _query_tokens(value: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Zа-яА-Я0-9]+", value.lower())
    return {token for token in tokens if len(token) > 1 and token not in QUERY_STOPWORDS}


def is_usable_query(query: str) -> bool:
    """Return True if query has enough semantic signal for search."""
    text = _sanitize_query_text(query).lower()
    if len(text) < 4:
        return False
    tokens = re.findall(r"[a-zA-Zа-яА-Я0-9]+", text)
    normalized_tokens = []
    for token in tokens:
        if len(token) <= 1:
            continue
        token_lower = token.lower()
        if token_lower in QUERY_STOPWORDS:
            continue
        if token_lower.isdigit():
            continue
        if re.fullmatch(r"[0-9a-f]{8,}", token_lower):
            continue
        if token_lower.startswith("audio") and any(char.isdigit() for char in token_lower):
            continue
        letters = len(re.findall(r"[a-zа-я]", token_lower))
        digits = len(re.findall(r"\d", token_lower))
        if letters < 2:
            continue
        if digits and len(token_lower) >= 10 and digits >= letters:
            continue
        normalized_tokens.append(token_lower)
    return len(normalized_tokens) >= 2


def build_query_from_message_text(message_text: str) -> str:
    """Extract artist/title-like query from plain text or from URL text."""
    text = _sanitize_query_text(message_text)
    if not text:
        return ""
    url_match = re.search(r"https?://\S+", text)
    if not url_match:
        return text
    url_text = url_match.group(0).rstrip(").,!?")
    try:
        url = URL(url_text)
        host = (url.host or "").lower()
        parsed_qs = parse_qs(urlparse(url_text).query)
        for key in ("q", "query", "text", "title"):
            if key in parsed_qs and parsed_qs[key]:
                candidate = _sanitize_query_text(unquote(parsed_qs[key][0]))
                if is_usable_query(candidate):
                    return candidate
        path_parts = [part for part in url.path_parts if part]
        vk_audio_part_match = (host in {"vk.com", "vk.ru"}) and any(VK_AUDIO_ID_PATH_RE.fullmatch(part) for part in path_parts)
        if vk_audio_part_match:
            candidate = _sanitize_query_text(text.replace(url_text, " ").strip())
            if is_usable_query(candidate):
                return candidate
            return ""
        words = []
        for part in path_parts:
            part_norm = part.replace("-", " ").replace("_", " ")
            words.extend(re.findall(r"[A-Za-zА-Яа-я0-9]+", part_norm))
        words = [w for w in words if not w.isdigit()]
        candidate = " ".join(words[:10])
        if is_usable_query(candidate):
            return candidate
    except Exception:
        logger.debug("build_query_from_message_text parse failed url=%s", _safe_log_url(url_text), exc_info=True)
    candidate = _sanitize_query_text(text.replace(url_text, " ").strip())
    if is_usable_query(candidate):
        return candidate
    return ""


def extract_query_from_source_metadata(
    url: str,
    ydl_module: Any,
    *,
    source_ip: str | None = None,
    proxy: str | None = None,
) -> str:
    """Try to derive artist/title query from source metadata."""
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "noplaylist": True,
    }
    if proxy:
        ydl_opts["proxy"] = proxy
    if source_ip:
        ydl_opts["source_address"] = source_ip
    try:
        info = ydl_module.YoutubeDL(ydl_opts).extract_info(url, download=False)
        if isinstance(info, dict) and info.get("entries"):
            info = next((x for x in info["entries"] if isinstance(x, dict)), None)
        if not isinstance(info, dict):
            return ""
    except Exception:
        logger.debug("extract_query_from_source_metadata failed url=%s", _safe_log_url(url), exc_info=True)
        return ""
    artist = info.get("artist") or info.get("uploader") or info.get("channel") or ""
    title = info.get("track") or info.get("title") or ""
    album = info.get("album") or ""
    candidate = _sanitize_query_text(f"{artist} {title}".strip())
    if is_usable_query(candidate):
        return candidate
    candidate = _sanitize_query_text(f"{artist} {title} {album}".strip())
    if is_usable_query(candidate):
        return candidate
    return ""


def search_high_quality_sources(
    query: str,
    ydl_module: Any,
    *,
    fallback_max_candidates: int,
    search_result_limit: int,
    enable_web_fallback: bool,
    youtube_min_height: int,
    source_ip: str | None = None,
    proxy: str | None = None,
    min_title_match: float = 0.45,
) -> list[tuple[str, AudioQuality]]:
    """Search candidate links and rank them by quality and relevance."""
    query_tokens = _query_tokens(query)
    candidates: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as discover_pool:
        futures: dict[str, concurrent.futures.Future[list[str]]] = {
            "youtube": discover_pool.submit(discover_youtube_candidates, query, ydl_module, fallback_max_candidates),
            "platform": discover_pool.submit(
                discover_platform_candidates,
                query,
                ydl_module,
                fallback_max_candidates,
                prefer_youtube=True,
            ),
        }
        if enable_web_fallback:
            futures["web"] = discover_pool.submit(discover_web_candidates, query, fallback_max_candidates)
        for source_name, future in futures.items():
            try:
                candidates.extend(future.result())
            except Exception:
                logger.warning("candidate discovery failed stage=%s query=%r", source_name, _sanitize_query_text(query)[:120], exc_info=True)

    seen = set()
    prepared = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        parsed = urlparse(candidate)
        candidate_text = unquote(f"{parsed.path} {parsed.query}").lower()
        candidate_tokens = _query_tokens(candidate_text)
        relevance = len(query_tokens & candidate_tokens) / max(1, len(query_tokens)) if query_tokens else 0.0
        prepared.append((candidate, relevance))
    if not prepared:
        return []

    ranked: list[tuple[tuple[float, ...], str, AudioQuality]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(prepared))) as probe_pool:
        future_map = {
            probe_pool.submit(
                probe_remote_quality,
                candidate,
                ydl_module,
                proxy=proxy,
                source_ip=source_ip,
            ): (candidate, relevance)
            for candidate, relevance in prepared
        }
        for future in concurrent.futures.as_completed(future_map):
            candidate, relevance = future_map[future]
            try:
                quality = future.result()
            except Exception:
                logger.debug("quality probe failed url=%s", _safe_log_url(candidate), exc_info=True)
                quality = None
            if quality is None:
                continue
            title_relevance = compute_title_match_ratio(query, quality.title or candidate)
            if title_relevance < min_title_match:
                continue
            try:
                host = (URL(candidate).host or "").lower()
            except Exception:
                host = ""
            youtube_hd = 1.0 if ("youtube.com" in host or "youtu.be" in host) and quality.max_video_height >= youtube_min_height else 0.0
            score = (
                youtube_hd,
                title_relevance,
                relevance,
                1.0 if quality.lossless else 0.0,
                float(quality.bitrate_kbps or 0),
                float(quality.sample_rate or 0),
                float(quality.max_video_height or 0),
            )
            ranked.append((score, candidate, quality))

    ranked.sort(key=lambda x: x[0], reverse=True)
    return [(url, quality) for _, url, quality in ranked[:search_result_limit]]


def format_search_choice_quality(quality: AudioQuality) -> str:
    """Format quality string for search result preview and buttons."""
    if quality.lossless:
        base = "lossless"
    else:
        bitrate = int(quality.bitrate_kbps) if quality.bitrate_kbps else 0
        base = f"{bitrate} kbps" if bitrate else "битрейт ?"
    details = [base]
    if quality.sample_rate:
        details.append(f"{quality.sample_rate} Hz")
    if quality.max_video_height:
        details.append(f"{quality.max_video_height}p")
    if quality.extension and quality.extension != "unknown":
        details.append(quality.extension.upper())
    return " · ".join(details)


def get_quality_points(quality: AudioQuality) -> int:
    """Calculate simple quality points used in UI preview ordering."""
    points = 0
    if quality.lossless:
        points += 1000
    points += int(quality.bitrate_kbps or 0)
    points += int((quality.sample_rate or 0) / 1000)
    points += int((quality.max_video_height or 0) / 10)
    return points
