"""AI-powered financial review using the Claude API.

Generates a brief narrative analysis of the user's financial data.
Requires an Anthropic API key in config.json ("anthropic_api_key").
Results are cached for 4 hours to avoid excessive API calls.
"""

import json
import time
from pathlib import Path

import requests

from . import atomic_write_json

_REVIEW_CACHE = Path(__file__).parent.parent / ".claude_review_cache.json"
_REVIEW_TTL = 4 * 3600  # 4 hours


def _load_cached_review():
    """Return cached review HTML if still fresh, else None."""
    try:
        if _REVIEW_CACHE.exists():
            cached = json.loads(_REVIEW_CACHE.read_text())
            if time.time() - cached.get("ts", 0) < _REVIEW_TTL:
                return cached["html"]
    except Exception:
        pass
    return None


def _save_review_cache(html):
    atomic_write_json(_REVIEW_CACHE, {"ts": time.time(), "html": html})


def _md_to_html(text):
    """Minimal Markdown-to-HTML: convert bullet lists and bold text."""
    lines = text.strip().split("\n")
    html_parts = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        # Detect bullet lines
        is_bullet = False
        content = stripped
        for prefix in ("- ", "• ", "* "):
            if stripped.startswith(prefix):
                content = stripped[len(prefix):]
                is_bullet = True
                break

        # Convert **bold** to <strong>
        import re
        content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)

        if is_bullet:
            if not in_list:
                html_parts.append('<ul class="review-list">')
                in_list = True
            html_parts.append(f"<li>{content}</li>")
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<p>{content}</p>")

    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def generate_financial_review(api_key, financial_summary):
    """Call Claude API to generate a brief financial narrative.

    Args:
        api_key: Anthropic API key.
        financial_summary: dict with keys like net_worth, income, spending,
            top_categories, goals_progress, over_budget, age_of_money.

    Returns:
        HTML string with the review, or None on failure.
    """
    if not api_key:
        return None

    # Check cache first
    cached = _load_cached_review()
    if cached:
        print("  Using cached Claude review (< 4h old)")
        return cached

    prompt = (
        "You are a concise personal finance advisor. Based on the data below, "
        "write a brief financial review (4-6 bullet points). Cover:\n"
        "- Overall financial health\n"
        "- Notable spending patterns\n"
        "- Savings goal progress\n"
        "- One actionable suggestion\n\n"
        "Be conversational and encouraging. Use **bold** for key figures.\n\n"
        f"Financial Data:\n{json.dumps(financial_summary, indent=2)}"
    )

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 600,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["content"][0]["text"]
        html = _md_to_html(text)
        _save_review_cache(html)
        return html
    except Exception as e:
        print(f"  Claude review failed: {e}")
        return None


def query_claude_financial(api_key, question, financial_summary):
    """Send a user question to Claude with financial context and return HTML.

    Unlike generate_financial_review, this is not cached — each question
    gets a fresh answer.
    """
    if not api_key or not question:
        return None

    prompt = (
        "You are a helpful personal finance assistant. The user has a question "
        "about their finances. Answer concisely (3-6 sentences). "
        "Use **bold** for key numbers or terms.\n\n"
        f"User's Financial Snapshot:\n{json.dumps(financial_summary, indent=2)}\n\n"
        f"Question: {question}"
    )

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 800,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["content"][0]["text"]
        return _md_to_html(text)
    except Exception as e:
        print(f"  Claude query failed: {e}")
        return None
