# backend/app/extract.py

import os
import json
import re
import datetime
import pytz
from typing import Optional
from openai import OpenAI

from .config import settings
from .schemas import ExtractedLead

# Load the system prompt from the text file
try:
    # Corrected the file path to be relative to the backend directory
    with open("app/prompt_system.txt", "r") as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    print("Warning: app/prompt_system.txt not found. Using empty system prompt.")
    SYSTEM_PROMPT = "You are a helpful assistant."


# Initialize the OpenAI client
# It will automatically use the OPENAI_API_KEY from the .env file
client = OpenAI(api_key=settings.openai_api_key)

# Define the timezone for all date operations
TZ = pytz.timezone("Australia/Adelaide")

def _today_au_str() -> str:
    """Returns the current date in Adelaide as a DD/MM/YYYY string."""
    return datetime.datetime.now(TZ).strftime("%d/%m/%Y")

def _safeguard_date(date_str: str) -> str:
    """Checks if a date string is valid, otherwise returns today's date."""
    try:
        datetime.datetime.strptime(date_str, "%d/%m/%Y")
        return date_str
    except (ValueError, TypeError):
        return _today_au_str()

def extract_lead(subject: str, from_addr: str, email_received_iso: str, body_markdown: str, ad_url: Optional[str]) -> ExtractedLead:
    """
    Calls the OpenAI API to extract structured data from raw email text.
    Also normalizes data and computes helper fields like priority and dedupe key.
    """
    # 1. Compose the user prompt with all available context
    # --- MOCKED RESPONSE FOR DEVELOPMENT ---
    # To test without making a real API call, we can return a hardcoded JSON response.
    # Remember to uncomment the real API call section below when your OpenAI account is ready.
    
    mock_json_response = """
    {
      "First Name": "N/A",
      "Email": "jobs@sparkyco.com.au",
      "Phone": "N/A",
      "Company": "Sparky Co",
      "Roles Advertised": "Qualified Electrician",
      "Sector": "Electrical",
      "Employment Type": "Full-time",
      "Date Posted": "17/08/2025",
      "Entry Date": "17/08/2025",
      "Salary Info": "Great salary package",
      "Location": "Melbourne",
      "Ad URL": "https://www.seek.com.au/job/12345678",
      "Skip": "No",
      "Skip Reason": "N/A"
    }
    """
    raw_content = mock_json_response

    # --- REAL API CALL (DISABLED) ---
    # When you're ready to use the real API, comment out the mock response above
    # and uncomment this section.
    # raw_content = _call_openai_api(subject, from_addr, email_received_iso, body_markdown, ad_url) # Keep this commented out for now

    # 3. Parse the JSON response safely
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError:
        # Fallback for cases where the model might not return perfect JSON
        print("Warning: Could not parse JSON directly. Attempting to extract from string.")
        match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
        else:
            raise ValueError("Failed to parse JSON from AI response.")

    # 4. Validate AI output and compute derived fields using the Pydantic model
    lead = ExtractedLead.model_validate(data)

    # Safeguard dates
    lead.entry_date = _safeguard_date(lead.entry_date)
    lead.date_posted = _safeguard_date(lead.date_posted)

    # Determine if the lead is qualified based on our business rules,
    # on top of the initial check done by the AI.
    is_qualified = (
        lead.skip == "No" and
        lead.sector == "Electrical" and
        lead.employment_type.lower().startswith("full")
    )
    if is_qualified:
        lead.qualified = "Yes"
    elif lead.skip == "No":
        # It's a direct employer, but doesn't match our more specific criteria.
        # We can provide a more specific reason for skipping.
        if lead.sector != "Electrical":
            lead.skip_reason = f"Not in Electrical sector (is {lead.sector})"
        elif not lead.employment_type.lower().startswith("full"):
            lead.skip_reason = f"Not a full-time role (is {lead.employment_type})"

    # Calculate priority score
    score = 0
    if lead.email != "N/A": score += 2
    if lead.phone != "N/A": score += 1
    if lead.salary_info != "N/A": score += 1
    lead.priority = score

    # Create a simple deduplication key from normalized company and role.
    company_norm = lead.company.lower().strip()
    roles_norm = lead.roles_advertised.lower().strip()
    lead.dedupe_key = f"{company_norm}|{roles_norm}"

    return lead

def _call_openai_api(subject: str, from_addr: str, email_received_iso: str, body_markdown: str, ad_url: Optional[str]) -> str:
    """Encapsulates the actual OpenAI API call."""
    user_prompt = f"""
    Subject: {subject}
    From: {from_addr}
    Email Date: {email_received_iso}
    Ad URL: {ad_url or 'N/A'}
    Body (markdown):
    {body_markdown}
    """

    response = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content
