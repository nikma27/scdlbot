"""
Провайдеры поиска музыки для FLAC бота.

Поддерживаемые источники:
- Spotify API: метаданные, превью (требует SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
- MusicBrainz: метаданные, ISRC (бесплатно)
- Bandcamp: поиск через yt-dlp (часто FLAC)
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TrackResult:
    """Результат поиска трека."""

    title: str
    artist: str
    album: str | None
    duration_ms: int | None
    source: str
    url: str | None
    preview_url: str | None
    artwork_url: str | None
    isrc: str | None
    quality_info: str | None  # "FLAC", "320kbps", "Lossless" и т.д.


def search_spotify(query: str, limit: int = 10) -> list[TrackResult]:
    """
    Поиск через Spotify API.
    Требует SPOTIFY_CLIENT_ID и SPOTIFY_CLIENT_SECRET в окружении.
    """
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
    except ImportError:
        logger.warning("spotipy не установлен: pip install spotipy")
        return []

    client_id = __import__("os").environ.get("SPOTIFY_CLIENT_ID")
    client_secret = __import__("os").environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        logger.warning("SPOTIFY_CLIENT_ID и SPOTIFY_CLIENT_SECRET не заданы")
        return []

    try:
        auth = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        sp = spotipy.Spotify(auth_manager=auth)
        results = sp.search(q=query, type="track", limit=limit)
    except Exception as e:
        logger.exception("Spotify search failed: %s", e)
        return []

    tracks = []
    for item in results.get("tracks", {}).get("items", []):
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        album = item.get("album", {})
        album_name = album.get("name")
        images = album.get("images", [])
        artwork = images[0]["url"] if images else None
        external = item.get("external_urls", {})
        spotify_url = external.get("spotify")

        tracks.append(
            TrackResult(
                title=item.get("name", ""),
                artist=artists,
                album=album_name,
                duration_ms=item.get("duration_ms"),
                source="Spotify",
                url=spotify_url,
                preview_url=item.get("preview_url"),
                artwork_url=artwork,
                isrc=item.get("external_ids", {}).get("isrc"),
                quality_info="Metadata only (Spotify не отдаёт FLAC)",
            )
        )
    return tracks


def search_musicbrainz(query: str, limit: int = 10) -> list[TrackResult]:
    """
    Поиск через MusicBrainz API.
    Бесплатно, без ключа. Возвращает ISRC для кросс-поиска.
    """
    try:
        import musicbrainzngs
    except ImportError:
        logger.warning("musicbrainzngs не установлен: pip install musicbrainzngs")
        return []

    musicbrainzngs.set_useragent("flacbot", "0.1", "https://github.com/gpchelkin/scdlbot")

    try:
        results = musicbrainzngs.search_recordings(query=query, limit=limit)
    except Exception as e:
        logger.exception("MusicBrainz search failed: %s", e)
        return []

    tracks = []
    for rec in results.get("recording-list", []):
        artists = ", ".join(
            a.get("artist", {}).get("name", "")
            for a in rec.get("artist-credit", [])
            if isinstance(a, dict) and "artist" in a
        )
        isrcs = rec.get("isrc-list", [])
        isrc = isrcs[0] if isrcs else None

        tracks.append(
            TrackResult(
                title=rec.get("title", ""),
                artist=artists,
                album=None,
                duration_ms=int(rec["length"]) if rec.get("length") else None,
                source="MusicBrainz",
                url=f"https://musicbrainz.org/recording/{rec.get('id', '')}" if rec.get("id") else None,
                preview_url=None,
                artwork_url=None,
                isrc=isrc,
                quality_info="Metadata + ISRC для кросс-поиска",
            )
        )
    return tracks


def search_bandcamp(query: str, limit: int = 5) -> list[TrackResult]:
    """
    Поиск на Bandcamp через поисковый URL.
    Bandcamp часто предлагает FLAC при покупке.
    """
    import urllib.parse

    encoded = urllib.parse.quote(query)
    search_url = f"https://bandcamp.com/search?q={encoded}"
    return [
        TrackResult(
            title=query,
            artist="",
            album=None,
            duration_ms=None,
            source="Bandcamp",
            url=search_url,
            preview_url=None,
            artwork_url=None,
            isrc=None,
            quality_info="FLAC при покупке",
        )
    ]


def search_all(query: str, limit_per_source: int = 5) -> list[TrackResult]:
    """Объединённый поиск по всем доступным источникам."""
    results = []
    results.extend(search_spotify(query, limit=limit_per_source))
    results.extend(search_musicbrainz(query, limit=limit_per_source))
    if not results:
        results.extend(search_bandcamp(query, limit=1))
    return results


def search_music(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Унифицированный поиск. Возвращает список словарей для бота.
    """
    raw = search_all(query, limit_per_source=limit)
    seen = set()
    output = []
    for t in raw:
        key = (t.artist.lower(), t.title.lower())
        if key in seen:
            continue
        seen.add(key)

        links = {}
        if t.url:
            links[t.source] = t.url
        if t.preview_url:
            links["Preview"] = t.preview_url

        output.append({
            "artist": t.artist or "?",
            "title": t.title or "?",
            "album": t.album or "",
            "quality": t.quality_info or "",
            "links": links,
        })
    return output
