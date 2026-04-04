# Project Structure

Follows Rule 17: File Awareness Rule.

## Root Directory
- `app/` → Main application source code.
- `requirements.txt` → Root-level dependencies.
- `.gitignore` → Excludes sensitive files like `.env`.
- `README.md` → Project overview and documentation.

## `app/` Directory
- `main.py` → FastAPI entry point. Defines `/browse` and `/health` endpoints. Handles request validation and coordination.
- `ai_client.py` → Singleton AI client (via OpenRouter). Implements model mappers for varied model payloads and parsing.
- `scraper.py` → `WebScraper` class for both static (requests) and dynamic (playwright) content extraction.
- `utils.py` → Shared text processing utilities (cleaning, heading/paragraph/metadata extraction).
- `setting.py` → Configuration management using Pydantic Settings. Loads `.env` file.
- `.env` → (Git-ignored) Local environment variables and secrets (API keys).
- `example.env` → Template for required environment variables.
- `requirements.txt` → App-specific dependencies.
- `.venv/` → Python virtual environment.

## `.github/`
- `copilot-instructions.md` → Custom coding standards and rules for AI assistants.

## Responsibilities
| File | Role |
| --- | --- |
| `main.py` | Orchestration & Routing |
| `ai_client.py` | AI Interaction & Model Mapping |
| `scraper.py` | Content Retrieval (Static/Dynamic) |
| `utils.py` | Text & Data Processing |
| `setting.py` | App Configuration |
