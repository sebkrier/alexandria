# Plan: Cloud Storage Abstraction with R2/S3 Support (Updated)

## Overview

Add a storage abstraction layer for PDF file persistence, following existing patterns (ABC + implementations). Uses single `S3CompatibleStorage` class that works with both Cloudflare R2 and AWS S3.

## Files to Create

```
backend/app/storage/
├── __init__.py      # Exports StorageProvider, get_storage_provider
├── base.py          # Abstract base class + StorageObject model
├── s3.py            # S3-compatible implementation (R2/S3)
└── factory.py       # Factory function with config-based instantiation

backend/tests/
└── test_storage.py  # Unit + integration tests
```

## Files to Modify

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Replace `boto3>=1.34.0` with `aioboto3>=13.0.0` |
| `backend/app/api/htmx.py` | Lines 1718-1746: Add R2 upload, Lines 608-651: Add R2 delete, Lines 1971-1988: Add bulk R2 delete |
| `backend/app/api/routes/articles.py` | Lines 207-239: Add R2 upload, Lines 553-574: Add R2 delete, Lines 726-755: Add bulk R2 delete |

## Implementation Steps

### Phase 1: Storage Layer (4 files)

1. **Create `app/storage/base.py`**
   - `StorageObject` Pydantic model (key, size, content_type, etag)
   - `StorageProvider` ABC with methods: `upload`, `download`, `delete`, `exists`, `get_url`, `health_check`

2. **Create `app/storage/s3.py`**
   - `S3CompatibleStorage` class using `aioboto3`
   - Constructor: `access_key_id`, `secret_access_key`, `bucket_name`, `endpoint_url` (None for AWS, set for R2)
   - All methods async

3. **Create `app/storage/factory.py`**
   - `get_storage_provider()` - returns configured provider or None if not configured
   - Uses existing R2 config from `settings` (`r2_access_key_id`, etc.)

4. **Create `app/storage/__init__.py`**
   - Export public API

5. **Update `pyproject.toml`**
   - Replace `boto3>=1.34.0` with `aioboto3>=13.0.0` (async S3 client, includes boto3)

### Phase 2: Tests

6. **Create `tests/test_storage.py`**
   - Unit tests for `StorageObject` model
   - Unit tests for factory returning None when unconfigured
   - Integration tests (skip if R2 not configured via env vars)
   - Test upload/download/delete cycle

### Phase 3: Upload Integration

7. **Modify `htmx.py` upload handler (lines 1718-1746)**

   Current flow problem: temp file deleted without R2 upload

   New flow:
   ```python
   content = await file.read()           # line 1721 - already exists
   # ... extraction ...

   # NEW: Upload to R2 if configured
   storage = get_storage_provider()
   if storage:
       storage_key = f"uploads/{current_user.id}/{uuid4()}.pdf"
       await storage.upload(key=storage_key, data=content, content_type="application/pdf")
       file_path = storage_key
   else:
       file_path = None  # Storage not configured

   article = Article(..., file_path=file_path, ...)
   ```

8. **Modify `routes/articles.py` upload handler (lines 207-239)**
   - Same pattern as htmx.py

### Phase 4: Download Endpoint

9. **Add to `htmx.py`**
   ```python
   @router.get("/article/{article_id}/pdf")
   async def get_article_pdf(...) -> RedirectResponse:
       # Verify ownership
       # Generate presigned URL via storage.get_url()
       # Return 307 redirect to presigned URL
   ```

### Phase 5: Delete Integration

10. **Update delete handlers** - add R2 file cleanup before database delete:
    - `htmx.py` delete_article (lines 635-639)
    - `htmx.py` bulk_delete (lines 1982-1984)
    - `routes/articles.py` delete_article (lines 571-574)
    - `routes/articles.py` bulk_delete_articles (lines 747-748)

    Pattern:
    ```python
    if article.file_path:
        storage = get_storage_provider()
        if storage:
            await storage.delete(article.file_path)
    ```

### Phase 6: Lint and Test

11. **Run linting and tests**
    ```bash
    cd backend
    pixi run lint
    pixi run lint-fix
    pixi run format
    pixi run test
    ```

## Key Design Decisions

1. **Single class for R2/S3** - Both use S3 API, difference is `endpoint_url`
2. **Async with aioboto3** - Matches project's async-first pattern (FastAPI, asyncpg, etc.)
3. **Optional storage** - Graceful degradation if not configured (returns None from factory)
4. **Presigned URLs** - Secure PDF access without exposing bucket credentials
5. **UUID in storage key** - Prevents filename collisions: `uploads/{user_id}/{uuid}.pdf`

## Verification

1. **Unit tests**: `pixi run test tests/test_storage.py`
2. **Manual test with R2**:
   - Set R2 env vars in `.env`
   - Upload a PDF via UI
   - Check R2 bucket has file
   - Click download link
   - Delete article, verify R2 file removed
3. **Test without R2**: Upload should work, file_path will be None

## Questions for Review

1. Should presigned URLs have a specific expiration time? (Default: 1 hour)
2. Should we add a `/api/articles/{id}/pdf` JSON API endpoint as well, or just HTMX?
