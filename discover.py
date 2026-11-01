"""Find recent GeekNews leads and fetch their linked primary announcements.

The RSS feed is only a lead list: it has neither the vote ranking nor the
original URL. Never describe an item as popular based on this feed alone.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

FEED = "https://feeds.feedburner.com/geeknews-feed"
BING = "https://www.bing.com/search"
NS = {"a": "http://www.w3.org/2005/Atom"}
VENDORS = {
    "OpenAI": ("openai.com", "developers.openai.com"),
    "ChatGPT": ("openai.com", "developers.openai.com"),
    "구글": ("blog.google", "deepmind.google", "developers.googleblog.com"),
    "Google": ("blog.google", "deepmind.google", "developers.googleblog.com"),
    "Gemini": ("blog.google", "deepmind.google", "developers.googleblog.com"),
    "DeepMind": ("deepmind.google", "blog.google"),
    "Anthropic": ("anthropic.com",),
    "Claude": ("anthropic.com",),
    "Microsoft": ("blogs.microsoft.com", "microsoft.com"),
    "마이크로소프트": ("blogs.microsoft.com", "microsoft.com"),
    "Meta": ("about.fb.com", "ai.meta.com"),
    "메타": ("about.fb.com", "ai.meta.com"),
    "NVIDIA": ("nvidia.com", "developer.nvidia.com"),
    "엔비디아": ("nvidia.com", "developer.nvidia.com"),
    "Apple": ("apple.com",),
    "애플": ("apple.com",),
    "GitHub": ("github.blog", "github.com"),
}
OFFICIAL_FEEDS = (
    ("OpenAI", "https://openai.com/news/rss.xml", ("openai.com",)),
    ("GitHub", "https://github.blog/changelog/feed/", ("github.blog",)),
    ("Google", "https://blog.google/rss/", ("blog.google",)),
    ("Meta", "https://about.fb.com/news/feed/", ("about.fb.com",)),
    ("NVIDIA", "https://blogs.nvidia.com/feed/", ("blogs.nvidia.com",)),
    ("Apple", "https://www.apple.com/newsroom/rss-feed.rss", ("apple.com",)),
)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "CatnoteNewsBot/1.0 (public-source verification)"})


@dataclass(frozen=True)
class Lead:
    title: str
    lead_url: str
    published: datetime
    vendor: str
    official_hosts: tuple[str, ...]


@dataclass(frozen=True)
class Source:
    lead: Lead
    url: str
    title: str
    published_meta: str
    text: str


def leads(now: datetime, used_urls: set[str], max_age_days: int = 7) -> list[Lead]:
    response = SESSION.get(FEED, timeout=25)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    found = []
    for entry in root.findall("a:entry", NS):
        title = entry.findtext("a:title", "", NS).strip()
        link = entry.find("a:link", NS)
        url = link.attrib.get("href", "").split("&utm_")[0] if link is not None else ""
        date_text = entry.findtext("a:published", "", NS)
        try:
            published = datetime.fromisoformat(date_text)
        except ValueError:
            continue
        if not url or url in used_urls or published > now + timedelta(hours=1):
            continue
        if now - published > timedelta(days=max_age_days):
            continue
        vendor = next((name for name in VENDORS if name.lower() in title.lower()), None)
        if vendor:
            found.append(Lead(title, url, published, vendor, VENDORS[vendor]))
    return found


def is_official(url: str, hosts: tuple[str, ...]) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(host == h or host.endswith("." + h) for h in hosts)


def primary_urls(lead: Lead) -> list[str]:
    # Bing RSS is a discovery aid. Every candidate is fetched and verified below.
    query = f'{lead.vendor} {lead.title[:95]}'
    response = SESSION.get(BING, params={"format": "rss", "q": query}, timeout=25)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    urls = []
    for item in root.findall(".//item"):
        url = (item.findtext("link") or "").strip()
        if is_official(url, lead.official_hosts) and urlparse(url).path not in {"", "/"} and url not in urls:
            urls.append(url)
    return urls[:5]


def read_source(lead: Lead, url: str) -> Source | None:
    if not is_official(url, lead.official_hosts):
        return None
    response = SESSION.get(url, timeout=30, allow_redirects=True)
    response.raise_for_status()
    if not is_official(response.url, lead.official_hosts):
        return None
    if urlparse(response.url).path in {"", "/"}:
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "aside", "form"]):
        tag.decompose()
    title = (soup.title.get_text(" ", strip=True) if soup.title else "")[:200]
    meta = []
    for tag in soup.find_all("meta"):
        name = (tag.get("property") or tag.get("name") or "").lower()
        if name in {"article:published_time", "date", "pubdate", "datepublished", "og:published_time"}:
            meta.append(tag.get("content", ""))
    for tag in soup.find_all("time", datetime=True)[:3]:
        meta.append(tag.get("datetime", ""))
    if not meta and not lead.lead_url.startswith("https://news.hada.io/"):
        meta.append(lead.published.date().isoformat())
    if not meta:
        return None
    try:
        announced = datetime.fromisoformat(meta[0][:10]).date()
        if (datetime.now(timezone.utc).date() - announced).days > 7:
            return None
    except ValueError:
        return None
    if lead.lead_url.startswith("https://news.hada.io/"):
        tokens = [token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", lead.title)
                  if token.casefold() not in {lead.vendor.casefold(), "show", "news"}]
        if not tokens or not any(token in (title + " " + response.url).casefold() for token in tokens):
            return None
    body = soup.find("article") or soup.find("main") or soup.body
    text = re.sub(r"\s+", " ", body.get_text(" ", strip=True)) if body else ""
    if len(text) < 450:
        return None
    return Source(lead, response.url, title, " | ".join(meta), text[:40000])


def official_feed_leads(now: datetime, used_urls: set[str], max_age_days: int = 7) -> list[Lead]:
    found = []
    for vendor, feed_url, hosts in OFFICIAL_FEEDS:
        try:
            response = SESSION.get(feed_url, timeout=25)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                url = (item.findtext("link") or "").strip()
                pubdate = (item.findtext("pubDate") or "").strip()
                try:
                    published = parsedate_to_datetime(pubdate)
                except (TypeError, ValueError):
                    continue
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                if (url not in used_urls and is_official(url, hosts)
                        and now - timedelta(days=max_age_days) <= published <= now + timedelta(hours=1)):
                    found.append(Lead(title, url, published, vendor, hosts))
        except (requests.RequestException, ET.ParseError):
            continue
    return sorted(found, key=lambda item: item.published, reverse=True)


def find_sources(now: datetime, used_urls: set[str], limit: int = 15) -> list[Source]:
    result = []
    for lead in leads(now, used_urls):
        try:
            for url in primary_urls(lead):
                source = read_source(lead, url)
                if source:
                    result.append(source)
                    break
        except (requests.RequestException, ET.ParseError):
            continue
        if len(result) >= limit:
            break
    if len(result) < limit:
        for lead in official_feed_leads(now, used_urls):
            if any(lead.lead_url == existing.url for existing in result):
                continue
            try:
                source = read_source(lead, lead.lead_url)
                if source:
                    result.append(source)
            except requests.RequestException:
                continue
            if len(result) >= limit:
                break
    return result
