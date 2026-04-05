import re
from typing import Dict, List
from bs4 import BeautifulSoup


def clean_text(text: str) -> str:
    """Normalize text by trimming whitespace and collapsing multiple spaces."""
    return re.sub(r"\s+", " ", text.strip())


def extract_headings(soup: BeautifulSoup) -> List[str]:
    """Extract all H1, H2, H3 headings from the soup."""
    headings = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = clean_text(tag.get_text())
        if text:
            headings.append(text)
    return headings


def extract_paragraphs(soup: BeautifulSoup, limit: int = 20) -> List[str]:
    """Extract main paragraph content, skipping nav/footer/header/aside, minimum 20 chars."""
    paragraphs = []
    for p in soup.find_all("p"):
        # Skip if in excluded elements
        if p.find_parent(["nav", "footer", "header", "aside"]):
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
    desc = soup.find("meta", attrs={"name": "description"})
    if desc and desc.get("content"):
        metadata["description"] = clean_text(desc["content"])
    else:
        metadata["description"] = ""

    # Keywords
    keywords = soup.find("meta", attrs={"name": "keywords"})
    if keywords and keywords.get("content"):
        metadata["keywords"] = clean_text(keywords["content"])
    else:
        metadata["keywords"] = ""

    return metadata


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    return clean_text(text)


def extract_interactive_elements(
    soup: BeautifulSoup,
) -> Dict[str, List[Dict[str, str]]]:
    """Extract input fields, buttons, and links for AI context."""
    interactive = {
        "inputs": [],
        "buttons": [],
        "links": [],
    }

    for form in soup.find_all("form"):
        form_id = form.get("id", "")
        form_name = form.get("name", "")
        form_action = form.get("action", "")
        for input_tag in form.find_all(["input", "textarea", "select"]):
            input_type = input_tag.name
            if input_tag.name == "input":
                input_type = input_tag.get("type", "text")
            label_text = ""
            if input_tag.get("id"):
                label = soup.find("label", attrs={"for": input_tag.get("id")})
                if label:
                    label_text = _normalize_text(label.get_text())
            if not label_text:
                parent_label = input_tag.find_parent("label")
                if parent_label:
                    label_text = _normalize_text(parent_label.get_text())

            # Get HTML context: the outer HTML of the input and its immediate parent
            parent = input_tag.parent if input_tag.parent else input_tag
            html_context = str(parent).strip()

            interactive["inputs"].append(
                {
                    "form_id": form_id,
                    "form_name": form_name,
                    "form_action": form_action,
                    "name": input_tag.get("name", ""),
                    "type": input_type,
                    "placeholder": input_tag.get("placeholder", ""),
                    "label": label_text,
                    "value": input_tag.get("value", ""),
                    "html_context": html_context,
                }
            )

    for button in soup.find_all("button"):
        # Get HTML context for button
        parent = button.parent if button.parent else button
        html_context = str(parent).strip()

        interactive["buttons"].append(
            {
                "type": button.get("type", "button"),
                "text": _normalize_text(button.get_text()),
                "html_context": html_context,
            }
        )

    for link in soup.find_all("a", href=True):
        # Get HTML context for link
        parent = link.parent if link.parent else link
        html_context = str(parent).strip()

        interactive["links"].append(
            {
                "href": link["href"],
                "text": _normalize_text(link.get_text()),
                "html_context": html_context,
            }
        )

    return interactive


def _word_count(text: str) -> int:
    return len(text.split())


def prepare_for_ai_summarization(data: Dict) -> str:
    """Prepare content for AI summarization in a structured format."""
    title = data.get("title", "")
    headings = data.get("headings", [])
    paragraphs = data.get("paragraphs", [])
    interactive = data.get("interactive_elements", {})
    raw_html = data.get("raw_html", "")

    body_text = "\n\n".join(paragraphs).strip()
    body_word_count = _word_count(body_text)

    formatted = f"Title: {title}\n\nHeadings:\n"
    for h in headings:
        formatted += f"- {h}\n"
    formatted += "\nContent:\n"
    for p in paragraphs:
        formatted += f"{p}\n\n"

    if interactive.get("inputs"):
        formatted += "Interactive input fields:\n"
        for field in interactive["inputs"]:
            formatted += (
                f"- name: {field['name']}, type: {field['type']}, label: {field['label']}, "
                f"placeholder: {field['placeholder']}, form_action: {field['form_action']}\n"
                f"  HTML context: {field['html_context']}\n"
            )
        formatted += "\n"

    if interactive.get("buttons"):
        formatted += "Buttons:\n"
        for button in interactive["buttons"]:
            formatted += f"- type: {button['type']}, text: {button['text']}\n"
            formatted += f"  HTML context: {button['html_context']}\n"
        formatted += "\n"

    if interactive.get("links"):
        formatted += "Links:\n"
        for link in interactive["links"]:
            formatted += f"- text: {link['text']}, href: {link['href']}\n"
            formatted += f"  HTML context: {link['html_context']}\n"
        formatted += "\n"

    if body_word_count < 250 and raw_html:
        formatted += (
            "The visible content is short. Include the raw HTML structure below to help answer questions "
            "about interactive elements and page navigation.\nRaw HTML:\n"
            f"{raw_html.strip()}"
        )

    return formatted.strip()


def requires_login(data: Dict) -> bool:
    """Check if the scraped content indicates login is required."""
    title = data.get("title", "").lower()
    headings = " ".join(data.get("headings", [])).lower()
    paragraphs = " ".join(data.get("paragraphs", [])).lower()
    metadata_desc = data.get("metadata", {}).get("description", "").lower()
    text = f"{title} {headings} {paragraphs} {metadata_desc}"

    login_keywords = [
        "login",
        "sign in",
        "sign-in",
        "authenticate",
        "log in",
        "log-in",
        "signin",
        "login required",
        "please log in",
        "unauthorized",
        "access denied",
        "forbidden",
        "permission denied",
    ]

    # Check if content is too minimal with no substantive paragraphs (sign of login page)
    if not data.get("paragraphs", []) and not data.get("headings", []):
        # If title mentions login or is a generic page with description only, likely protected
        if any(keyword in title for keyword in ["login", "sign", "auth"]):
            return True

    return any(keyword in text for keyword in login_keywords)
