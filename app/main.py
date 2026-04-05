import logging
from typing import Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

from ai_client import get_ai_client
from exceptions import ScraperError
from scraper import WebScraper
from schemas import BrowseRequest, BrowseResponse
from setting import get_settings
from utils import prepare_for_ai_summarization

settings = get_settings()

# Configure logging
log_level = getattr(logging, settings.LOG_LEVEL.upper(), settings.LOG_LEVEL.upper())
logging.basicConfig(
    level=log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, version="1.0.0", debug=settings.DEBUG)

web_scraper = WebScraper()

# Initialize AI client (singleton) at startup - may be None if API key not set
ai_client = get_ai_client()


# Global exception handler
@app.exception_handler(ScraperError)
async def scraper_exception_handler(request: Request, exc: ScraperError):
    """Handle scraper exceptions with statuscode and error_message."""
    logger.warning("Scraper exception for %s: %s", request.url, exc.error_message)
    return JSONResponse(
        status_code=exc.status_code or 400,
        content={
            "statuscode": exc.status_code,
            "error_message": exc.error_message,
            "details": exc.details,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions globally and return error details."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "statuscode": 500,
            "error_message": "Internal server error",
            "details": {"reason": type(exc).__name__},
        },
    )


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/", include_in_schema=False)
def root_redirect():
    """Redirect the root path to API docs."""
    return RedirectResponse(url="/docs")


@app.post("/browse", response_model=BrowseResponse)
def browse_webpage(request: BrowseRequest):
    """Browse a webpage and extract structured content."""
    logger.info(f"Step 1: Scraping webpage - {request.url}")
    result = web_scraper.scrape(str(request.url), request.use_dynamic)

    if result is None:
        logger.error(f"Failed to scrape {request.url}")
        raise ScraperError(
            error_message="Failed to scrape webpage",
            status_code=502,
            details={"url": str(request.url)},
        )

    response_data = {
        "url": str(request.url),
        "title": result["title"],
        "headings": result["headings"],
        "paragraphs": result["paragraphs"],
        "metadata": result["metadata"],
    }

    # Summarize paragraphs if possible
    logger.info("Step 2: Preparing context for AI summarization")
    prepared_context = prepare_for_ai_summarization(result)
    try:
        if ai_client is None:
            logger.warning("AI client not available, using raw paragraphs")
            response_data["paragraphs"] = result["paragraphs"]
        else:
            logger.info("Step 3: Generating AI summary for paragraphs")
            summary_data = ai_client.get_summary(
                question="Summarize the main content of this webpage concisely.",
                context=prepared_context,
                max_tokens=300,
                return_model=True,
            )
            if isinstance(summary_data, tuple):
                summary, model = summary_data
            else:
                summary, model = summary_data, None

            if summary and summary != "AI summarization failed":
                response_data["paragraphs"] = [summary]
                response_data["model_used"] = model
                logger.info(
                    "Successfully summarized paragraphs with AI using %s", model
                )
            else:
                response_data["paragraphs"] = result["paragraphs"]
                logger.warning("AI summary failed, using raw paragraphs")
    except Exception:
        logger.exception(
            "AI paragraph summarization failed, falling back to raw paragraphs"
        )
        response_data["paragraphs"] = result["paragraphs"]

    # Handle specific questions if provided
    if request.questions:
        if ai_client is None:
            raise ValueError(
                "AI features require OPENROUTER_API_KEY to be set in environment"
            )

        logger.info(f"Step 4: Answering {len(request.questions)} specific questions")
        response_data["ai_answers"] = {}
        response_data["answer_models"] = {}
        answers, model_map = ai_client.answer_questions(
            request.questions,
            prepared_context,
            max_tokens=500,
            batch_size=10,
            delay_seconds=0.3,
        )
        for entry in answers:
            response_data["ai_answers"][entry["question"]] = entry["answer"]
            response_data["answer_models"][entry["question"]] = model_map.get(
                entry["question"], "none"
            )

    return BrowseResponse(**response_data)
