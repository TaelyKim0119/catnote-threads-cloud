"""Prepare or publish one Catnote news-and-question pair from a cloud runner."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from comic_scene import scene
from create_fact_card import render
from discover import find_sources
from draft import fact_card_spec, generate, news_text, question_text
from threads_api import ThreadsAPI
from token_store import TOKEN_FILE, load, maybe_refresh, save

ROOT = Path(__file__).resolve().parent
KST = ZoneInfo("Asia/Seoul")
CARD_DIR = ROOT / "cards"
STATE_DIR = ROOT / "state"


def git_save(message: str, paths: list[Path]) -> None:
    if not os.environ.get("GITHUB_REPOSITORY"):
        return
    args = [str(path.relative_to(ROOT)) for path in paths if path.exists()]
    if not args:
        return
    subprocess.run(["git", "add", "--", *args], cwd=ROOT, check=True)
    changed = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if changed.returncode == 0:
        return
    subprocess.run([
        "git", "-c", "user.name=catnote-bot", "-c", "user.email=catnote-bot@users.noreply.github.com",
        "commit", "-m", message,
    ], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=ROOT, check=True)


def state_file(now: datetime, slot: str) -> Path:
    return STATE_DIR / f"{now.date().isoformat()}-{slot}.json"


def public_card_url(card: Path) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo or card.parent != CARD_DIR:
        raise RuntimeError("Public GitHub repository is required for Threads images")
    return f"https://raw.githubusercontent.com/{repo}/main/cards/{card.name}"


def wait_for_public_card(card: Path) -> str:
    url = public_card_url(card)
    for attempt in range(10):
        response = requests.get(url, params={"v": int(time.time())}, timeout=15)
        if response.status_code == 200 and response.content == card.read_bytes():
            return url
        time.sleep(3)
    raise RuntimeError("Card is not publicly fetchable yet; nothing was posted")


def previous_leads() -> set[str]:
    values = set()
    for path in STATE_DIR.glob("*.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            if item.get("lead_url"):
                values.add(item["lead_url"])
        except (ValueError, OSError):
            continue
    return values


def prepare(now: datetime, slot: str, api_key: str, recent: list[dict]) -> tuple[Path, dict]:
    state_path = state_file(now, slot)
    if state_path.exists():
        return state_path, json.loads(state_path.read_text(encoding="utf-8"))
    recent_text = "\n".join(post.get("text", "") for post in recent)
    same_day_vendors = set()
    for previous in STATE_DIR.glob(f"{now.date().isoformat()}-*.json"):
        try:
            same_day_vendors.add(json.loads(previous.read_text(encoding="utf-8"))["vendor"])
        except (OSError, ValueError, KeyError):
            pass
    candidates = find_sources(now, previous_leads())
    candidates.sort(key=lambda source: source.lead.vendor in same_day_vendors)
    for source in candidates:
        if source.url in recent_text:
            continue
        try:
            draft = generate(source, api_key)
            body = news_text(draft, source)
            question = question_text(draft, source)
            if len(body) > 500 or len(question) > 500:
                continue
            stem = f"{now.date().isoformat()}-{slot}"
            comic = CARD_DIR / f"{stem}-comic.png"
            card = CARD_DIR / f"{stem}.png"
            scene(draft.prop, comic)
            render(fact_card_spec(draft, source, str(comic)), card)
            item = {
                "status": "prepared", "date": now.date().isoformat(), "slot": slot,
                "lead_url": source.lead.lead_url,
                "source_url": source.url, "vendor": source.lead.vendor,
                "news_text": body, "question_text": question,
                "card": card.name, "news_id": None, "question_id": None,
            }
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
            return state_path, item
        except (ValueError, requests.RequestException, KeyError) as exc:
            print(f"Candidate skipped: {type(exc).__name__}")
            continue
    raise RuntimeError("No current article passed official-source checks; nothing was posted")


def save_state(path: Path, item: dict) -> None:
    path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
    git_save(f"Record {item['date']} {item['slot']} {item['status']}", [path, TOKEN_FILE])


def run(slot: str, dry_run: bool) -> None:
    now = datetime.now(KST)
    if slot not in {"morning", "evening"}:
        raise ValueError("slot must be morning or evening")
    if not dry_run:
        allowed = (9 <= now.hour < 12) if slot == "morning" else (18 <= now.hour < 21)
        if not allowed:
            print("Outside the scheduled Seoul-time window; skipped")
            return
        if os.environ.get("CATNOTE_LIVE_ENABLED") != "true":
            print("Live posting is disabled; skipped")
            return

    api_key = os.environ.get("CATNOTE_GEMINI_FREE_KEY", "")
    if not api_key:
        raise RuntimeError("Missing Free Tier Gemini key; nothing was posted")
    api = None
    recent = []
    if not dry_run:
        token, refreshed_at = load()
        api = ThreadsAPI(token)
        identity = api.identity()
        if identity.get("username", "").lower() != "emilykim0503":
            raise RuntimeError("Threads token belongs to the wrong account")
        if not TOKEN_FILE.exists():
            save(token, refreshed_at)
            git_save("Store encrypted Threads token", [TOKEN_FILE])
        if maybe_refresh(api, refreshed_at):
            git_save("Rotate encrypted Threads token", [TOKEN_FILE])
        recent = api.recent(limit=100)
        today = api.today(now)
        if len(today) >= 4:
            print("Daily cap of four posts reached; skipped")
            return

    path, item = prepare(now, slot, api_key, recent)
    card = CARD_DIR / item["card"]
    if dry_run:
        print(json.dumps({"status": "dry_run", "source": item["source_url"],
                          "card": str(card), "news": item["news_text"],
                          "question": item["question_text"]}, ensure_ascii=False, indent=2))
        return

    assert api is not None
    comic = CARD_DIR / f"{now.date().isoformat()}-{slot}-comic.png"
    git_save(f"Prepare Catnote card {item['date']} {slot}", [card, comic, path])
    card_url = wait_for_public_card(card)
    for post in api.today(now):
        body = post.get("text", "")
        if item["source_url"] in body and "①" not in body:
            item["news_id"] = post["id"]
        if item["question_text"].splitlines()[0] in body:
            item["question_id"] = post["id"]

    if not item["news_id"]:
        if len(api.today(now)) >= 4:
            print("Daily cap reached before news post; skipped")
            return
        container = api.create_image(item["news_text"], card_url,
                                     "캣노트 AI·IT 뉴스 사실 카드와 고양이 만화")
        published = api.publish(container)
        item["news_id"] = published["id"]
        item["status"] = "news_published"
        save_state(path, item)

    if not item["question_id"]:
        if len(api.today(now)) >= 4:
            print("Daily cap reached before question post; skipped")
            return
        container = api.create_quote(item["question_text"], item["news_id"])
        published = api.publish(container)
        if not published.get("is_quote_post"):
            raise RuntimeError("Question published but quote attachment could not be verified")
        item["question_id"] = published["id"]
        item["status"] = "complete"
        save_state(path, item)
    print(json.dumps({"status": item["status"], "news_id": item["news_id"],
                      "question_id": item["question_id"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=["morning", "evening"], required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.slot, args.dry_run)
