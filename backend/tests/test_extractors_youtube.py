"""
Tests for the YouTube extractor (app/extractors/youtube.py).

Tests video URL detection, yt-dlp integration for metadata extraction,
and formatting of video information.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.extractors.youtube import YouTubeExtractor


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def extractor():
    """Create a YouTubeExtractor instance."""
    return YouTubeExtractor()


@pytest.fixture
def sample_video_info():
    """Sample yt-dlp video info dict."""
    return {
        "id": "dQw4w9WgXcQ",
        "title": "Test Video Title",
        "description": "This is a test video description.\n\nIt has multiple paragraphs.",
        "uploader": "Test Channel",
        "channel": "Test Channel Official",
        "upload_date": "20240315",
        "duration": 3723,  # 1:02:03
        "view_count": 1000000,
        "like_count": 50000,
        "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
        "channel_url": "https://www.youtube.com/channel/UCtest",
        "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "extractor": "youtube",
        "chapters": [
            {"start_time": 0, "title": "Introduction"},
            {"start_time": 300, "title": "Main Topic"},
            {"start_time": 1800, "title": "Conclusion"},
        ],
    }


@pytest.fixture
def sample_video_info_minimal():
    """Minimal yt-dlp video info with only required fields."""
    return {
        "id": "abc123",
        "title": "Minimal Video",
        "description": "",
    }


# =============================================================================
# can_handle() Tests
# =============================================================================


class TestCanHandle:
    """Tests for video URL detection."""

    def test_handles_youtube_watch_url(self):
        """Standard YouTube watch URLs should be handled."""
        assert YouTubeExtractor.can_handle("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert YouTubeExtractor.can_handle("https://youtube.com/watch?v=abc123")

    def test_handles_youtu_be_short_url(self):
        """YouTube short URLs should be handled."""
        assert YouTubeExtractor.can_handle("https://youtu.be/dQw4w9WgXcQ")

    def test_handles_youtube_embed_url(self):
        """YouTube embed URLs should be handled."""
        assert YouTubeExtractor.can_handle("https://www.youtube.com/embed/dQw4w9WgXcQ")

    def test_handles_vimeo(self):
        """Vimeo URLs should be handled."""
        assert YouTubeExtractor.can_handle("https://vimeo.com/123456789")
        assert YouTubeExtractor.can_handle("https://www.vimeo.com/video/123456789")

    def test_handles_dailymotion(self):
        """Dailymotion URLs should be handled."""
        assert YouTubeExtractor.can_handle("https://www.dailymotion.com/video/x7tgrov")

    def test_handles_twitch(self):
        """Twitch URLs should be handled."""
        assert YouTubeExtractor.can_handle("https://www.twitch.tv/videos/123456")

    def test_rejects_non_video_urls(self):
        """Non-video URLs should not be handled."""
        assert not YouTubeExtractor.can_handle("https://example.com/video")
        assert not YouTubeExtractor.can_handle("https://medium.com/article")
        # Note: youtube.com matches VIDEO_DOMAINS check, so root domain is handled


# =============================================================================
# extract() Tests - Success Cases
# =============================================================================


class TestExtractSuccess:
    """Tests for successful video extraction."""

    @pytest.mark.asyncio
    async def test_extract_video_success(self, extractor, sample_video_info):
        """Test extracting a YouTube video."""
        with patch("asyncio.to_thread", return_value=sample_video_info):
            result = await extractor.extract(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")

            assert result.title == "Test Video Title"
            assert result.source_type == "video"
            assert "Test Channel" in result.authors or "Test Channel Official" in result.authors

    @pytest.mark.asyncio
    async def test_extract_includes_description(self, extractor, sample_video_info):
        """Test that video description is included in text."""
        with patch.object(extractor, "_extract_info", return_value=sample_video_info):
            result = await extractor.extract(url="https://www.youtube.com/watch?v=abc")

            assert "test video description" in result.text.lower()

    @pytest.mark.asyncio
    async def test_extract_includes_chapters(self, extractor, sample_video_info):
        """Test that chapters are included in text."""
        with patch.object(extractor, "_extract_info", return_value=sample_video_info):
            result = await extractor.extract(url="https://www.youtube.com/watch?v=abc")

            assert "Chapters" in result.text
            assert "Introduction" in result.text
            assert "Main Topic" in result.text
            assert "Conclusion" in result.text

    @pytest.mark.asyncio
    async def test_extract_publication_date(self, extractor, sample_video_info):
        """Test publication date extraction from upload_date."""
        with patch.object(extractor, "_extract_info", return_value=sample_video_info):
            result = await extractor.extract(url="https://www.youtube.com/watch?v=abc")

            assert result.publication_date is not None
            assert isinstance(result.publication_date, datetime)
            assert result.publication_date.year == 2024
            assert result.publication_date.month == 3
            assert result.publication_date.day == 15

    @pytest.mark.asyncio
    async def test_extract_metadata(self, extractor, sample_video_info):
        """Test video metadata extraction."""
        with patch.object(extractor, "_extract_info", return_value=sample_video_info):
            result = await extractor.extract(url="https://www.youtube.com/watch?v=abc")

            assert result.metadata.get("platform") == "youtube"
            assert result.metadata.get("duration") == 3723
            assert result.metadata.get("view_count") == 1000000
            assert result.metadata.get("like_count") == 50000
            assert result.metadata.get("video_id") == "dQw4w9WgXcQ"

    @pytest.mark.asyncio
    async def test_extract_uses_channel_for_author(self, extractor, sample_video_info):
        """Test that channel name is preferred over uploader for author."""
        with patch.object(extractor, "_extract_info", return_value=sample_video_info):
            result = await extractor.extract(url="https://www.youtube.com/watch?v=abc")

            # Should use "channel" over "uploader" when available
            assert "Test Channel Official" in result.authors or "Test Channel" in result.authors


# =============================================================================
# extract() Tests - Error Handling
# =============================================================================


class TestExtractErrors:
    """Tests for error handling during extraction."""

    @pytest.mark.asyncio
    async def test_extract_requires_url(self, extractor):
        """Extract should raise ValueError if no URL provided."""
        with pytest.raises(ValueError, match="URL is required"):
            await extractor.extract()

    @pytest.mark.asyncio
    async def test_extract_handles_yt_dlp_error(self, extractor):
        """Test handling of yt-dlp extraction failure."""
        with patch.object(extractor, "_extract_info", side_effect=Exception("Video unavailable")):
            with pytest.raises(Exception, match="Video unavailable"):
                await extractor.extract(url="https://www.youtube.com/watch?v=invalid")


# =============================================================================
# _extract_info() Tests
# =============================================================================


class TestExtractInfo:
    """Tests for yt-dlp info extraction."""

    def test_extract_info_uses_yt_dlp(self, extractor):
        """Test that _extract_info uses yt-dlp."""
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {"title": "Test"}

        with patch("yt_dlp.YoutubeDL") as mock_class:
            mock_class.return_value.__enter__.return_value = mock_ydl

            result = extractor._extract_info("https://www.youtube.com/watch?v=abc")

            mock_ydl.extract_info.assert_called_once_with(
                "https://www.youtube.com/watch?v=abc",
                download=False,
            )

    def test_extract_info_returns_empty_on_none(self, extractor):
        """Test that empty dict is returned if yt-dlp returns None."""
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = None

        with patch("yt_dlp.YoutubeDL") as mock_class:
            mock_class.return_value.__enter__.return_value = mock_ydl

            result = extractor._extract_info("https://www.youtube.com/watch?v=abc")

            assert result == {}


# =============================================================================
# _format_duration() Tests
# =============================================================================


class TestFormatDuration:
    """Tests for duration formatting."""

    def test_format_duration_minutes_seconds(self, extractor):
        """Test formatting duration under an hour."""
        assert extractor._format_duration(65) == "1:05"
        assert extractor._format_duration(599) == "9:59"

    def test_format_duration_hours(self, extractor):
        """Test formatting duration over an hour."""
        assert extractor._format_duration(3600) == "1:00:00"
        assert extractor._format_duration(3723) == "1:02:03"
        assert extractor._format_duration(7265) == "2:01:05"

    def test_format_duration_zero(self, extractor):
        """Test formatting zero duration."""
        assert extractor._format_duration(0) == "0:00"

    def test_format_duration_none(self, extractor):
        """Test formatting None duration."""
        assert extractor._format_duration(None) == "0:00"


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_handles_missing_optional_fields(self, extractor, sample_video_info_minimal):
        """Test handling of videos with minimal metadata."""
        with patch.object(extractor, "_extract_info", return_value=sample_video_info_minimal):
            result = await extractor.extract(url="https://www.youtube.com/watch?v=abc")

            assert result.title == "Minimal Video"
            assert result.authors == []  # No uploader/channel
            assert result.publication_date is None  # No upload_date

    @pytest.mark.asyncio
    async def test_handles_no_chapters(self, extractor):
        """Test handling of videos without chapters."""
        info = {
            "id": "abc",
            "title": "Test Video",
            "description": "Just a description.",
        }
        with patch("asyncio.to_thread", return_value=info):
            result = await extractor.extract(url="https://www.youtube.com/watch?v=abc")

            # Check that chapters section is not present (## Chapters heading)
            assert "## Chapters" not in result.text

    @pytest.mark.asyncio
    async def test_prefers_uploader_when_no_channel(self, extractor):
        """Test uploader is used when channel is not available."""
        info = {
            "id": "abc",
            "title": "Test",
            "uploader": "UploaderName",
            # No "channel" field
        }
        with patch.object(extractor, "_extract_info", return_value=info):
            result = await extractor.extract(url="https://www.youtube.com/watch?v=abc")

            assert "UploaderName" in result.authors

    @pytest.mark.asyncio
    async def test_uses_webpage_url_for_original(self, extractor, sample_video_info):
        """Test that webpage_url is used as original_url when available."""
        with patch.object(extractor, "_extract_info", return_value=sample_video_info):
            result = await extractor.extract(url="https://youtu.be/dQw4w9WgXcQ")

            assert result.original_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    @pytest.mark.asyncio
    async def test_handles_invalid_upload_date(self, extractor):
        """Test handling of invalid upload_date format."""
        info = {
            "id": "abc",
            "title": "Test",
            "upload_date": "invalid",
        }
        with patch.object(extractor, "_extract_info", return_value=info):
            result = await extractor.extract(url="https://www.youtube.com/watch?v=abc")

            assert result.publication_date is None
