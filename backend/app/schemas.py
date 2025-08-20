# backend/app/schemas.py
import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class ExtractedLead(BaseModel):
    first_name: str = Field("N/A", alias="First Name")
    email: str = Field("N/A", alias="Email")
    phone: str = Field("N/A", alias="Phone")
    company: str = Field("N/A", alias="Company")
    roles_advertised: str = Field("N/A", alias="Roles Advertised")
    sector: str = Field("N/A", alias="Sector")
    employment_type: str = Field("N/A", alias="Employment Type")
    date_posted: str = Field("N/A", alias="Date Posted")
    entry_date: str = Field("N/A", alias="Entry Date")
    salary_info: str = Field("N/A", alias="Salary Info")
    location: str = Field("N/A", alias="Location")
    ad_url: str = Field("N/A", alias="Ad URL")
    skip: str = Field("N/A", alias="Skip")
    skip_reason: str = Field("N/A", alias="Skip Reason")

    # Computed fields
    qualified: str = "No"
    priority: int = 0
    dedupe_key: str = ""

    model_config = ConfigDict(
        populate_by_name=True # Allows using both field name and alias
    )

class Lead(BaseModel):
    id: int
    first_name: str
    email: str
    phone: str
    company: str
    roles_advertised: str
    sector: str
    employment_type: str
    date_posted: Optional[datetime.date] = None
    entry_date: Optional[datetime.date] = None
    salary_info: str
    location: str
    ad_url: str
    source_subject: str
    duplicate_flag: bool
    priority: int
    qualified: bool
    skip_reason: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

class IngestResponse(BaseModel):
    status: str
    reason: Optional[str] = None
    lead: Optional[Lead] = None
    data: Optional[ExtractedLead] = None

class MetricsResponse(BaseModel):
    total_leads: int = 0
    unique_leads: int = 0
    high_priority_leads: int = 0
    duplicates_found: int = 0
    contacts_found: int = 0

    model_config = ConfigDict(from_attributes=True)