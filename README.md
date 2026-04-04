# Browser MCP

A powerful web browsing and summarization service built with FastAPI, Playwright, and OpenRouter AI.

## 🚀 Features
- **Intelligent Scraping**: Supports both static and dynamic (JavaScript-heavy) content selection.
- **AI-Powered Summarization**: Automatically summarizes page content with fallback protection.
- **Multi-Question Answering**: Pose multiple questions about a page in a single request.
- **Model Mapping**: Custom payload and parsing logic for different AI models (e.g., Qwen).
- **Model Tracking**: Provides transparency by returning the specific model used for each answer.

## 🛠️ Stack
- **Framework**: FastAPI
- **Web Scraping**: Playwright, BeautifulSoup4
- **AI Interaction**: OpenAI SDK (via OpenRouter)
- **Settings Management**: Pydantic Settings

## 📂 File Structure
See [structure.md](./structure.md) for a detailed file map.

## ⚙️ Setup
1. Clone the repository.
2. Create a `.env` file in the `app/` folder based on `app/example.env`.
3. Install dependencies: `pip install -r requirements.txt`.
4. Run the server: `python -m uvicorn main:app` (inside `app/` folder).

## 🏷️ License
MIT
