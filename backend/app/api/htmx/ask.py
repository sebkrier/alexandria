from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.article import Article, ProcessingStatus
from app.models.user import User
from app.utils.auth import get_current_user

from .utils import fetch_sidebar_data, templates

router = APIRouter()

@router.get("/ask", response_class=HTMLResponse)
async def ask_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chat page for asking questions about your library."""
    # Fetch sidebar data
    sidebar_data = await fetch_sidebar_data(db, current_user.id)

    # Example questions to show in empty state
    example_questions = [
        "What are the main topics covered in my articles?",
        "Summarize what I've saved about machine learning",
        "What do my articles say about productivity?",
        "How many articles do I have in each category?",
    ]

    return templates.TemplateResponse(
        request=request,
        name="pages/ask.html",
        context={
            "current_path": "/app/ask",
            "example_questions": example_questions,
            **sidebar_data,
        },
    )


@router.post("/ask/query")
async def ask_query(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Handle a question about the user's library with streaming response."""
    import html
    import logging
    import re
    import uuid

    from sqlalchemy import func as sqla_func

    from app.ai.embeddings import generate_query_embedding
    from app.ai.factory import get_default_provider
    from app.ai.prompts import truncate_text

    logger = logging.getLogger(__name__)

    form = await request.form()
    question = form.get("question", "").strip()

    if not question:
        return HTMLResponse(
            templates.get_template("components/toast.html").render(
                toast_type="error",
                toast_message="Please enter a question",
            )
        )

    message_id = str(uuid.uuid4())[:8]

    # Render user's question
    user_message_html = templates.get_template("partials/chat_message_user.html").render(
        message=question
    )

    async def generate_response():
        """Generator that yields HTML chunks for streaming."""
        # First, send the user message
        yield user_message_html

        try:
            # Get AI provider
            provider = await get_default_provider(db, current_user.id)
            if not provider:
                yield templates.get_template("partials/chat_message_assistant.html").render(
                    message_id=message_id,
                    content="",
                    sources=[],
                    is_streaming=False,
                    error="No AI provider configured. Please add one in Settings.",
                )
                return

            # Show typing indicator while searching
            yield f"""<div class="flex justify-start mb-4" id="message-{message_id}">
                <div class="max-w-[80%]">
                    <div class="flex items-start gap-3">
                        <div class="w-8 h-8 rounded-full bg-article-blue/10 flex items-center justify-center flex-shrink-0">
                            <svg class="w-4 h-4 text-article-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>
                            </svg>
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="bg-dark-surface border border-dark-border rounded-2xl rounded-tl-md px-4 py-3">
                                <div id="content-{message_id}" class="chat-prose text-dark-text text-sm">
                                    <div class="flex items-center gap-1">
                                        <div class="w-2 h-2 bg-article-blue rounded-full animate-pulse"></div>
                                        <div class="w-2 h-2 bg-article-blue rounded-full animate-pulse" style="animation-delay: 0.2s"></div>
                                        <div class="w-2 h-2 bg-article-blue rounded-full animate-pulse" style="animation-delay: 0.4s"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>"""

            # Perform hybrid search
            semantic_results = []
            keyword_results = []

            # Semantic Search
            has_embeddings = hasattr(Article, "embedding")
            if has_embeddings:
                try:
                    query_embedding = generate_query_embedding(question)
                    if query_embedding:
                        distance = Article.embedding.cosine_distance(query_embedding)
                        semantic_query = (
                            select(Article, distance.label("distance"))
                            .where(Article.user_id == current_user.id)
                            .where(Article.processing_status == ProcessingStatus.COMPLETED)
                            .where(Article.embedding.isnot(None))
                            .order_by(distance)
                            .limit(10)
                        )
                        result = await db.execute(semantic_query)
                        semantic_results = [(row[0], row[1]) for row in result.all()]
                except Exception as e:
                    logger.warning(f"Semantic search failed: {e}")

            # Keyword Search
            try:
                search_words = question.lower().split()[:10]
                valid_words = [w for w in search_words if len(w) >= 3]
                conditions = []

                for word in valid_words[:5]:
                    conditions.append(Article.title.ilike(f"%{word}%"))

                ts_query = sqla_func.plainto_tsquery("english", question)
                conditions.append(Article.search_vector.op("@@")(ts_query))

                if conditions:
                    ts_rank = sqla_func.ts_rank(Article.search_vector, ts_query)
                    keyword_query = (
                        select(Article, ts_rank.label("rank"))
                        .where(Article.user_id == current_user.id)
                        .where(Article.processing_status == ProcessingStatus.COMPLETED)
                        .where(or_(*conditions))
                        .order_by(ts_rank.desc())
                        .limit(10)
                    )
                    result = await db.execute(keyword_query)
                    keyword_results = [(row[0], row[1]) for row in result.all()]
            except Exception as e:
                logger.warning(f"Keyword search failed: {e}")

            # Merge Results
            article_scores = {}
            for article, distance in semantic_results:
                article_id = str(article.id)
                semantic_score = max(0, 1 - distance)
                article_scores[article_id] = article_scores.get(article_id, 0) + semantic_score

            max_rank = max((r for _, r in keyword_results), default=1) or 1
            for article, rank in keyword_results:
                article_id = str(article.id)
                keyword_score = rank / max_rank if max_rank > 0 else 0
                article_scores[article_id] = article_scores.get(article_id, 0) + keyword_score

            all_articles = {str(a.id): a for a, _ in semantic_results + keyword_results}
            sorted_ids = sorted(
                article_scores.keys(), key=lambda x: article_scores[x], reverse=True
            )

            merged_articles = []
            seen_ids = set()
            for article_id in sorted_ids[:10]:
                if article_id not in seen_ids:
                    seen_ids.add(article_id)
                    merged_articles.append(all_articles[article_id])

            # Fallback if no results
            if not merged_articles:
                query = (
                    select(Article)
                    .where(Article.user_id == current_user.id)
                    .where(Article.processing_status == ProcessingStatus.COMPLETED)
                    .order_by(Article.created_at.desc())
                    .limit(5)
                )
                result = await db.execute(query)
                merged_articles = list(result.scalars().all())

            if not merged_articles:
                # Replace typing indicator with error message
                yield f"""<script>document.getElementById('message-{message_id}').outerHTML = `
                    {
                    templates.get_template("partials/chat_message_assistant.html")
                    .render(
                        message_id=message_id,
                        content="You don't have any processed articles yet. Add some articles and wait for them to be processed.",
                        sources=[],
                        is_streaming=False,
                        error=None,
                    )
                    .replace("`", "\\`")
                    .replace("${", "\\${")
                }`;</script>"""
                return

            # Build context
            context_parts = []
            sources = []
            for article in merged_articles:
                article_context = f"### {article.title}\n\n"
                if article.summary:
                    article_context += f"**Summary:**\n{article.summary}\n\n"
                if article.extracted_text:
                    excerpt = truncate_text(article.extracted_text, 2000)
                    article_context += f"**Content excerpt:**\n{excerpt}\n"
                context_parts.append(article_context)
                sources.append({"id": str(article.id), "title": article.title})

            context = "\n\n---\n\n".join(context_parts)

            # Stream AI response
            full_response = ""
            async for chunk in provider.answer_question_stream(question=question, context=context):
                full_response += chunk
                # Escape the chunk for safe HTML/JS insertion
                escaped_chunk = html.escape(chunk).replace("\n", "\\n").replace("\r", "\\r")
                # Update the content div with the accumulated response
                yield f'''<script>
                    (function() {{
                        var el = document.getElementById('content-{message_id}');
                        if (el) {{
                            var current = el.getAttribute('data-raw') || '';
                            current += "{escaped_chunk}";
                            el.setAttribute('data-raw', current);
                            el.innerHTML = current.replace(/\\n/g, '<br>');
                        }}
                    }})();
                </script>'''

            # Convert final markdown to HTML
            html_answer = full_response
            html_answer = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_answer)
            html_answer = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html_answer)
            html_answer = re.sub(
                r"```(\w*)\n(.*?)```", r"<pre><code>\2</code></pre>", html_answer, flags=re.DOTALL
            )
            html_answer = re.sub(r"`(.+?)`", r"<code>\1</code>", html_answer)
            html_answer = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html_answer, flags=re.MULTILINE)
            html_answer = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html_answer, flags=re.MULTILINE)
            html_answer = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html_answer, flags=re.MULTILINE)
            html_answer = re.sub(r"^- (.+)$", r"<li>\1</li>", html_answer, flags=re.MULTILINE)
            html_answer = re.sub(r"(<li>.*</li>\n?)+", r"<ul>\g<0></ul>", html_answer)
            html_answer = re.sub(r"\n\n", "</p><p>", html_answer)
            html_answer = f"<p>{html_answer}</p>"
            html_answer = re.sub(r"<p>\s*</p>", "", html_answer)

            # Replace entire message with final formatted version including sources
            final_html = templates.get_template("partials/chat_message_assistant.html").render(
                message_id=message_id,
                content=html_answer,
                sources=sources[:5],
                is_streaming=False,
                error=None,
            )
            # Escape for JS string
            final_html_escaped = (
                final_html.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
            )
            yield f"""<script>document.getElementById('message-{message_id}').outerHTML = `{final_html_escaped}`;</script>"""

        except Exception as e:
            logger.error(f"Ask query failed: {e}")
            error_html = templates.get_template("partials/chat_message_assistant.html").render(
                message_id=message_id,
                content="",
                sources=[],
                is_streaming=False,
                error=f"Sorry, something went wrong: {str(e)[:100]}",
            )
            error_html_escaped = (
                error_html.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
            )
            yield f"""<script>document.getElementById('message-{message_id}').outerHTML = `{error_html_escaped}`;</script>"""

    return StreamingResponse(
        generate_response(),
        media_type="text/html",
    )
