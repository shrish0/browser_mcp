from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, HttpUrl


class BrowseRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    url: HttpUrl
    questions: Optional[List[str]] = None
    use_dynamic: bool = False


class BrowseResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    url: str
    title: Optional[str] = None
    headings: Optional[List[str]] = None
    paragraphs: Optional[List[str]] = None
    metadata: Optional[Dict[str, str]] = None
    ai_answers: Optional[Dict[str, str]] = None
    model_used: Optional[str] = None
    answer_models: Optional[Dict[str, str]] = None
    error: Optional[str] = None
