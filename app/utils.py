import re
from typing import Dict, List
from bs4 import BeautifulSoup


def clean_text(text: str) -> str:
    """Normalize text by trimming whitespace and collapsing multiple spaces."""
    return re.sub(r'\s+', ' ', text.strip())


def extract_headings(soup: BeautifulSoup) -> List[str]:
    """Extract all H1, H2, H3 headings from the soup."""
    headings = []
    for tag in soup.find_all(['h1', 'h2', 'h3']):
        text = clean_text(tag.get_text())
        if text:
            headings.append(text)
    return headings


def extract_paragraphs(soup: BeautifulSoup, limit: int = 20) -> List[str]:
    """Extract main paragraph content, skipping nav/footer/header/aside, minimum 20 chars."""
    paragraphs = []
    for p in soup.find_all('p'):
        # Skip if in excluded elements
        if p.find_parent(['nav', 'footer', 'header', 'aside']):
            continue
        text = clean_text(p.get_text())
        if len(text) >= 20:
            paragraphs.append(text)
            if len(paragraphs) >= limit:
                break
    return paragraphs


def extract_metadata(soup: BeautifulSoup) -> Dict[str, str]:
    """Extract meta description and keywords."""
    metadata = {}
    # Description
    desc = soup.find('meta', attrs={'name': 'description'})
    if desc and desc.get('content'):
        metadata['description'] = clean_text(desc['content'])
    else:
        metadata['description'] = ''

    # Keywords
    keywords = soup.find('meta', attrs={'name': 'keywords'})
    if keywords and keywords.get('content'):
        metadata['keywords'] = clean_text(keywords['content'])
    else:
        metadata['keywords'] = ''

    return metadata


def prepare_for_ai_summarization(data: Dict) -> str:
    """Prepare content for AI summarization in a structured format."""
    title = data.get('title', '')
    headings = data.get('headings', [])
    paragraphs = data.get('paragraphs', [])

    formatted = f"Title: {title}\n\nHeadings:\n"
    for h in headings:
        formatted += f"- {h}\n"
    formatted += "\nContent:\n"
    for p in paragraphs:
        formatted += f"{p}\n\n"

    return formatted.strip()


def requires_login(data: Dict) -> bool:
    """Check if the scraped content indicates login is required."""
    title = data.get('title', '').lower()
    headings = ' '.join(data.get('headings', [])).lower()
    paragraphs = ' '.join(data.get('paragraphs', [])).lower()
    text = f"{title} {headings} {paragraphs}"
    login_keywords = ['login', 'sign in', 'sign-in', 'authenticate', 'log in', 'log-in', 'signin', 'login required', 'please log in']
    return any(keyword in text for keyword in login_keywords)