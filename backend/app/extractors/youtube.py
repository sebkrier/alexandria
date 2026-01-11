"""YouTube and video extractor using yt-dlp"""

import asyncio
import re
from urllib.parse import urlparse
from datetime import datetime

import yt_dlp

from app.extractors.base import BaseExtractor, ExtractedContent


class YouTubeExtractor(BaseExtractor):
    """Extract content from YouTube and other video platforms.

    Supports: YouTube, Vimeo, and other platforms supported by yt-dlp.
    """

    # Video platforms we explicitly support
    VIDEO_DOMAINS = [
        "youtube.com",
        "youtu.be",
        "vimeo.com",
        "dailymotion.com",
        "twitch.tv",
    ]

    @staticmethod
    def can_handle(url: str) -> bool:
        """Check if URL is a video link"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")

        for video_domain in YouTubeExtractor.VIDEO_DOMAINS:
            if video_domain in domain:
                return True

        return False

    async def extract(self, url: str = None, file_path: str = None) -> ExtractedContent:
        if not url:
            raise ValueError("URL is required for YouTubeExtractor")

        # Run yt-dlp in thread pool to avoid blocking
        info = await asyncio.to_thread(self._extract_info, url)

        # Parse upload date
        pub_date = None
        if info.get("upload_date"):
            try:
                pub_date = datetime.strptime(info["upload_date"], "%Y%m%d")
            except ValueError:
                pass

        # Build text content from title, description, and chapters
        text_parts = []

        if info.get("title"):
            text_parts.append(f"# {info['title']}\n")

        if info.get("description"):
            text_parts.append(info["description"])

        # Add chapter information if available
        if info.get("chapters"):
            text_parts.append("\n\n## Chapters\n")
            for chapter in info["chapters"]:
                start = self._format_duration(chapter.get("start_time", 0))
                title = chapter.get("title", "Untitled")
                text_parts.append(f"- [{start}] {title}")

        text = "\n".join(text_parts)

        # Get channel/uploader as author
        authors = []
        if info.get("uploader") or info.get("channel"):
            authors = [info.get("channel") or info.get("uploader")]

        return ExtractedContent(
            title=info.get("title", "Untitled Video"),
            text=self._clean_text(text),
            authors=authors,
            publication_date=pub_date,
            source_type="video",
            original_url=info.get("webpage_url") or url,
            metadata={
                "platform": info.get("extractor", "unknown"),
                "duration": info.get("duration"),
                "duration_string": self._format_duration(info.get("duration")),
                "view_count": info.get("view_count"),
                "like_count": info.get("like_count"),
                "thumbnail": info.get("thumbnail"),
                "channel_url": info.get("channel_url"),
                "video_id": info.get("id"),
            },
        )

    def _extract_info(self, url: str) -> dict:
        """Extract video information using yt-dlp (sync)"""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
            "no_color": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info or {}

    def _format_duration(self, seconds: int | None) -> str:
        """Format seconds into HH:MM:SS or MM:SS"""
        if not seconds:
            return "0:00"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
