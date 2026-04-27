"""Scraping ligero de webs públicas: emails, teléfonos, RRSS, meta tags."""
from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:(?:\+|00)\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}")
SOCIAL_DOMAINS = {
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "linkedin.com": "linkedin",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "tiktok.com": "tiktok",
    "youtube.com": "youtube",
    "pinterest.com": "pinterest",
}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 VibeMarketingBot/1.0"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}


def fetch(url: str, *, timeout: float = 10.0) -> tuple[int, str]:
    if not url:
        return 0, ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        with httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=timeout) as c:
            r = c.get(url)
            return r.status_code, r.text
    except Exception:
        return 0, ""


def extract_contacts(html: str, base_url: str | None = None) -> dict[str, Any]:
    soup = BeautifulSoup(html or "", "lxml")
    text = soup.get_text(" ", strip=True)
    emails = sorted(set(m.group(0) for m in EMAIL_RE.finditer(text)))
    phones_raw = sorted(set(m.group(0).strip() for m in PHONE_RE.finditer(text)))
    # filtra ruido (números muy cortos / códigos)
    phones = [p for p in phones_raw if sum(c.isdigit() for c in p) >= 8][:5]

    socials: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        for dom, name in SOCIAL_DOMAINS.items():
            if dom in href and name not in socials:
                socials[name] = href
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    descs = soup.find_all("meta", attrs={"name": "description"}) + soup.find_all(
        "meta", attrs={"property": "og:description"}
    )
    description = ""
    for d in descs:
        v = d.get("content")
        if v:
            description = v.strip()
            break
    h1 = (soup.find("h1").get_text(strip=True) if soup.find("h1") else "")
    return {
        "title": title,
        "description": description,
        "h1": h1,
        "emails": emails[:5],
        "phones": phones,
        "socials": socials,
        "text_excerpt": text[:4000],
    }


def basic_seo_audit(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html or "", "lxml")
    issues: list[str] = []
    score = 100
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    if not title:
        issues.append("Falta etiqueta <title>")
        score -= 15
    elif len(title) < 20 or len(title) > 70:
        issues.append(f"Título de longitud subóptima ({len(title)} chars; ideal 30-60)")
        score -= 5
    desc_tag = soup.find("meta", attrs={"name": "description"})
    desc = (desc_tag.get("content") or "").strip() if desc_tag else ""
    if not desc:
        issues.append("Falta meta description")
        score -= 10
    elif len(desc) < 70 or len(desc) > 170:
        issues.append(f"Meta description de longitud subóptima ({len(desc)} chars)")
        score -= 5
    if not soup.find("h1"):
        issues.append("Falta H1")
        score -= 10
    imgs = soup.find_all("img")
    no_alt = [i for i in imgs if not i.get("alt")]
    if imgs and len(no_alt) / max(len(imgs), 1) > 0.3:
        issues.append(f"{len(no_alt)}/{len(imgs)} imágenes sin atributo alt")
        score -= 8
    if not soup.find("meta", attrs={"property": "og:title"}):
        issues.append("Faltan etiquetas Open Graph (og:title)")
        score -= 5
    if not soup.find("link", attrs={"rel": "canonical"}):
        issues.append("Falta link canonical")
        score -= 4
    if not soup.find("html", attrs={"lang": True}):
        issues.append("Falta atributo lang en <html>")
        score -= 3
    return {
        "score": max(score, 0),
        "title": title,
        "description": desc,
        "h1_count": len(soup.find_all("h1")),
        "img_count": len(imgs),
        "img_missing_alt": len(no_alt),
        "issues": issues,
    }
