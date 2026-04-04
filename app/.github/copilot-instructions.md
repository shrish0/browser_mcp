# Global AI Development Rules

## Prime Directive
Minimize friction per unit of output. Every action must increase speed, reduce complexity, improve feedback loop.

## Execution Rules
- Use existing project setup; avoid unnecessary configuration changes
- Prefer small, incremental edits; keep changes minimal and testable
- Generate boilerplate fully, assist with business logic, be cautious with critical logic
- Follow: Generate → Modify → Verify
- If setup/debugging >120s → simplify or reset
- Prefer simple working solutions over overengineering

## Anti-Patterns
- Blindly trusting generated code
- Making large untested changes
- Adding dependencies without need
- Ignoring project structure
- Overcomplicating solutions

## Git Branching Rules
- **Never work on the `main` or `master` branch directly.**
- **Workflow**: If the current branch is `main` or `master`, the AI must **STOP** and ask the user to provide a name for a new feature branch (`feature/*`) to be created.
- Ensure every logical change is committed on its own branch and then merged.

---

# Browser MCP Server - AI Coding Guidelines

## Architecture Overview
This is a Model Context Protocol (MCP) server built with FastAPI that provides web scraping capabilities. The server extracts structured content from websites using both static and dynamic scraping methods.

**Key Components:**
- `main.py`: FastAPI application with `/browse` endpoint and health checks
- `scraper.py`: WebScraper class handling static (requests/BeautifulSoup) and dynamic (Playwright) scraping
- `utils.py`: Text processing utilities for content extraction and AI summarization

## Core Workflows
- **Run server**: `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
- **Install dependencies**: `pip install -r requirements.txt` then `playwright install`
- **Health check**: GET `/health` returns `{"status": "healthy"}`

## API Patterns
- **Browse endpoint**: POST `/browse` with `{"url": "https://example.com", "question": "optional query"}`
- **Response structure**: Includes `url`, `title`, `headings[]`, `paragraphs[]`, `metadata{}`, `ai_summary_text?`
- **Scraping strategy**: Try static first, fallback to dynamic Playwright if `use_dynamic=True` and static fails

## Code Conventions
- **Logging**: Use `logger.info()` for operations, `logger.error()` for failures
- **Error handling**: Raise `HTTPException` for client errors (400/500), log unexpected exceptions
- **Text processing**: Always use `utils.clean_text()` for normalization, `re.sub(r'\s+', ' ', text.strip())`
- **Content extraction**: Use `utils.extract_headings()`, `extract_paragraphs(limit=20)`, `extract_metadata()`
- **AI summarization**: Call `utils.prepare_for_ai_summarization(data)` when question provided, formats content as "Title: ...\nHeadings:\n- ...\nContent:\n..."

## Scraping Rules
- **Static scraping**: Remove `<script>` and `<style>` tags before parsing
- **Dynamic scraping**: Wait for `networkidle` then additional 2s timeout for content loading
- **Content filtering**: Skip paragraphs in `nav/footer/header/aside` elements, minimum 20 chars
- **Validation**: Check URL with `urlparse()`, require scheme and netloc

## Dependencies
- **Playwright**: Requires `playwright install` for browser automation
- **BeautifulSoup**: Use `lxml` parser for HTML parsing
- **Requests**: Custom User-Agent header for static scraping