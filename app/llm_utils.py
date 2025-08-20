import os
import logging
from typing import Any, Dict, Optional
import json
from pathlib import Path
from .config import settings

logger = logging.getLogger("zionic-llm-utils")


def get_openai_client():
    """
    Return a real OpenAI client (OpenAI class instance) when OPENAI_API_KEY is set.
    Returns None if the package or API key is not available (falls back to local stub).
    """
    try:
        from openai import OpenAI
    except Exception:
        logger.info("openai package not installed; using local stub processor.")
        return None

    api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "openai_api_key", None)
    if not api_key:
        logger.info("OPENAI_API_KEY not set — using local stub processor.")
        return None

    client = OpenAI(api_key=api_key)
    logger.info("OPENAI configured — real client available.")
    return client


def _simple_company_from_title(title: str) -> Optional[str]:
    # heuristics: split on common separators
    if not title:
        return None
    for sep in [" - ", " | ", " — ", "–", " —", " / "]:
        if sep in title:
            parts = [p.strip() for p in title.split(sep) if p.strip()]
            # if last part looks like company (short), use it
            if len(parts) >= 2:
                return parts[-1]
    # fallback: return None (many job titles won't include company)
    return None


def process_lead_with_openai(oai: Optional[object], source_subject: str, ad_url: str) -> Dict[str, Any]:
    """
    Deterministic local fallback to produce a lead-like dict when OpenAI isn't available.
    Keep keys compatible with your DB insert logic used in app.main.
    """
    # If a real OpenAI client is provided, call the model to extract structured fields.
    if oai:
        try:
            system_prompt = "You are a helpful assistant that extracts company and role from a short job title. Output JSON with keys Company, Roles Advertised, Location, Email, Phone, Salary Info, Qualified, Skip Reason."
            prompt = f"Title: {source_subject}\nAd URL: {ad_url}"
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            resp = oai.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = getattr(resp.choices[0].message, "content", None) or resp.choices[0].message.content
            try:
                parsed = json.loads(content) if isinstance(content, str) else content
            except Exception:
                parsed = {"Company": None, "Roles Advertised": source_subject}

            # Map model keys to DB-ready fields (keep compatibility with existing DB insert logic)
            company = parsed.get("Company") or _simple_company_from_title(source_subject)
            roles_advertised = parsed.get("Roles Advertised") or source_subject or "N/A"
            location = parsed.get("Location")
            email = parsed.get("Email")
            phone = parsed.get("Phone")
            salary_info = parsed.get("Salary Info")
            qualified = parsed.get("Qualified", True)
            skip_reason = parsed.get("Skip Reason", "N/A" if qualified else "unqualified")
            dedupe_key = (ad_url or source_subject).lower()
            priority = 2
            if any(k in (roles_advertised or "").lower() for k in ("senior", "lead", "manager")):
                priority = 4

            return {
                "company": company,
                "roles_advertised": roles_advertised,
                "location": location,
                "first_name": None,
                "email": email,
                "phone": phone,
                "priority": priority,
                "duplicate_flag": False,
                "salary_info": salary_info,
                "qualified": qualified,
                "skip_reason": skip_reason,
                "dedupe_key": dedupe_key,
            }
        except Exception as e:
            logger.exception("OpenAI call failed, falling back to deterministic processor.")

    # Basic deterministic fallback (no OpenAI available or model failed)
    title = (source_subject or "").strip()
    ad_url_norm = (ad_url or "").strip()
    dedupe_key = ad_url_norm.lower() if ad_url_norm else f"{title}".lower()

    company = _simple_company_from_title(title)
    roles_advertised = title or "N/A"

    # Simple heuristic qualification: mark as qualified for dev / local testing
    qualified = True
    skip_reason = "N/A" if qualified else "unqualified"

    # Priority heuristic: if title contains "senior" or "lead" bump priority
    priority = 2
    if any(k in title.lower() for k in ("senior", "lead", "manager")):
        priority = 4

    result = {
        "company": company,
        "roles_advertised": roles_advertised,
        "location": None,
        "first_name": None,
        "email": None,
        "phone": None,
        "priority": priority,
        "duplicate_flag": False,
        "salary_info": None,
        "qualified": qualified,
        "skip_reason": skip_reason,
        "dedupe_key": dedupe_key,
    }

    # If an actual OpenAI client is provided and you want to use it later,
    # you can extend this function to call it and parse a response. For now
    # we return the deterministic result so local dev works without keys.
    return result

