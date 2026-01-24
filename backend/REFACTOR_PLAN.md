# Alexandria Backend Refactoring Plan

**Generated:** 2026-01-23
**Status:** Phase 1 Analysis Complete - Awaiting Approval

---

## Executive Summary

The Alexandria backend codebase is in good health overall:
- **Lint:** All checks pass (ruff)
- **Naming conventions:** Consistent (snake_case functions, PascalCase classes)
- **No unused imports** detected
- **No bare except clauses**

However, several files have grown large and should be split for maintainability:
- `htmx.py` (3,158 lines) - **Critical**
- `articles.py` (1,123 lines) - **High Priority**
- 6 additional files over 400 lines - **Medium Priority**

---

## Phase 1 Findings

### 1. Lint Results

```
✅ All checks passed!
```

No linting issues to address.

---

### 2. Files Over 300 Lines (Candidates for Splitting)

| File | Lines | Priority | Recommendation |
|------|-------|----------|----------------|
| `app/api/htmx.py` | 3,158 | **CRITICAL** | Split into 7 feature modules |
| `app/api/routes/articles.py` | 1,123 | **HIGH** | Extract helpers, split by concern |
| `app/ai/llm.py` | 516 | HIGH | Split provider/parsing logic |
| `app/ai/query_router.py` | 463 | HIGH | Use strategy pattern for operations |
| `app/api/routes/library.py` | 461 | MEDIUM | Split export/import logic |
| `app/extractors/pdf.py` | 450 | MEDIUM | Extract font analysis module |
| `app/ai/service.py` | 449 | MEDIUM | Keep as-is, it's cohesive |
| `app/extractors/url.py` | 405 | LOW | Good structure, optional split |
| `app/api/routes/settings.py` | 343 | LOW | Optional: sub-routers |
| `app/ai/prompts.py` | 326 | NONE | Well-designed, no changes needed |

---

### 3. Duplicate/Similar Code Patterns

#### 3.1 User-Scoped Entity Fetching (48+ occurrences)

**Pattern appearing in:** articles.py, settings.py, tags.py, categories.py, notes.py, htmx.py, query_router.py

```python
result = await db.execute(
    select(Entity).where(
        Entity.id == entity_id,
        Entity.user_id == current_user.id,
    )
)
entity = result.scalar_one_or_none()
if not entity:
    raise HTTPException(status_code=404, detail="Entity not found")
```

**Recommendation:** Create `app/api/helpers/db.py`:
```python
async def get_user_entity_or_404(
    db: AsyncSession,
    model_class: type,
    entity_id: UUID,
    user_id: UUID,
    entity_name: str = "Entity"
) -> Any:
    """Fetch user-scoped entity or raise 404."""
```

---

#### 3.2 Article Eager Loading (6+ occurrences)

**Pattern appearing in:** articles.py (6x), library.py (1x)

```python
.options(
    selectinload(Article.categories).selectinload(ArticleCategory.category),
    selectinload(Article.tags).selectinload(ArticleTag.tag),
    selectinload(Article.notes),
)
```

**Recommendation:** Create query builder:
```python
def article_with_relations() -> Select:
    """Return Article query with relationships pre-loaded."""
```

---

#### 3.3 Bulk Operation Loop (3 occurrences in articles.py, 4 in htmx.py)

**Pattern:**
```python
for article_id in article_ids:
    try:
        # fetch article
        # perform operation
    except Exception as e:
        failed.append(...)
await db.commit()
return BulkResponse(succeeded=..., failed=...)
```

**Recommendation:** Create generic bulk operation helper in `app/api/helpers/bulk.py`.

---

#### 3.4 HTML Toast Responses with HX-Trigger (15+ in htmx.py)

**Pattern:**
```python
response = templates.TemplateResponse(
    request=request,
    name="components/toast.html",
    context={"toast_type": "success", "toast_message": "..."}
)
response.headers["HX-Trigger"] = "articlesUpdated"
return response
```

**Recommendation:** Create toast helper function.

---

### 4. Unused Imports & Dead Code

**Result:** ✅ No unused imports detected by ruff (F401) or static analysis.

**Minor issues:**
- 2 TODO comments in `articles.py` (lines 217, 571) about R2 storage
- 2 print statements that should use logger (articles.py:185-186)

---

### 5. Naming Conventions

**Result:** ✅ Consistent throughout codebase

- Functions: `snake_case` ✓
- Classes: `PascalCase` ✓
- Constants: `UPPER_SNAKE_CASE` ✓
- Private methods: `_leading_underscore` ✓

No violations found.

---

### 6. Functions Missing Type Hints

**80+ functions** are missing return type hints. Key files:

| File | Missing Hints |
|------|---------------|
| `app/api/htmx.py` | 40+ route handlers |
| `app/api/routes/*.py` | 25+ route handlers |
| `app/db/queries.py` | 4 functions |
| `app/ai/*.py` | 10+ functions |

Most are FastAPI route handlers where return types can be inferred but should be explicit for documentation.

**Recommendation:** Add return type hints during Phase 2 (safe cleanups).

---

### 7. God Files Analysis

#### 7.1 `app/api/htmx.py` (3,158 lines) - **CRITICAL**

**Current state:** 44 route handlers + 10 helper functions across 9 feature areas

**Proposed split:**

```
app/api/htmx/
├── __init__.py          # Main router, imports sub-routers
├── articles.py          # 10 routes - Library & CRUD
├── article_props.py     # 4 routes - Color, tags, categories, read status
├── ingestion.py         # 2 routes - URL & PDF upload
├── bulk.py              # 6 routes - Bulk operations
├── settings.py          # 9 routes - AI providers & colors
├── reader.py            # 5 routes - Reader mode
├── ask.py               # 2 routes - AI chat/Q&A
├── taxonomy.py          # 3 routes - Category optimization
└── helpers/
    ├── data_fetchers.py # fetch_sidebar_data, fetch_categories_with_counts, etc.
    ├── converters.py    # article_to_dict, article_to_detail_dict
    └── responses.py     # Toast builders, common responses
```

**Benefits:**
- Each file ~300-400 lines
- Feature-focused modules
- Easier to test and maintain
- Parallel development possible

---

#### 7.2 `app/api/routes/articles.py` (1,123 lines) - **HIGH**

**Current state:** 13 route handlers with embedded helpers

**Proposed changes:**

1. Extract `article_to_response()` to `app/api/helpers/converters.py`
2. Extract `_handle_content_query()` to `app/api/helpers/search.py`
3. Create `app/api/helpers/article_db.py` for common queries
4. Move note schemas to `app/schemas/note.py`

**After refactoring:** ~600 lines (routes only), with helpers extracted

---

#### 7.3 `app/ai/query_router.py` (463 lines) - **HIGH**

**Current state:** 200+ line if/elif chain for metadata operations

**Proposed changes:**

Use strategy pattern:
```python
# app/ai/metadata_operations.py
class MetadataOperation(ABC):
    @abstractmethod
    async def execute(self, db, user_id, params): ...

class TotalCountOperation(MetadataOperation): ...
class CountByCategoryOperation(MetadataOperation): ...
# etc.

OPERATIONS = {
    "TOTAL_COUNT": TotalCountOperation(),
    "COUNT_BY_CATEGORY": CountByCategoryOperation(),
    ...
}
```

---

#### 7.4 `app/extractors/pdf.py` (450 lines) - **MEDIUM**

**Current state:** Mixed concerns: download, parse, font analysis, thumbnail

**Proposed changes:**
- Extract `_extract_title_and_authors_from_font()` (145 lines) to `pdf_font_analysis.py`
- Keep main PDFExtractor as orchestrator

---

### 8. Other Issues

| Issue | Location | Severity | Action |
|-------|----------|----------|--------|
| Print statements | `articles.py:185-186` | Medium | Replace with logger |
| TODO comments | `articles.py:217,571` | Low | Track in backlog |
| Magic numbers | `articles.py:954,1017` | Low | Extract as constants |

---

## Proposed Refactoring Phases

### Phase 2: Safe Cleanups (Low Risk)

1. ✅ Remove unused imports (none found)
2. ✅ Remove dead code (none found)
3. ✅ Fix naming conventions (none needed)
4. Add return type hints to route handlers
5. Replace print() with logger in articles.py
6. Extract magic numbers as constants

**Estimated impact:** ~200 line changes, no behavior changes

---

### Phase 3: File Organization (Medium Risk)

**Priority order:**

1. **Create helper modules** (no import changes needed)
   - `app/api/helpers/db.py` - User entity fetching
   - `app/api/helpers/converters.py` - Response converters
   - `app/api/helpers/responses.py` - Toast/response builders

2. **Split htmx.py into feature modules**
   - Create `app/api/htmx/` directory structure
   - Move routes one feature at a time
   - Run tests after each move

3. **Refactor articles.py**
   - Extract helpers first
   - Keep routes in single file (manageable at ~600 lines after helpers extracted)

4. **Refactor query_router.py**
   - Implement strategy pattern for metadata operations
   - Keep backwards compatible

5. **Optional: Split remaining large files**
   - `pdf.py` font analysis extraction
   - `library.py` export/import split

---

### Phase 4: Code Quality (Higher Risk - Optional)

1. Improve error handling (already no bare except)
2. Extract business logic from route handlers
3. Add docstrings to public functions
4. Create database query builder for common patterns

---

## Files NOT to Change

Per project guidelines:
- ❌ Database models or migrations
- ❌ API route URLs (breaks existing clients)
- ❌ JSON API routes in `app/api/routes/` (WhatsApp bot dependency)

---

## Testing Strategy

After each change:
```bash
pixi run test      # Unit tests
pixi run lint      # Linting
pixi run e2e-headless  # E2E tests (after Phase 3)
```

---

## Approval Request

**Please review this analysis and approve before proceeding to Phase 2.**

Questions to consider:
1. Is the proposed htmx.py split structure acceptable?
2. Should we proceed with Phase 2 (safe cleanups) immediately?
3. Any files or patterns that should NOT be refactored?
4. Priority order for Phase 3 changes?

---

## Appendix: File Line Counts

### Application Code (>100 lines)
```
3158 app/api/htmx.py
1123 app/api/routes/articles.py
 516 app/ai/llm.py
 463 app/ai/query_router.py
 461 app/api/routes/library.py
 450 app/extractors/pdf.py
 449 app/ai/service.py
 405 app/extractors/url.py
 343 app/api/routes/settings.py
 326 app/ai/prompts.py
 235 app/ai/base.py
 223 app/db/queries.py
 199 app/schemas/article.py
 182 app/api/routes/notes.py
 182 app/api/routes/categories.py
 178 app/extractors/substack.py
 164 app/ai/factory.py
 136 app/extractors/lesswrong.py
 130 app/utils/article_helpers.py
 127 app/ai/embeddings.py
 122 app/extractors/youtube.py
 115 app/extractors/constants.py
 105 app/extractors/arxiv.py
 102 app/api/routes/tags.py
 100 app/core/constants.py
```

### Test Files (>200 lines)
```
 743 tests/test_ai_service.py
 723 tests/api/test_articles.py
 634 tests/conftest.py
 583 tests/test_extractors_pdf.py
 578 tests/e2e/conftest.py
 560 tests/test_extractors_url.py
 513 tests/test_ai_query_router.py
 472 tests/test_extractors_init.py
 472 tests/test_ai_llm.py
 446 tests/test_extractors_lesswrong.py
 391 tests/test_utils_auth.py
 387 tests/test_extractors_substack.py
 376 tests/api/test_settings.py
 340 tests/api/test_library.py
 324 tests/test_extractors_youtube.py
 322 tests/test_ai_factory.py
 293 tests/e2e/test_bulk_operations.py
 277 tests/api/test_categories.py
 276 tests/test_ai_embeddings.py
```
