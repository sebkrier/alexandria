"""
Shared constants for content extractors.

Centralizes timeout values, HTTP headers, and regex patterns used
across multiple extractor implementations.
"""

# =============================================================================
# Timeouts (in seconds)
# =============================================================================

DEFAULT_TIMEOUT = 30.0  # Standard timeout for URL fetching
PDF_TIMEOUT = 60.0  # PDFs can be large, allow more time
ARCHIVE_TIMEOUT = 15.0  # Timeout for archive.org lookups
BYPASS_TIMEOUT = 20.0  # Timeout for paywall bypass services

# =============================================================================
# User Agent Strings
# =============================================================================

# Chrome on Windows (most common)
CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Mobile Safari on iOS
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)

# =============================================================================
# HTTP Headers
# =============================================================================

# Base browser-like headers to avoid 403 blocks
BROWSER_HEADERS = {
    "User-Agent": CHROME_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-CH-UA": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "Cache-Control": "max-age=0",
}

# Headers for requests that appear to come from Google search
GOOGLE_REFERER_HEADERS = {
    **BROWSER_HEADERS,
    "Referer": "https://www.google.com/",
    "Sec-Fetch-Site": "cross-site",
}

# Simplified mobile headers
MOBILE_HEADERS = {
    "User-Agent": MOBILE_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}

# Headers for PDF downloads
PDF_HEADERS = {
    "User-Agent": CHROME_USER_AGENT,
    "Accept": "application/pdf,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# =============================================================================
# Text Cleaning Patterns
# =============================================================================

# Control characters to remove (keep \n, \r, \t)
CONTROL_CHARS_PATTERN = r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"

# Multiple newlines normalization
MULTIPLE_NEWLINES_PATTERN = r"\n{3,}"

# Multiple spaces normalization
MULTIPLE_SPACES_PATTERN = r" {2,}"


# =============================================================================
# Header Factory Functions
# =============================================================================


def get_headers(variant: str = "browser") -> dict[str, str]:
    """
    Get HTTP headers for the specified variant.

    Args:
        variant: One of "browser", "google", "mobile", "pdf"

    Returns:
        Dictionary of HTTP headers
    """
    headers_map = {
        "browser": BROWSER_HEADERS,
        "google": GOOGLE_REFERER_HEADERS,
        "mobile": MOBILE_HEADERS,
        "pdf": PDF_HEADERS,
    }
    return headers_map.get(variant, BROWSER_HEADERS).copy()
