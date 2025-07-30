# --- Pydantic Models for Tool Inputs ---

class ParseEmailArgs(BaseModel):
    """Input model for the parse_email function."""
    email_content: str = Field(..., description="The full content of the email to be parsed.")

class RetrieveCalendarEventsArgs(BaseModel):
    """Input model for the retrieve_calendar_events function."""
    start_date: str = Field(..., description="The start date for retrieving calendar events in YYYY-MM-DD format.")
    end_date: str = Field(..., description="The end date for retrieving calendar events in YYYY-MM-DD format.")

class FindAvailableSlotsArgs(BaseModel):
    """Input model for the find_available_slots function."""
    start_date: str = Field(..., description="The start date for finding available slots in YYYY-MM-DD format.")
    end_date: str = Field(..., description="The end date for finding available slots in YYYY-MM-DD format.")
    duration_minutes: int = Field(..., description="The duration of the meeting in minutes.")
    attendee_emails: List[str] = Field(..., description="A list of email addresses for the meeting attendees. The attendees must be part of the known user list.")

# --- Pydantic Models for Tool Outputs ---

class ParseEmailOutput(BaseModel):
    """Output model for the parse_email function."""
    sender: str
    subject: str
    body: str
    inferred_attendees: List[str]
    parsed_at: str

class CalendarEvent(BaseModel):
    """Model for a single calendar event."""
    title: str
    start: str
    end: str

class RetrieveCalendarEventsOutput(BaseModel):
    """Output model for the retrieve_calendar_events function."""
    events: List[CalendarEvent] = []
    status: str | None = None
    error: str | None = None

class TimeSlot(BaseModel):
    """Model for a single available time slot."""
    start_time: str
    end_time: str

class FindAvailableSlotsOutput(BaseModel):
    """Output model for the find_available_slots function."""
    slots: List[TimeSlot] = []
    status: str | None = None
    error: str | None = None