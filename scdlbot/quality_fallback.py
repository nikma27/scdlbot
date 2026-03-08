"""Quality-aware fallback discovery for audio downloads."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

import requests
from mutagen import File as MutagenFile


LOSSLESS_EXTENSIONS = {"flac", "wav", "aiff", "alac", "ape"}
PREFERRED_SEARCH_PREFIXES = ("ytsearch5", "scsearch5")


class _YdlSilentLogger:
    def debug(self, msg: str) -> None:  # pragma: no cover - utility
        return

    def warning(self, msg: str) -> None:  # pragma: no cover - utility
        return

    def error(self, msg: str) -> None:  # pragma: no cover - utility
        return


@dataclass
class AudioQuality:
    """Describes the best known audio quality for a source."""

    lossless: bool
    bitrate_kbps: float
    sample_rate: int | None
    extension: str
    source_url: str


def _safe_lower(value: str | None) -> str:
    return (value or "").strip().lower()


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def inspect_local_audio_quality(file_paths: list[str]) -> AudioQuality | None:
    """Return best local audio quality from downloaded files."""
    best: AudioQuality | None = None
    for file_path in file_paths:
        path = Path(file_path)
        ext = path.suffix.lower().replace(".", "")
        if not ext:
            continue
        if ext not in LOSSLESS_EXTENSIONS and ext not in {"mp3", "m4a", "ogg", "opus", "webm", "aac"}:
            continue

        bitrate_kbps = 0.0
        sample_rate = None
        try:
            mf = MutagenFile(path)
            if mf and getattr(mf, "info", None):
                bitrate_kbps = round(float(getattr(mf.info, "bitrate", 0) or 0) / 1000.0, 1)
                sample_rate = getattr(mf.info, "sample_rate", None)
        except Exception:
            # Keep best-effort quality analysis; fallback should continue.
            pass

        is_lossless = ext in LOSSLESS_EXTENSIONS
        candidate = AudioQuality(
            lossless=is_lossless,
            bitrate_kbps=bitrate_kbps,
            sample_rate=sample_rate,
            extension=ext,
            source_url=str(path),
        )
        if _is_candidate_better(candidate, best):
            best = candidate
    return best


def build_query_from_local_tags(file_paths: list[str]) -> str:
    """Build search query from local tags/filenames."""
    artists: list[str] = []
    albums: list[str] = []
    titles: list[str] = []
    for file_path in file_paths:
        path = Path(file_path)
        try:
            mf = MutagenFile(path)
        except Exception:
            mf = None
        if mf and getattr(mf, "tags", None):
            tags = mf.tags
            artist = _clean_text(str(tags.get("TPE1") or tags.get("artist") or ""))
            title = _clean_text(str(tags.get("TIT2") or tags.get("title") or ""))
            album = _clean_text(str(tags.get("TALB") or tags.get("album") or ""))
            if artist:
                artists.append(artist)
            if album:
                albums.append(album)
            if title:
                titles.append(title)
    if artists and albums:
        return f"{artists[0]} {albums[0]}".strip()
    if artists and titles:
        return f"{artists[0]} {titles[0]}".strip()
    for file_path in file_paths:
        path = Path(file_path)
        stem = _clean_text(path.stem.replace("_", " ").replace("-", " "))
        if stem:
            return stem
    return ""


def find_better_source(
    *,
    query: str,
    current_quality: AudioQuality | None,
    ydl_module: Any,
    min_bitrate_kbps: int,
    prefer_lossless: bool,
    max_candidates: int,
    web_fallback: bool,
    proxy: str | None,
    source_ip: str | None,
) -> tuple[str, AudioQuality] | None:
    """Find better source URL by searching platforms, then web."""
    if not query:
        return None

    candidates = discover_platform_candidates(query, ydl_module, max_candidates)
    if web_fallback:
        candidates.extend(discover_web_candidates(query, max_candidates))

    seen = set()
    best_pair: tuple[str, AudioQuality] | None = None
    for candidate_url in candidates:
        if candidate_url in seen:
            continue
        seen.add(candidate_url)
        quality = probe_remote_quality(candidate_url, ydl_module, proxy=proxy, source_ip=source_ip)
        if not quality:
            continue
        if not _meets_floor(quality, min_bitrate_kbps=min_bitrate_kbps, prefer_lossless=prefer_lossless):
            # Keep only if still better than current and no strict floor candidate exists.
            if not _is_candidate_better(quality, current_quality):
                continue
        if best_pair is None or _is_candidate_better(quality, best_pair[1]):
            best_pair = (candidate_url, quality)

    if not best_pair:
        return None
    if _is_candidate_better(best_pair[1], current_quality):
        return best_pair
    return None


def discover_platform_candidates(query: str, ydl_module: Any, max_candidates: int) -> list[str]:
    """Discover candidate URLs from platform searches supported by yt-dlp."""
    results: list[str] = []
    for prefix in PREFERRED_SEARCH_PREFIXES:
        search_url = f"{prefix}:{query}"
        try:
            info = ydl_module.YoutubeDL(
                {
                    "skip_download": True,
                    "quiet": True,
                    "no_warnings": True,
                    "ignoreerrors": True,
                    "noplaylist": True,
                    "logger": _YdlSilentLogger(),
                }
            ).extract_info(search_url, download=False)
        except Exception:
            continue
        entries = info.get("entries") if isinstance(info, dict) else None
        if not entries:
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            candidate = entry.get("webpage_url") or entry.get("url")
            if candidate and candidate.startswith("http"):
                results.append(candidate)
            if len(results) >= max_candidates:
                return results
    return results


def discover_web_candidates(query: str, max_candidates: int) -> list[str]:
    """Search the web and collect candidate URLs as a last resort."""
    # DuckDuckGo html endpoint works in server-side scenarios without JS.
    search_url = f"https://duckduckgo.com/html/?q={quote(query + ' lossless flac')}"
    try:
        response = requests.get(search_url, timeout=8)
        response.raise_for_status()
    except Exception:
        return []
    hrefs = re.findall(r'href="([^"]+)"', response.text)
    urls: list[str] = []
    for href in hrefs:
        if "duckduckgo.com/l/?" in href and "uddg=" in href:
            parsed = urlparse(href)
            query_parts = parsed.query.split("&")
            uddg = None
            for part in query_parts:
                if part.startswith("uddg="):
                    uddg = part[len("uddg=") :]
                    break
            if not uddg:
                continue
            candidate = unquote(uddg)
        else:
            candidate = href
        if candidate.startswith("http"):
            urls.append(candidate)
        if len(urls) >= max_candidates:
            break
    return urls


def probe_remote_quality(
    url: str,
    ydl_module: Any,
    *,
    proxy: str | None,
    source_ip: str | None,
) -> AudioQuality | None:
    """Probe best available audio quality for URL with yt-dlp metadata."""
    opts: dict[str, Any] = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "noplaylist": True,
        "logger": _YdlSilentLogger(),
    }
    if proxy:
        opts["proxy"] = proxy
    if source_ip:
        opts["source_address"] = source_ip
    try:
        info = ydl_module.YoutubeDL(opts).extract_info(url, download=False)
        if isinstance(info, dict) and info.get("entries"):
            # For playlist-like entries, probe first item.
            first = next((x for x in info["entries"] if isinstance(x, dict)), None)
            if first:
                info = first
    except Exception:
        return None

    if not isinstance(info, dict):
        return None

    formats = info.get("formats") or []
    best_lossless = None
    best_lossy = None
    for fmt in formats:
        if not isinstance(fmt, dict):
            continue
        if fmt.get("vcodec") not in (None, "none"):
            continue
        ext = _safe_lower(fmt.get("ext"))
        abr = float(fmt.get("abr") or 0.0)
        tbr = float(fmt.get("tbr") or 0.0)
        bitrate = round(max(abr, tbr), 1)
        sample_rate = fmt.get("asr")
        q = AudioQuality(
            lossless=ext in LOSSLESS_EXTENSIONS or _safe_lower(fmt.get("acodec")).startswith("flac"),
            bitrate_kbps=bitrate,
            sample_rate=sample_rate,
            extension=ext or "unknown",
            source_url=url,
        )
        if q.lossless:
            if _is_candidate_better(q, best_lossless):
                best_lossless = q
        elif _is_candidate_better(q, best_lossy):
            best_lossy = q

    return best_lossless or best_lossy


def _meets_floor(quality: AudioQuality, *, min_bitrate_kbps: int, prefer_lossless: bool) -> bool:
    if quality.lossless:
        return True
    if prefer_lossless and quality.bitrate_kbps < min_bitrate_kbps:
        return False
    return quality.bitrate_kbps >= min_bitrate_kbps


def _is_candidate_better(candidate: AudioQuality | None, current: AudioQuality | None) -> bool:
    if candidate is None:
        return False
    if current is None:
        return True
    if candidate.lossless != current.lossless:
        return candidate.lossless and not current.lossless
    if candidate.bitrate_kbps != current.bitrate_kbps:
        return candidate.bitrate_kbps > current.bitrate_kbps
    return (candidate.sample_rate or 0) > (current.sample_rate or 0)
