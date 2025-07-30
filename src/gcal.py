# --- Google Calendar Imports ---
import os
from typing import Any, Dict, List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel, Field

# --- Google Calendar Authentication for Multiple Users ---

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

def authenticate_google_calendar(user_id: str):
    """
    Handles user authentication for a specific user via their token.
    Tokens are stored in the 'Keys/' directory.
    Returns a service object to interact with the API.
    """
    creds = None
    token_path = os.path.join("Keys", f"{user_id}.token.json")
    os.makedirs("Keys", exist_ok=True)

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print(f"Refreshing token for {user_id}...")
            creds.refresh(Request())
        else:
            print(f"No valid token found for {user_id}. Starting authentication flow...")
            if not os.path.exists("credentials.json"):
                print("Error: credentials.json not found. Please download it from your Google Cloud project.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(token_path, "w") as token:
            token.write(creds.to_json())
        print(f"Token for {user_id} stored at {token_path}")

    try:
        service = build("calendar", "v3", credentials=creds)
        return service
    except HttpError as error:
        print(f"An error occurred during service build: {error}")
        return None

# --- Tool Functions (Updated to use Output Models) ---

def parse_email(args: ParseEmailArgs, user_map: Dict[str, str]) -> ParseEmailOutput:
    """
    Parses the content of an email to extract key information, including attendees.
    Infers attendees by looking for known user IDs or emails in the email body.
    """
    print(f"Parsing email to infer attendees: {args.email_content[:50]}...")
    
    inferred_attendees = []
    email_body = args.email_content.lower()

    for user_id, user_email in user_map.items():
        if user_id.lower() in email_body or user_email.lower() in email_body:
            if user_email not in inferred_attendees:
                inferred_attendees.append(user_email)

    return ParseEmailOutput(
        sender="inferred-sender@example.com",
        subject="Inferred Meeting Request",
        body=args.email_content,
        inferred_attendees=inferred_attendees,
        parsed_at=datetime.datetime.now().isoformat()
    )

def retrieve_calendar_events(gcal_service: Any, args: RetrieveCalendarEventsArgs) -> RetrieveCalendarEventsOutput:
    """Retrieves calendar events from Google Calendar within a specified date range."""
    print(f"Retrieving Google Calendar events from {args.start_date} to {args.end_date}...")
    try:
        start_time = datetime.datetime.fromisoformat(args.start_date + "T00:00:00Z").isoformat()
        end_time = datetime.datetime.fromisoformat(args.end_date + "T23:59:59Z").isoformat()
        events_result = gcal_service.events().list(calendarId="primary", timeMin=start_time, timeMax=end_time, singleEvents=True, orderBy="startTime").execute()
        events = events_result.get("items", [])
        if not events:
            return RetrieveCalendarEventsOutput(status="No upcoming events found.")
        
        formatted_events = [
            CalendarEvent(
                title=event["summary"],
                start=event["start"].get("dateTime", event["start"].get("date")),
                end=event["end"].get("dateTime", event["end"].get("date"))
            ) for event in events
        ]
        return RetrieveCalendarEventsOutput(events=formatted_events)
    except HttpError as error:
        return RetrieveCalendarEventsOutput(error=f"An API error occurred: {error}")
    except Exception as e:
        return RetrieveCalendarEventsOutput(error=f"An unexpected error occurred: {e}")

def find_available_slots(gcal_service: Any, args: FindAvailableSlotsArgs) -> FindAvailableSlotsOutput:
    """Finds available time slots for a list of attendees based on their Google Calendar free/busy information."""
    print(f"Finding available {args.duration_minutes}-minute slots for {args.attendee_emails}...")
    try:
        start_time_dt = datetime.datetime.fromisoformat(args.start_date + "T00:00:00").replace(tzinfo=datetime.timezone.utc)
        end_time_dt = datetime.datetime.fromisoformat(args.end_date + "T23:59:59").replace(tzinfo=datetime.timezone.utc)
        body = {"timeMin": start_time_dt.isoformat(), "timeMax": end_time_dt.isoformat(), "items": [{"id": email} for email in args.attendee_emails], "timeZone": "UTC"}
        freebusy_result = gcal_service.freebusy().query(body=body).execute()
        
        all_busy_intervals = []
        for cal_id, data in freebusy_result.get('calendars', {}).items():
            if data.get('errors'):
                print(f"Warning: Could not retrieve free/busy for {cal_id}.")
                continue
            for interval in data.get('busy', []):
                all_busy_intervals.append((datetime.datetime.fromisoformat(interval['start']), datetime.datetime.fromisoformat(interval['end'])))
        
        all_busy_intervals.sort(key=lambda x: x[0])
        merged_busy = []
        if all_busy_intervals:
            current_start, current_end = all_busy_intervals[0]
            for next_start, next_end in all_busy_intervals[1:]:
                if next_start < current_end:
                    current_end = max(current_end, next_end)
                else:
                    merged_busy.append((current_start, current_end))
                    current_start, current_end = next_start, next_end
            merged_busy.append((current_start, current_end))

        available_slots = []
        last_busy_end = start_time_dt
        for busy_start, busy_end in merged_busy:
            if busy_start > last_busy_end and (busy_start - last_busy_end) >= datetime.timedelta(minutes=args.duration_minutes):
                available_slots.append(TimeSlot(start_time=last_busy_end.isoformat(), end_time=busy_start.isoformat()))
            last_busy_end = max(last_busy_end, busy_end)
        
        if end_time_dt > last_busy_end and (end_time_dt - last_busy_end) >= datetime.timedelta(minutes=args.duration_minutes):
            available_slots.append(TimeSlot(start_time=last_busy_end.isoformat(), end_time=end_time_dt.isoformat()))
        
        return FindAvailableSlotsOutput(slots=available_slots) if available_slots else FindAvailableSlotsOutput(status="No common slots found.")
    except HttpError as error:
        return FindAvailableSlotsOutput(error=f"An API error occurred: {error}")
    except Exception as e:
        return FindAvailableSlotsOutput(error=f"An unexpected error occurred: {e}")
