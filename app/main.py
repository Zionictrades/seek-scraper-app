# backend/app/main.py

import os
import io
import csv
import logging
from datetime import datetime
from typing import Optional, Any, Dict, List
import urllib.parse
import sys
import asyncio
import subprocess
import logging
from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from supabase import create_client, Client
import openai

# --- Local modules ---
from .scraper import scrape_seek
from .llm_utils import process_lead_with_openai, get_openai_client  # your llm_utils should expose these
# If you still want to support email ingestion via the old extractor, keep this:
try:
    from app.extract import extract_lead  # optional, only used by /ingest
except Exception:
    extract_lead = None  # skip /ingest if not present

# -------------------- Logging --------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("zionic-api")

# -------------------- Env & App --------------------
load_dotenv()
app = FastAPI(title="Zionic Leads API")
logger = logging.getLogger("uvicorn.error")

# Ensure Playwright browsers are installed at startup (registered on the final `app`)
@app.on_event("startup")
async def ensure_playwright_browsers():
    try:
        logger.info("Ensuring Playwright browsers are installed...")
        subprocess.run(["python", "-m", "playwright", "install", "--with-deps"], check=True)
        logger.info("Playwright browsers installed or already present.")
    except Exception as e:
        logger.exception("Playwright install at startup failed (continuing): %s", e)

# -------------------- CORS --------------------
# Open CORS by default; tighten if needed via env
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",") if os.getenv("CORS_ORIGINS") else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- Supabase & OpenAI Providers --------------------
def get_db() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Supabase credentials are not configured (SUPABASE_URL / SUPABASE_KEY).")
    return create_client(url, key)

def get_openai_client_dep() -> openai.OpenAI:
    # Wrapper so we can use FastAPI Depends while reusing your util
    logger.info("Using REAL OpenAI client.")
    return get_openai_client()  # delegates to your llm_utils

# -------------------- Models --------------------
class Lead(BaseModel):
    id: int
    created_at: datetime
    company: Optional[str] = None
    roles_advertised: Optional[str] = None
    location: Optional[str] = None
    first_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    priority: Optional[int] = None
    duplicate_flag: Optional[bool] = Field(None, alias="duplicate_flag")
    salary_info: Optional[str] = None
    ad_url: Optional[str] = None
    qualified: Optional[bool] = None
    skip_reason: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True

class Metrics(BaseModel):
    total_leads: int
    unique_leads: int
    high_priority_leads: int
    duplicates_found: int

class ScrapeRequest(BaseModel):
    role: str = "Electrician"
    location: str = "Adelaide"
    pages: int = 1

class IngestPayload(BaseModel):
    subject: str
    from_addr: str
    email_received_iso: str
    body_markdown: str
    ad_url: Optional[str] = None

# -------------------- Health --------------------
@app.get("/health")
async def health():
    return {"status": "ok"}

# -------------------- Scrape → Process (OpenAI) → Store (Supabase) --------------------
@app.post("/scrape", summary="Scrape new leads from Seek, process with AI, and save to DB")
async def scrape_and_process_leads(
    request: ScrapeRequest,
    db: Client = Depends(get_db),
    oai: openai.OpenAI = Depends(get_openai_client_dep),
):
    """
    Pipeline:
    1) Scrape Seek ads
    2) Process each ad with OpenAI to extract/qualify
    3) Check duplicates by `dedupe_key`
    4) Insert new qualified leads into 'leads'
    """
    logger.info(f"Starting scrape for role='{request.role}' in location='{request.location}' pages={request.pages}")

    try:
        # scraped_jobs = scrape_seek(role=request.role, location=request.location, pages=request.pages)
        scraped_jobs = await scrape_seek(role=request.role, location=request.location, pages=request.pages)

        # Determine provider availability
        supabase_configured = bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"))
        openai_configured = bool(os.getenv("OPENAI_API_KEY"))

        # Case A: no Supabase AND no OpenAI -> return raw scraped jobs
        if not supabase_configured and not openai_configured:
            logger.info("Supabase and OpenAI not configured — returning scraped jobs.")
            return {"message": "Scraping finished (no DB/AI configured).", "jobs": scraped_jobs, "new_leads_count": len(scraped_jobs)}

        # Case B: SKIP_DB -> optionally process with OpenAI, but do not perform DB inserts
        if SKIP_DB:
            logger.info("SKIP_DB set — processing with OpenAI if available, skipping DB inserts.")
            if openai_configured:
                processed_jobs = []
                for job in scraped_jobs:
                    processed = process_lead_with_openai(oai, job.get("source_subject", ""), job.get("ad_url", ""))  # type: ignore
                    processed_jobs.append({**job, **processed})
                return {"message": "Scraping finished (SKIP_DB). Processed jobs returned.", "jobs": processed_jobs, "new_leads_count": len(processed_jobs)}
            else:
                return {"message": "Scraping finished (SKIP_DB) and OpenAI not configured. Returning raw scraped jobs.", "jobs": scraped_jobs, "new_leads_count": len(scraped_jobs)}

        # Case C: Supabase not configured but OpenAI is -> run AI processing and return results (no DB)
        if not supabase_configured and openai_configured:
            logger.info("Supabase not configured but OpenAI available — processing jobs and returning results (no DB).")
            processed_jobs = []
            for job in scraped_jobs:
                processed = process_lead_with_openai(oai, job.get("source_subject", ""), job.get("ad_url", ""))  # type: ignore
                processed_jobs.append({**job, **processed})
            return {"message": "Scraping finished (no DB). Processed jobs returned.", "jobs": processed_jobs, "new_leads_count": len(processed_jobs)}

        if not scraped_jobs:
            return {"message": "Scraping finished. No new jobs found.", "new_leads_count": 0}

        logger.info(f"Scraped {len(scraped_jobs)} jobs. Processing with OpenAI...")
        new_count = 0

        for job in scraped_jobs:
            # Your process_lead_with_openai should return a dict with keys matching DB columns
            processed = process_lead_with_openai(oai, job.get("source_subject", ""), job.get("ad_url", ""))  # type: ignore
            lead_record: Dict[str, Any] = {**job, **processed}

            # We expect a 'dedupe_key' to exist in processed/job data. If not, create a simple one.
            dedupe_key = lead_record.get("dedupe_key")
            if not dedupe_key:
                # Fallback dedupe: company + roles_advertised + ad_url
                dedupe_key = f"{lead_record.get('company','')}-{lead_record.get('roles_advertised','')}-{lead_record.get('ad_url','')}".lower()
                lead_record["dedupe_key"] = dedupe_key

            # Check for existing lead with the same dedupe_key where qualified = true
            existing = db.table("leads").select("id, duplicate_flag").eq("dedupe_key", dedupe_key).execute()
            if existing.data:
                # Mark duplicates on the existing record if not already
                row = existing.data[0]
                if not row.get("duplicate_flag"):
                    db.table("leads").update({"duplicate_flag": True}).eq("id", row["id"]).execute()
                logger.info(f"Duplicate lead skipped: {dedupe_key}")
                continue

            # Default fields
            lead_record.setdefault("duplicate_flag", False)
            lead_record.setdefault("qualified", True if str(lead_record.get("qualified", "Yes")).lower() in {"true", "yes", "1"} else False)
            lead_record.setdefault("skip_reason", "N/A" if lead_record["qualified"] else lead_record.get("skip_reason") or "unqualified")

            # Only insert qualified leads into the main table
            if not lead_record["qualified"]:
                logger.info(f"Skipping unqualified lead for company={lead_record.get('company')} reason={lead_record.get('skip_reason')}")
                continue

            insert_res = db.table("leads").insert(lead_record).execute()
            if insert_res.data:
                new_count += 1
                logger.info(f"Inserted lead: company={lead_record.get('company')} role={lead_record.get('roles_advertised')}")
            else:
                logger.error(f"Failed to insert lead for {lead_record.get('company')}: {insert_res}")

        return {"message": f"Scraping & processing complete. Added {new_count} new leads.", "new_leads_count": new_count}

    except Exception as e:
        logger.error("Error in /scrape", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# -------------------- Leads (filtered) --------------------
@app.get("/leads", response_model=List[Lead], summary="Get all qualified leads from the database")
def get_leads_from_db(
    role: Optional[str] = Query(None, description="Filter by role substring"),
    town: Optional[str] = Query(None, description="Filter by town (location substring)"),
    state: Optional[str] = Query(None, description="Filter by state (location substring)"),
    db: Client = Depends(get_db),
):
    try:
        q = db.table("leads").select("*").order("created_at", desc=True).limit(500)

        # Build ilike filters
        if role:
            q = q.ilike("roles_advertised", f"%{role}%")
        if town:
            q = q.ilike("location", f"%{town}%")
        if state:
            q = q.ilike("location", f"%{state}%")

        res = q.execute()
        return res.data or []
    except Exception as e:
        logger.error("Error fetching leads from DB", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch leads from database.")

# -------------------- Metrics --------------------
@app.get("/metrics", response_model=Metrics, summary="Get key metrics from the database")
def get_metrics_from_db(db: Client = Depends(get_db)):
    try:
        # Pull minimal fields for counts to reduce payload
        res = db.table("leads").select("id, priority, duplicate_flag", count="exact").execute()
        leads = res.data or []
        total = res.count or 0

        duplicates = sum(1 for l in leads if l.get("duplicate_flag"))
        unique_leads = total - duplicates
        high_priority = sum(1 for l in leads if (l.get("priority") is not None) and (int(l["priority"]) >= 4))

        return Metrics(
            total_leads=total,
            unique_leads=unique_leads,
            high_priority_leads=high_priority,
            duplicates_found=duplicates,
        )
    except Exception as e:
        logger.error("Error fetching metrics from DB", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch metrics from database.")

# -------------------- CSV Export --------------------
@app.get("/leads/export", summary="Export leads to CSV")
def export_leads_to_csv(db: Client = Depends(get_db)):
    try:
        res = db.table("leads").select("*").order("created_at", desc=True).execute()
        leads: List[Dict[str, Any]] = res.data or []

        if not leads:
            return Response(status_code=204)

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=leads[0].keys())
        writer.writeheader()
        writer.writerows(leads)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=zionic_leads_{datetime.now().date()}.csv"},
        )
    except Exception as e:
        logger.error("Error exporting leads to CSV", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to export leads.")

# -------------------- Optional: Email Ingest (uses your extractor) --------------------
@app.post("/ingest")
def ingest(p: IngestPayload, db: Client = Depends(get_db)):
    """
    Receives raw email data, extracts a lead with AI (your extract_lead),
    and stores a qualified row in Supabase. If you don't use email ingestion,
    you can remove this endpoint safely.
    """
    if extract_lead is None:
        raise HTTPException(status_code=501, detail="Email ingestion is not enabled in this build.")

    try:
        logger.info("Ingestion request received.")
        lead = extract_lead(
            subject=p.subject,
            from_addr=p.from_addr,
            email_received_iso=p.email_received_iso,
            body_markdown=p.body_markdown,
            ad_url=p.ad_url,
        )

        # Expect your extractor to return a pydantic model or dict-like object
        data = lead.model_dump() if hasattr(lead, "model_dump") else dict(lead)

        # --- Normalize dates: convert DD/MM/YYYY (from extractor) to ISO YYYY-MM-DD for Postgres ---
        def _ddmmyyyy_to_iso(val):
            if not val or val == "N/A":
                return None
            try:
                # extractor returns strings like "17/08/2025" — convert to ISO date
                dt = datetime.strptime(val, "%d/%m/%Y").date()
                return dt.isoformat()
            except Exception:
                return None

        # Apply conversion for fields that may be DD/MM/YYYY strings
        if "entry_date" in data:
            data["entry_date"] = _ddmmyyyy_to_iso(data.get("entry_date"))
        if "date_posted" in data:
            data["date_posted"] = _ddmmyyyy_to_iso(data.get("date_posted"))

        # Normalize flags
        qualified = str(data.get("qualified", "Yes")).lower() in {"true", "yes", "1"}
        data.setdefault("qualified", qualified)
        data.setdefault("duplicate_flag", False)
        data.setdefault("skip_reason", data.get("skip_reason") or ("N/A" if qualified else "unqualified"))

        # Ensure dedupe_key exists
        if not data.get("dedupe_key"):
            data["dedupe_key"] = f"{data.get('company','')}-{data.get('roles_advertised','')}-{data.get('ad_url','')}".lower()

        # De-dup check
        existing = db.table("leads").select("id, duplicate_flag").eq("dedupe_key", data["dedupe_key"]).execute()
        if existing.data:
            row = existing.data[0]
            if not row.get("duplicate_flag"):
                db.table("leads").update({"duplicate_flag": True}).eq("id", row["id"]).execute()
            return {"status": "duplicate", "lead_id": row["id"]}

        if not qualified:
            return {"status": "skipped", "reason": data.get("skip_reason", "unqualified"), "data": data}

        ins = db.table("leads").insert(data).execute()
        if not ins.data:
            raise HTTPException(status_code=500, detail="Insert failed.")
        return {"status": "stored", "lead": ins.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error during ingestion", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion error: {e}")

# -- Create a minimal leads table compatible with the inserted fields
# CREATE TABLE IF NOT EXISTS leads (
#   id serial PRIMARY KEY,
#   first_name TEXT,
#   email TEXT,
#   phone TEXT,
#   company TEXT,
#   roles_advertised TEXT,
#   sector TEXT,
#   employment_type TEXT,
#   date_posted DATE,
#   entry_date DATE,
#   salary_info TEXT,
#   location TEXT,
#   ad_url TEXT,
#   skip TEXT,
#   skip_reason TEXT,
#   source_subject TEXT,
#   dedupe_key TEXT,
#   duplicate_flag BOOLEAN DEFAULT FALSE,
#   priority INTEGER DEFAULT 0,
#   qualified BOOLEAN DEFAULT TRUE,
#   created_at TIMESTAMPTZ DEFAULT NOW()
# );

# Docker CMD removed  put start command in Dockerfile or Render settings
