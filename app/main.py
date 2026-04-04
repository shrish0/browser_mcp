import logging
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl

from ai_client import get_ai_client
from scraper import WebScraper
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


class BrowseRequest(BaseModel):
    url: HttpUrl
    questions: Optional[List[str]] = None
    use_dynamic: bool = False


class BrowseResponse(BaseModel):
    url: str
    title: Optional[str] = None
    headings: Optional[List[str]] = None
    paragraphs: Optional[List[str]] = None
    metadata: Optional[Dict[str, str]] = None
    ai_answers: Optional[Dict[str, str]] = None  # Mapping question -> answer
    model_used: Optional[str] = None  # Primary model used for paragraphs
    answer_models: Optional[Dict[str, str]] = None  # Mapping question -> model used
    error: Optional[str] = None


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
    try:
        logger.info(f"Step 1: Scraping webpage - {request.url}")
        result = web_scraper.scrape(str(request.url), request.use_dynamic)

        if result is None:
            logger.error(f"Failed to scrape {request.url}")
            raise HTTPException(status_code=500, detail="Failed to scrape webpage")

        if isinstance(result, dict) and result.get("requires_login"):
            return BrowseResponse(
                url=str(request.url),
                error="This site requires login so can't summarize it",
            )

        response_data = {
            "url": str(request.url),
            "title": result["title"],
            "headings": result["headings"],
            "paragraphs": result["paragraphs"],
            "metadata": result["metadata"],
        }

        # Summarize paragraphs if possible, else use raw paragraphs
        logger.info("Step 2: Preparing context for AI summarization")
        prepared_context = prepare_for_ai_summarization(result)
        logger.debug(
            "Step 2: Prepared context for AI summarization (length=%d chars, headings=%d, paragraphs=%d)",
            len(prepared_context),
            len(result.get("headings", [])) if isinstance(result, dict) else 0,
            len(result.get("paragraphs", [])) if isinstance(result, dict) else 0,
        )
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
                    return_model=True,  # We need a way to get the model used
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
                logger.warning("AI client not available, cannot answer questions")
                raise HTTPException(
                    status_code=400,
                    detail="AI features require OPENROUTER_API_KEY to be set in environment",
                )
            logger.info(
                f"Step 4: Answering {len(request.questions)} specific questions"
            )
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

    except ValueError as e:
        logger.warning(f"Invalid URL: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.info(f"FLOW FAILED: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
