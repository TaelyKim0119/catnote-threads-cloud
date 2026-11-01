"""Make a Korean fact card and a linked, developer-oriented question from one source.

Only the free-tier Gemini model is called. The API key must belong to a
Google AI Studio project that is visibly marked Free and has no billing link.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import requests

from discover import Source

MODEL = "gemini-3.6-flash"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
LABELS = ["WHO", "WHEN", "WHERE", "WHAT", "WHY", "HOW"]
PROPS = {"screen", "chip", "phone", "robot", "lock", "globe", "satellite", "document"}


@dataclass(frozen=True)
class Draft:
    title: str
    highlight: str
    facts: list[list[str]]
    source_date: str
    post_text: str
    question: str
    option_one: str
    option_two: str
    question_context: str
    prop: str
    evidence: list[str]


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def generate(source: Source, api_key: str) -> Draft:
    prompt = f"""You are preparing a strictly factual Korean Threads news pair for software developers.
Use ONLY the official source below. GeekNews is a lead, not evidence. Do not invent dates,
availability, numbers, popularity, causes, or capabilities. If the article is not a concrete
announcement within the last 7 days, or its publication date cannot be established, return
{{"reject": "reason"}}. The date of the GeekNews item is not the announcement date.

Return a JSON object with exactly these fields:
- title: one or two short Korean lines, with [[...]] around the central subject/action phrases;
- highlight: a short ending that completes the title into one clear sentence;
- facts: six [label, Korean fact] pairs ordered WHO, WHEN, WHERE, WHAT, WHY, HOW;
  use '미공개' when an item is not stated in the source. Mark only central terms [[...]].
- source_date: source's actual announced/published date as YYYY.MM.DD;
- post_text: 2-3 short Korean sentences. First sentence plainly says who did what.
  State the announcement date and current availability. No interpretation or hype.
- question: a concrete work scenario about this news in 1-2 Korean sentences, ending in a question;
- option_one and option_two: realistic, distinct team choices, no colored emoji or leading numerals;
- question_context: one short factual Korean sentence giving verified date/scope;
- prop: one of screen, chip, phone, robot, lock, globe, satellite, document;
- evidence: 4 to 8 EXACT short verbatim phrases copied from the official source text
  that collectively support the date, title, scope, the WHO/WHAT/HOW, and question context.
No evidence phrase may come from GeekNews. Keep all quoted phrases under 20 words.

Official URL: {source.url}
Official page title: {source.title}
Official date metadata: {source.published_meta}
GeekNews lead title (discovery only): {source.lead.title}
Official source text:\n{source.text[:28000]}"""
    response = requests.post(
        ENDPOINT,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.15},
        },
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    text = "".join(
        part.get("text", "")
        for choice in payload.get("candidates", [])
        for part in choice.get("content", {}).get("parts", [])
    )
    data = json.loads(text)
    if "reject" in data:
        raise ValueError(f"Source rejected: {data['reject']}")
    draft = Draft(**{key: data[key] for key in Draft.__dataclass_fields__})
    validate(draft, source)
    return draft


def validate(draft: Draft, source: Source) -> None:
    if [row[0] for row in draft.facts] != LABELS:
        raise ValueError("Missing or unordered six facts")
    if any(len(row) != 2 or not row[1].strip() for row in draft.facts):
        raise ValueError("Empty fact")
    if draft.prop not in PROPS:
        raise ValueError("Unknown comic prop")
    if not re.fullmatch(r"20\d\d\.\d\d\.\d\d", draft.source_date):
        raise ValueError("Unverified announcement date format")
    raw_date = draft.source_date.replace(".", "-")
    compact_date = draft.source_date.replace(".", "")
    source_check = _normalized(source.published_meta + " " + source.text)
    if raw_date not in source_check and compact_date not in source_check and draft.source_date not in source_check:
        # Some original articles use 'November 1, 2026'; evidence must still
        # explicitly support the date, so this gate intentionally skips them.
        raise ValueError("Announcement date not found verbatim in source")
    if len(draft.evidence) < 4:
        raise ValueError("Too few source quotes")
    for quote in draft.evidence:
        if not quote or _normalized(quote) not in source_check:
            raise ValueError("Evidence quote not found in official source")
    if len(draft.title.splitlines()) > 2 or len(draft.highlight) > 40:
        raise ValueError("Card text too long")
    if any(len(value) > 55 for _, value in draft.facts):
        raise ValueError("Fact value too long")
    if not all((draft.question, draft.option_one, draft.option_two, draft.question_context)):
        raise ValueError("Incomplete question")
    if "①" in draft.option_one or "②" in draft.option_two:
        raise ValueError("Question options contain extra numbering")


def fact_card_spec(draft: Draft, source: Source, comic_panel: str) -> dict:
    return {
        "source": f"{draft.source_date}  ·  출처 {source.lead.vendor}",
        "title": draft.title,
        "highlight": draft.highlight,
        "facts": draft.facts,
        "comic_panel": comic_panel,
    }


def news_text(draft: Draft, source: Source) -> str:
    return f"{draft.post_text.strip()}\n\n원문: {source.url}"


def question_text(draft: Draft, source: Source) -> str:
    return (f"{draft.question.strip()}\n\n"
            f"① {draft.option_one.strip()}\n"
            f"② {draft.option_two.strip()}\n\n"
            f"{draft.question_context.strip()} 여러분 팀은 ①과 ② 중 어느 쪽을 택하시겠어요?\n\n"
            f"원문: {source.url}")
