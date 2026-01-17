# Alexandria HTMX Migration - Complete Fix Session

## CRITICAL: Read This Entire Prompt Before Doing Anything

I'm fixing a broken HTMX migration for my personal research library app called Alexandria. The migration from Next.js/React to HTMX+Jinja2 was rushed and now several things are broken. I need you to help me fix it PROPERLY this time - with actual debugging, not guessing.

---

## Project Location & Setup

```
Repository: ~/alexandria
Branch: feature/htmx-migration  
Backup branch: backup/pre-htmx-migration (safe restore point)
```

**Before writing ANY code, run these commands to understand the current state:**

```bash
cd ~/alexandria
git status
git log --oneline -5
```

---

## How to Start the App

**Terminal 1 - Database:**
```bash
docker start alexandria-db
```

**Terminal 2 - Backend (the one we're fixing):**
```bash
cd ~/alexandria/backend
pixi run dev
# Runs at http://localhost:8000/app/
```

**Terminal 3 - React reference (optional, for visual comparison):**
```bash
cd ~/alexandria/frontend  
npm run dev
# Runs at http://localhost:3000
```

---

## Database Connection (for debugging queries)

```
Host: localhost
Port: 5432
User: postgres
Password: localdev
Database: alexandria
```

Quick test:
```bash
PGPASSWORD=localdev psql -h localhost -U postgres -d alexandria -c "SELECT COUNT(*) FROM articles;"
```

---

## Critical File Locations

| File | Purpose | Notes |
|------|---------|-------|
| `backend/app/api/htmx.py` | ALL HTMX routes | **Main file to debug - ~800+ lines** |
| `backend/templates/base.html` | Base template | Tailwind CDN, HTMX, Alpine.js setup |
| `backend/templates/pages/index.html` | Article list page | |
| `backend/templates/pages/settings.html` | Settings page | **BROKEN - hangs forever** |
| `backend/templates/partials/sidebar.html` | Sidebar | **BROKEN - filtering doesn't work** |
| `backend/templates/partials/article_card.html` | Article cards | **BROKEN - checkboxes don't work** |
| `backend/app/api/routes/` | JSON API routes | **DO NOT MODIFY - WhatsApp bot uses these** |

---

## What's Currently Working

✅ Article list displays at /app/
✅ Search filters articles  
✅ Grid/list view toggle
✅ Article detail page
✅ Add article modal
✅ Ask/RAG chat page (loads)
✅ Remote add page
✅ Static files (logo)

---

## What's Broken (Fix in This Order)

### 1. Settings Page Hangs Forever
- **URL:** http://localhost:8000/app/settings
- **Symptom:** Page never loads, browser just spins
- **Likely causes:** N+1 database queries, blocking I/O without `await`, AI provider testing on page load
- **Test:** `curl -v --max-time 10 http://localhost:8000/app/settings`

### 2. Tailwind Styles Look Wrong/Ugly  
- **Symptom:** Pages render but don't look like the React version
- **Likely causes:** Tailwind CDN not loading, missing dark mode class, missing custom config
- **Test:** Check browser DevTools Network tab for tailwindcss.com requests, check if `class="dark"` is on `<html>`

### 3. Color Filtering Broken
- **Symptom:** Clicking colors in sidebar does nothing
- **Likely cause:** Missing `hx-get` attributes on color items in sidebar.html
- **Test:** 
  ```bash
  # Get a color ID first
  PGPASSWORD=localdev psql -h localhost -U postgres -d alexandria -c "SELECT id, name FROM colors LIMIT 5;"
  # Then test the route
  curl "http://localhost:8000/app/articles?color_id=<ID>" -H "HX-Request: true"
  ```

### 4. Category Filtering Broken
- **Symptom:** Clicking subcategories in sidebar does nothing  
- **Likely cause:** Missing `hx-get` attributes on category items in sidebar.html
- **Test:**
  ```bash
  PGPASSWORD=localdev psql -h localhost -U postgres -d alexandria -c "SELECT id, name FROM categories LIMIT 5;"
  curl "http://localhost:8000/app/articles?category_id=<ID>" -H "HX-Request: true"
  ```

### 5. Bulk Selection Checkboxes Don't Work
- **Symptom:** Clicking checkboxes on article cards does nothing
- **Likely cause:** Alpine.js not properly wired up
- **Test:** Check browser console (F12) for JavaScript errors when clicking

### 6. Read/Unread Feature Missing
- **Symptom:** Feature doesn't exist at all
- **Needs:** New route, new template, keyboard navigation
- **Reference:** `frontend/src/app/reader/[id]/page.tsx`
- **DO THIS LAST** after other bugs are fixed

---

## Debugging Rules - VERY IMPORTANT

1. **FIX ONE ISSUE AT A TIME** - Don't try to fix everything at once
2. **TEST AFTER EACH FIX** - Use curl first, then check in browser
3. **COMMIT AFTER EACH WORKING FIX** - `git add -A && git commit -m "Fix: <description>"`
4. **CHECK SERVER LOGS** - Watch the terminal running `pixi run dev` for Python errors
5. **DON'T GUESS** - If something isn't working, add logging/print statements to find out why
6. **COMPARE TO REACT** - If unsure how something should look/work, check the React version at :3000

---

## Your First Task: Set Up Debugging

Before fixing any bugs, I need you to:

1. **Read the key files** to understand the current state:
   - Read `backend/app/api/htmx.py` (focus on the settings_page function)
   - Read `backend/templates/base.html` (check Tailwind/HTMX/Alpine setup)
   - Read `backend/templates/partials/sidebar.html` (check for hx-get attributes)

2. **Check if Chrome DevTools MCP is available** by running:
   ```bash
   claude mcp list
   ```
   If chrome-devtools is NOT listed, tell me and I'll set it up.

3. **Start the backend** and test what's actually broken:
   ```bash
   cd ~/alexandria/backend
   # In background or separate terminal: pixi run dev
   
   # Then test:
   curl -v --max-time 10 http://localhost:8000/app/settings
   ```

4. **Report back** with:
   - What you found in the key files
   - Whether chrome-devtools MCP is available
   - What error/timeout you see from the curl command
   - Any Python errors in the server logs

**DO NOT write any code yet.** Just investigate and report what you find.

---

## When You're Ready to Fix

For each issue, follow this pattern:

1. **Diagnose:** Read relevant code, check logs, test with curl
2. **Plan:** Tell me what you think the problem is and how to fix it (don't code yet)
3. **Get approval:** Wait for me to say "go ahead" 
4. **Implement:** Make the minimal change needed
5. **Test:** Verify with curl, then browser
6. **Commit:** `git add -A && git commit -m "Fix: <description>"`

---

## If Everything Goes Wrong

```bash
# Reset to the working backup
cd ~/alexandria
git checkout backup/pre-htmx-migration

# Or just undo recent changes
git checkout -- .
```

---

## Additional Context

- This is a personal project, not production - so we can take risks
- The React frontend at :3000 is the "source of truth" for how things should look/work
- I'm not an expert developer, so explain what you're doing and why
- Previous Claude sessions rushed through this and broke things - let's be methodical this time

---

## Start Now

Please begin by reading the files and running the diagnostic commands listed in "Your First Task" above. Report back what you find before suggesting any fixes.
