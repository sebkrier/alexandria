# HTMX Migration Plan: Alexandria

## Executive Summary

Migrate the Alexandria frontend from Next.js/React to HTMX + Jinja2 templates served directly by FastAPI. This reduces complexity, eliminates the Node.js dependency, and improves performance through server-side rendering.

---

## Current Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CURRENT STATE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────┐         ┌─────────────────────┐       │
│  │   Next.js (React)   │ ──JSON──▶│   FastAPI Backend   │       │
│  │      :3000          │◀──────── │       :8000         │       │
│  │                     │          │                     │       │
│  │  - Zustand store    │          │  - SQLAlchemy ORM   │       │
│  │  - TanStack Query   │          │  - PostgreSQL       │       │
│  │  - Client routing   │          │  - pgvector         │       │
│  │  - React components │          │  - AI services      │       │
│  └─────────────────────┘          └─────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Frontend Components Inventory (14 components, 5 pages)

**Pages:**
| Page | Location | Complexity | Notes |
|------|----------|------------|-------|
| Library (home) | `app/page.tsx` | Medium | Grid/list view, filters, bulk actions |
| Article Detail | `app/article/[id]/page.tsx` | High | Notes, tags, categories, color picker |
| Settings | `app/settings/page.tsx` | Medium | AI providers CRUD, colors, prompts |
| Unread Reader | `app/reader/[id]/page.tsx` | Medium | Keyboard nav, mark-as-read modal |
| Remote Add | `app/remote/page.tsx` | Low | Static documentation page |

**Components:**
| Component | Complexity | HTMX Pattern |
|-----------|------------|--------------|
| Sidebar | Medium | Partial with hx-target, category tree |
| Header | Low | Search form with hx-trigger="input" |
| ArticleCard | Medium | Partial template, checkbox state |
| AddArticleModal | Medium | Modal pattern with hx-boost |
| BulkActionBar | High | Selection tracking, confirm dialogs |
| AskModal | Medium | Form submission, streaming response |
| Modal | Low | Generic modal wrapper |
| Button | Low | CSS classes only |
| Input | Low | CSS classes only |
| Badge | Low | CSS classes only |

### State Management Analysis

**Current React State:**
```
Zustand Store:
├── sidebarOpen (boolean)
├── viewMode ("grid" | "list")
├── selectedCategoryId (string | null)
├── selectedColorId (string | null)
├── searchQuery (string)
├── addArticleModalOpen (boolean)
└── selectedArticleIds (Set<string>)
```

**HTMX Equivalent:**
- `viewMode` → URL query param `?view=grid|list`
- `selectedCategoryId` → URL query param `?category=uuid`
- `selectedColorId` → URL query param `?color=uuid`
- `searchQuery` → URL query param `?search=term`
- `sidebarOpen` → CSS class toggle via Alpine.js or `data-*`
- `addArticleModalOpen` → HTMX modal pattern
- `selectedArticleIds` → Form checkboxes + Alpine.js Set

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         TARGET STATE                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    FastAPI Backend (:8000)                   ││
│  │                                                              ││
│  │  ┌─────────────────┐  ┌──────────────────┐                 ││
│  │  │  JSON API       │  │  HTMX Routes     │                 ││
│  │  │  /api/v1/*      │  │  /app/*          │                 ││
│  │  │  (unchanged)    │  │  (new HTML)      │                 ││
│  │  └─────────────────┘  └──────────────────┘                 ││
│  │           │                    │                            ││
│  │           └────────┬───────────┘                            ││
│  │                    ▼                                        ││
│  │            ┌───────────────┐                                ││
│  │            │   Jinja2      │                                ││
│  │            │   Templates   │                                ││
│  │            └───────────────┘                                ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Browser: HTMX + Alpine.js (minimal JS)                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Migration Phases

### Phase 0: Foundation (This Phase - Planning Only)
- [x] Document current architecture
- [x] Create migration plan
- [ ] Add Jinja2 to dependencies
- [ ] Set up template directory structure
- [ ] Create base template with Tailwind CDN

### Phase 1: Base Layout & Static Pages
**Scope:** Create foundation and migrate simplest page first

**Templates to create:**
```
backend/templates/
├── base.html           # Layout with HTMX, Alpine.js, Tailwind CDN
├── components/
│   ├── sidebar.html    # Static version first
│   └── header.html     # Static version first
└── pages/
    └── remote.html     # Static docs page (easiest)
```

**Routes to add:**
```python
# backend/app/api/htmx.py
@router.get("/remote")  # Returns full HTML page
```

**Risk:** Low - Static page, no data dependencies
**Rollback:** Delete templates, remove route

---

### Phase 2: Library Page (Read-Only)
**Scope:** Main article list with filtering (no mutations yet)

**Templates to create:**
```
backend/templates/
├── pages/
│   └── library.html
├── components/
│   ├── article_card.html      # Grid view card
│   ├── article_row.html       # List view row
│   └── article_list.html      # Container for cards/rows
└── partials/
    └── article_grid.html      # HTMX partial for filtering
```

**HTMX Patterns:**
```html
<!-- Search with debounce -->
<input type="search"
       hx-get="/app/articles"
       hx-trigger="input changed delay:300ms"
       hx-target="#article-list"
       name="search">

<!-- Category filter -->
<button hx-get="/app/articles?category={{cat.id}}"
        hx-target="#article-list"
        hx-push-url="true">
```

**Risk:** Medium - Core functionality, but read-only
**Rollback:** Keep React frontend as default, HTMX as opt-in

---

### Phase 3: Sidebar & Navigation
**Scope:** Dynamic sidebar with category tree

**Templates:**
```
backend/templates/
├── components/
│   ├── sidebar.html           # Full sidebar
│   ├── category_item.html     # Recursive category tree
│   └── color_filter.html      # Color buttons
```

**Challenge:** Recursive category tree with expand/collapse
**Solution:** Alpine.js for expand/collapse state:
```html
<div x-data="{ expanded: false }">
  <button @click="expanded = !expanded">
    {{ category.name }}
  </button>
  <div x-show="expanded">
    {% for child in category.children %}
      {% include 'components/category_item.html' %}
    {% endfor %}
  </div>
</div>
```

**Risk:** Medium - Recursive rendering, state management
**Rollback:** Use simpler flat category list

---

### Phase 4: Article Detail Page
**Scope:** View and edit single article

**Templates:**
```
backend/templates/
├── pages/
│   └── article.html
├── components/
│   ├── summary_section.html
│   ├── notes_section.html
│   ├── tag_editor.html
│   ├── category_editor.html
│   └── color_picker.html
└── partials/
    ├── note_item.html
    └── note_form.html
```

**HTMX Patterns:**
```html
<!-- Add note -->
<form hx-post="/app/articles/{{article.id}}/notes"
      hx-target="#notes-list"
      hx-swap="afterbegin"
      hx-on::after-request="this.reset()">

<!-- Inline tag editing -->
<div hx-get="/app/articles/{{article.id}}/tags/edit"
     hx-trigger="click"
     hx-swap="outerHTML">
```

**Risk:** High - Multiple interactive elements
**Rollback:** Link to React detail page for editing

---

### Phase 5: Modals (Add Article, Ask, etc.)
**Scope:** Modal dialogs with form submission

**Templates:**
```
backend/templates/
├── modals/
│   ├── add_article.html
│   ├── ask_library.html
│   ├── confirm_delete.html
│   └── mark_as_read.html
```

**HTMX Modal Pattern:**
```html
<!-- Trigger -->
<button hx-get="/app/modals/add-article"
        hx-target="#modal-container"
        hx-swap="innerHTML">

<!-- Modal template -->
<div id="modal-backdrop" class="fixed inset-0 bg-black/60">
  <div class="modal-content">
    <form hx-post="/app/articles"
          hx-target="#article-list"
          hx-on::after-request="closeModal()">
      ...
    </form>
  </div>
</div>
```

**Risk:** Medium - Event handling, form state
**Rollback:** Keep modals as separate lightweight React components

---

### Phase 6: Bulk Operations
**Scope:** Select multiple articles, bulk actions

**Challenge:** Track selection state across page loads
**Solution:** Alpine.js store + hidden form:
```html
<div x-data="{ selected: new Set() }">
  <!-- Checkbox -->
  <input type="checkbox"
         :checked="selected.has('{{article.id}}')"
         @change="selected.has('{{article.id}}')
                  ? selected.delete('{{article.id}}')
                  : selected.add('{{article.id}}')">

  <!-- Bulk action bar -->
  <div x-show="selected.size > 0">
    <form hx-post="/app/articles/bulk/delete">
      <template x-for="id in Array.from(selected)">
        <input type="hidden" name="ids" :value="id">
      </template>
      <button type="submit">Delete Selected</button>
    </form>
  </div>
</div>
```

**Risk:** High - Complex client-side state
**Rollback:** Remove bulk operations from HTMX version

---

### Phase 7: Unread Reader
**Scope:** Focused reading mode with keyboard shortcuts

**Templates:**
```
backend/templates/
├── pages/
│   └── reader.html
├── components/
│   └── reader_nav.html
└── modals/
    └── mark_as_read.html
```

**Keyboard Navigation (minimal JS):**
```html
<script>
  document.addEventListener('keydown', (e) => {
    if (e.key === 'j') htmx.ajax('GET', '{{ prev_url }}', {target: 'body'});
    if (e.key === 'k') htmx.ajax('GET', '{{ next_url }}', {target: 'body'});
    if (e.key === 'o') window.open('{{ article.url }}');
    if (e.key === 'm') htmx.ajax('GET', '/app/modals/mark-read', {target: '#modal'});
  });
</script>
```

**Risk:** Medium - Keyboard handling, transitions
**Rollback:** Keep React reader, link from HTMX

---

### Phase 8: Settings Page
**Scope:** AI provider management, color labels

**Templates:**
```
backend/templates/
├── pages/
│   └── settings.html
├── components/
│   ├── provider_card.html
│   └── color_label.html
└── modals/
    └── add_provider.html
```

**Risk:** Low-Medium - Forms with validation
**Rollback:** Link to React settings

---

### Phase 9: Cleanup & Deprecation
**Scope:** Remove React frontend

- [ ] Remove `frontend/` directory
- [ ] Update documentation
- [ ] Update dev commands
- [ ] Remove npm from dependencies
- [ ] Update CLAUDE.md

---

## Dependencies to Add

```toml
# backend/pyproject.toml additions
dependencies = [
    # ... existing ...
    "jinja2>=3.1.0",           # Template engine
    "python-markdown>=3.5.0",  # Markdown rendering
]
```

---

## Tailwind CSS Migration

**Current:** Compiled by Next.js, custom classes in `tailwind.config.ts`

**Target:** Tailwind CDN with inline config:
```html
<script src="https://cdn.tailwindcss.com"></script>
<script>
  tailwind.config = {
    darkMode: 'class',
    theme: {
      extend: {
        colors: {
          dark: {
            bg: '#0f0f0f',
            surface: '#1a1a1a',
            border: '#2a2a2a',
            hover: '#333333',
            text: '#e5e5e5',
            muted: '#888888',
          },
          article: {
            blue: '#6B7FD7',
            green: '#5BA37C',
            orange: '#D4915D',
            purple: '#9B7FC7',
            red: '#D46A6A',
            gray: '#6B7280',
          }
        }
      }
    }
  }
</script>
```

---

## Risk Assessment Summary

| Phase | Risk Level | Impact if Failed | Mitigation |
|-------|------------|------------------|------------|
| 1 | Low | Minimal | Delete and retry |
| 2 | Medium | Core feature degraded | Keep React as fallback |
| 3 | Medium | Navigation broken | Flat category list fallback |
| 4 | High | Editing broken | React detail page for edits |
| 5 | Medium | Can't add articles | Minimal React modal |
| 6 | High | Bulk ops missing | Remove feature from HTMX |
| 7 | Medium | Reader degraded | Link to React reader |
| 8 | Low-Medium | Settings inaccessible | React settings fallback |

---

## Rollback Strategy

Each phase maintains:
1. **JSON API intact** - React can always work
2. **Feature flags** - Can toggle between React/HTMX
3. **Gradual rollout** - Test each phase before proceeding

**Emergency rollback:**
```bash
# Revert to React frontend
git checkout main -- frontend/
cd frontend && npm install && npm run dev
```

---

## Success Criteria

- [ ] All 5 pages render correctly in HTMX
- [ ] All CRUD operations work
- [ ] Bulk operations work
- [ ] Search and filtering work
- [ ] Keyboard shortcuts work in reader
- [ ] Visual appearance matches current design
- [ ] No JavaScript errors in console
- [ ] Performance equal or better than React

---

## Questions to Resolve Before Starting

1. **Alpine.js vs vanilla JS** - Alpine.js adds ~15KB but simplifies state management
2. **Markdown rendering** - Server-side (Python-Markdown) or client-side (marked.js)?
3. **Error handling** - Toast notifications vs inline errors?
4. **Loading states** - HTMX indicators vs skeleton loaders?

---

## Next Steps

1. Review and approve this plan
2. Add Jinja2 to backend dependencies
3. Create base template structure
4. Begin Phase 1: Foundation & Remote page
