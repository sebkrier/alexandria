# ArticleCard.tsx Complete Analysis

## Source Files
- `frontend/src/components/articles/ArticleCard.tsx`
- `frontend/src/components/ui/Badge.tsx`
- `frontend/src/components/ui/MediaTypeBadge.tsx`

---

## Data Fields Used

```typescript
article.id                    // string - UUID
article.source_type           // "url" | "pdf" | "arxiv" | "video"
article.media_type            // "article" | "paper" | "video" | "blog" | "pdf" | "newsletter"
article.processing_status     // "pending" | "processing" | "completed" | "failed"
article.title                 // string
article.summary               // string | null
article.original_url          // string | null
article.is_read               // boolean
article.reading_time_minutes  // number | null
article.color_id              // string | null (resolved to articleColor.hex_value)
article.categories            // array of { id, name }
article.tags                  // array of { id, name, color }
```

## Computed Values

```typescript
const SourceIcon = sourceIcons[article.source_type] || Globe;
const StatusIcon = statusIcons[article.processing_status];  // null if completed
const articleColor = colors?.find((c) => c.id === article.color_id);
const isProcessing = article.processing_status === "processing";
const isFailed = article.processing_status === "failed";
const isSelected = selectedArticleIds.has(article.id);
const summaryPreview = article.summary?.split("\n").find((line) => line.trim() && !line.startsWith("#"))?.slice(0, 200);
const externalLink = article.original_url ? article.original_url : `https://www.google.com/search?q=${encodeURIComponent(article.title || "")}`;
```

---

## GRID VIEW - Complete JSX Structure

### Lines 150-248: Grid View Return

```
Line 151-158: <Link> (root container)
├── Line 161-194: <div> (Header)
│   ├── Line 162-170: <div> (left side: icon + color dot)
│   │   ├── Line 163: <SourceIcon>
│   │   └── Line 164-169: <div> (color dot) [CONDITIONAL: articleColor]
│   └── Line 171-193: <div> (right side: status + checkbox)
│       ├── Line 172-180: <StatusIcon> [CONDITIONAL: StatusIcon exists]
│       └── Line 182-192: <button> (checkbox)
│           └── Line 191: <Check> [CONDITIONAL: isSelected]
├── Line 197-202: <div> (Title section)
│   ├── Line 198-200: <span> (unread dot) [CONDITIONAL: !article.is_read]
│   └── Line 201: <h3> (title)
├── Line 205-207: <p> (summary) [CONDITIONAL: summaryPreview]
├── Line 210-221: <div> (Categories & Tags)
│   ├── Lines 211-215: <Badge> for categories [LOOP: 0-1 items]
│   └── Lines 216-220: <Badge> for tags [LOOP: 0-2 items]
└── Line 224-246: <div> (Footer)
    ├── Line 225-232: <span> or <span/> (reading time) [CONDITIONAL]
    │   ├── Line 227: <Clock>
    │   └── Line 228: text "{minutes} min read"
    └── Line 233-245: <div> (right side: media badge + link)
        ├── Line 234: <MediaTypeBadge>
        └── Line 235-244: <a> (paperclip link)
```

### Grid View Classes - Element by Element

#### Root `<Link>` (lines 151-158)
```
ALWAYS:      "flex flex-col p-4 bg-dark-surface border rounded-lg transition-colors h-full"
IF selected: "border-article-blue bg-article-blue/5"
ELSE:        "border-dark-border hover:border-dark-hover hover:bg-dark-hover/50"
```

#### Header `<div>` (line 161)
```
"flex items-start justify-between gap-2 mb-3"
```

#### Header Left `<div>` (line 162)
```
"flex items-center gap-2"
```

#### SourceIcon (line 163)
```
"w-4 h-4 text-dark-muted"
```

#### Color Dot `<div>` (lines 165-168) - CONDITIONAL: articleColor
```
"w-2 h-2 rounded-full"
style: { backgroundColor: articleColor.hex_value }
```

#### Header Right `<div>` (line 171)
```
"flex items-center gap-2"
```

#### StatusIcon (lines 173-179) - CONDITIONAL: StatusIcon exists
```
ALWAYS:         "w-4 h-4"
IF isProcessing: "animate-spin text-article-blue"
IF isFailed:     "text-article-red"
```

#### Checkbox `<button>` (lines 183-189)
```
ALWAYS:      "w-5 h-5 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors"
IF selected: "bg-article-blue border-article-blue"
ELSE:        "border-dark-border hover:border-dark-muted"
```

#### Check Icon (line 191) - CONDITIONAL: isSelected
```
"w-3 h-3 text-white"
```

#### Title Section `<div>` (line 197)
```
"flex items-start gap-2 mb-2"
```

#### Unread Dot `<span>` (line 199) - CONDITIONAL: !article.is_read
```
"w-2 h-2 rounded-full bg-article-blue flex-shrink-0 mt-1.5"
title="Unread"
```

#### Title `<h3>` (line 201)
```
"font-medium text-white line-clamp-2"
```

#### Summary `<p>` (line 206) - CONDITIONAL: summaryPreview
```
"text-sm text-dark-muted line-clamp-3 mb-3 flex-1"
```

#### Tags Container `<div>` (line 210)
```
"flex flex-wrap gap-1.5 mt-auto"
```

#### Category Badge (lines 211-215) - LOOP: categories.slice(0, 1)
```
<Badge size="sm" color="#6B7280" variant="outline">
```

#### Tag Badge (lines 216-220) - LOOP: tags.slice(0, 2)
```
<Badge size="sm" color={tag.color || "#8B5CF6"}>
```

#### Footer `<div>` (line 224)
```
"mt-3 pt-3 border-t border-dark-border flex justify-between items-center"
```

#### Reading Time `<span>` (line 226) - CONDITIONAL: reading_time_minutes
```
"flex items-center gap-1 text-xs text-dark-muted"
```

#### Reading Time Clock Icon (line 227)
```
"w-3 h-3"
```

#### Reading Time Text (line 228)
```
"{reading_time_minutes} min read"
```

#### Empty Span (line 231) - CONDITIONAL: !reading_time_minutes
```
<span />  (no classes)
```

#### Footer Right `<div>` (line 233)
```
"flex items-center gap-2"
```

#### Paperclip Link `<a>` (lines 235-243)
```
"text-dark-muted hover:text-article-blue transition-colors"
href={externalLink}
target="_blank"
rel="noopener noreferrer"
title={article.original_url ? "Open source" : "Search on Google"}
content: 📎
```

---

## LIST VIEW - Complete JSX Structure

### Lines 59-146: List View Return

```
Line 61-68: <Link> (root container)
├── Line 71-76: <div> (color indicator) [CONDITIONAL: articleColor]
├── Line 79-106: <div> (Content wrapper)
│   └── Line 80-105: <div> (inner content)
│       ├── Line 81: <SourceIcon>
│       └── Line 82-104: <div> (text content)
│           ├── Line 83-88: <div> (title row)
│           │   ├── Line 84-86: <span> (unread dot) [CONDITIONAL: !is_read]
│           │   └── Line 87: <h3> (title)
│           ├── Line 89-91: <p> (summary) [CONDITIONAL: summaryPreview]
│           └── Line 92-103: <div> (tags)
│               ├── Lines 93-97: <Badge> categories [LOOP: 0-1]
│               └── Lines 98-102: <Badge> tags [LOOP: 0-3]
└── Line 109-144: <div> (Meta section)
    ├── Line 110-115: <span> (reading time) [CONDITIONAL]
    │   ├── Line 112: <Clock>
    │   └── Line 113: text
    ├── Line 116-120: <StatusIcon> [CONDITIONAL]
    ├── Line 121: <MediaTypeBadge>
    ├── Line 122-131: <a> (paperclip)
    └── Line 133-143: <button> (checkbox)
        └── Line 142: <Check> [CONDITIONAL: isSelected]
```

### List View Classes - Element by Element

#### Root `<Link>` (lines 62-68)
```
ALWAYS:      "flex items-start gap-4 p-4 bg-dark-surface border rounded-lg transition-colors"
IF selected: "border-article-blue bg-article-blue/5"
ELSE:        "border-dark-border hover:border-dark-hover hover:bg-dark-hover/50"
```

#### Color Indicator `<div>` (lines 72-75) - CONDITIONAL: articleColor
```
"w-1 self-stretch rounded-full flex-shrink-0"
style: { backgroundColor: articleColor.hex_value }
```

#### Content Wrapper `<div>` (line 79)
```
"flex-1 min-w-0"
```

#### Inner Content `<div>` (line 80)
```
"flex items-start gap-3"
```

#### SourceIcon (line 81)
```
"w-4 h-4 text-dark-muted mt-1 flex-shrink-0"
```

#### Text Content `<div>` (line 82)
```
"flex-1 min-w-0"
```

#### Title Row `<div>` (line 83)
```
"flex items-center gap-2"
```

#### Unread Dot `<span>` (line 85) - CONDITIONAL: !article.is_read
```
"w-2 h-2 rounded-full bg-article-blue flex-shrink-0"
title="Unread"
```

#### Title `<h3>` (line 87)
```
"font-medium text-white truncate"
```

#### Summary `<p>` (line 90) - CONDITIONAL: summaryPreview
```
"text-sm text-dark-muted mt-1 line-clamp-2"
```

#### Tags Container `<div>` (line 92)
```
"flex items-center gap-2 mt-2"
```

#### Category Badge (lines 93-97) - LOOP: categories.slice(0, 1)
```
<Badge size="sm" color="#6B7280" variant="outline">
```

#### Tag Badge (lines 98-102) - LOOP: tags.slice(0, 3)
```
<Badge size="sm" color={tag.color || "#8B5CF6"}>
```

#### Meta Section `<div>` (line 109)
```
"flex items-center gap-3 flex-shrink-0 text-sm text-dark-muted"
```

#### Reading Time `<span>` (line 111) - CONDITIONAL: reading_time_minutes
```
"flex items-center gap-1"
```

#### Reading Time Clock Icon (line 112)
```
"w-3.5 h-3.5"
```

#### Reading Time Text (line 113)
```
"{reading_time_minutes} min"
```

#### StatusIcon (lines 117-119) - CONDITIONAL: StatusIcon exists
```
ALWAYS:          "w-4 h-4"
IF isProcessing: "animate-spin"
IF isFailed:     "text-article-red"
```

#### Paperclip Link `<a>` (lines 122-130)
```
"hover:text-article-blue transition-colors"
href={externalLink}
target="_blank"
rel="noopener noreferrer"
title={article.original_url ? "Open source" : "Search on Google"}
content: 📎
```

#### Checkbox `<button>` (lines 134-140)
```
ALWAYS:      "w-5 h-5 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors"
IF selected: "bg-article-blue border-article-blue"
ELSE:        "border-dark-border hover:border-dark-muted"
```

#### Check Icon (line 142) - CONDITIONAL: isSelected
```
"w-3 h-3 text-white"
```

---

## Badge Component (Badge.tsx)

### Props
```typescript
children: ReactNode
color?: string           // hex color like "#8B5CF6"
variant?: "solid" | "outline"  // default: "solid"
size?: "sm" | "md"       // default: "sm"
className?: string
```

### Base Classes
```
"inline-flex items-center font-medium rounded-full"
```

### Size Classes
```
sm: "px-2 py-0.5 text-xs"
md: "px-2.5 py-1 text-sm"
```

### Variant Classes (when NO color)
```
solid:   "bg-dark-hover text-dark-text"
outline: "border border-dark-border text-dark-muted"
```

### When color IS provided (inline style)
```javascript
{
  backgroundColor: variant === "solid" ? `${color}20` : "transparent",
  color: color,
  borderColor: color
}
```

---

## MediaTypeBadge Component (MediaTypeBadge.tsx)

### Container Classes
```
"inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
+ config.bgColor
+ config.textColor
```

### Icon Classes
```
"w-3 h-3"
```

### Config by Type

| Type       | Label      | Icon          | bgColor           | textColor       |
|------------|------------|---------------|-------------------|-----------------|
| article    | Article    | FileText      | bg-gray-500/20    | text-gray-400   |
| paper      | Paper      | GraduationCap | bg-blue-500/20    | text-blue-400   |
| video      | Video      | PlayCircle    | bg-red-500/20     | text-red-400    |
| blog       | Blog       | PenLine       | bg-green-500/20   | text-green-400  |
| pdf        | PDF        | FileDown      | bg-orange-500/20  | text-orange-400 |
| newsletter | Newsletter | Mail          | bg-purple-500/20  | text-purple-400 |

---

## Key Differences: Grid vs List

| Aspect              | Grid View                                    | List View                                   |
|---------------------|----------------------------------------------|---------------------------------------------|
| Root layout         | `flex flex-col`                              | `flex items-start`                          |
| Color indicator     | Small dot (w-2 h-2) in header                | Vertical bar (w-1 self-stretch) on left     |
| Title               | `line-clamp-2`                               | `truncate`                                  |
| Summary             | `line-clamp-3 mb-3 flex-1`                   | `mt-1 line-clamp-2`                         |
| Tags shown          | 1 category + 2 tags                          | 1 category + 3 tags                         |
| Tags container      | `flex flex-wrap gap-1.5 mt-auto`             | `flex items-center gap-2 mt-2`              |
| Reading time text   | "{n} min read"                               | "{n} min"                                   |
| Reading time icon   | `w-3 h-3`                                    | `w-3.5 h-3.5`                               |
| Footer/Meta         | Separate footer div with border-t            | Inline meta div on right                    |
| Unread dot position | In title row with `mt-1.5`                   | In title row, no margin-top                 |
| Source icon         | `w-4 h-4 text-dark-muted` (no mt)            | `w-4 h-4 text-dark-muted mt-1 flex-shrink-0`|
