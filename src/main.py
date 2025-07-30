
import json
from datetime import datetime, timedelta, timezone
from threading import Thread

from flask import Flask, jsonify, request
from rich import print_json

from src.agent import PydanticAgent
from src.gcal import (authenticate_google_calendar, find_available_slots,
                      parse_email, retrieve_calendar_events)
from src.models import (FindAvailableSlotsArgs, FindAvailableSlotsOutput,
                        ParseEmailArgs, ParseEmailOutput,
                        RetrieveCalendarEventsArgs,
                        RetrieveCalendarEventsOutput)

app = Flask(__name__)

# --- Global Configuration ---
USER_MAP = {
    "userone": "userone.amd@gmail.com",
    "usertwo": "usertwo.amd@gmail.com",
    "userthree": "userthree.amd@gmail.com",
}
LLAMA_BASE_URL = "http://localhost:11434/v1"
LLAMA_MODEL = "llama3"


def your_meeting_assistant(data):
    # Find the user_id by reverse-mapping the email from USER_MAP
    current_user_id = None
    for user_id, email in USER_MAP.items():
        if email == data.get("From"):
            current_user_id = user_id
            break
    
    if not current_user_id:
        return jsonify({"error": f"User with email '{from_email}' not found in USER_MAP."}), 400

    print(f"--- Received request for user: {current_user_id} ---")

    # Authenticate the user for this request
    gcal_service = authenticate_google_calendar(current_user_id)
    if not gcal_service:
        return jsonify({"error": f"Could not authenticate Google Calendar for user {current_user_id}"}), 500

    # Initialize the agent for this request
    agent = PydanticAgent(
        gcal_service=gcal_service,
        model_name=LLAMA_MODEL,
        base_url=LLAMA_BASE_URL,
        user_map=USER_MAP
    )

    # Construct the system prompt and conversation history
    system_prompt = (
        "You are a helpful assistant. "
        f"The current user is '{current_user_id}' ({USER_MAP[current_user_id]}). "
        "You have access to a list of users and their emails: "
        f"{str(USER_MAP)}. When a user is mentioned by their ID (e.g., userone), "
        "you must use their corresponding email address for calendar operations. "
        "When a request requires multiple steps (like parsing an email and then finding a time), "
        "complete each step sequentially using the available tools. "
        "IMPORTANT: When calling a tool, ensure that all arguments are valid JSON. "
        "Specifically, lists of strings must be formatted as proper JSON arrays, for example: "
        '["email1@example.com", "email2@example.com"]. Do not use single quotes or output a string representation of a Python list.'
    )
    
    conversation_history = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    try:
        final_response = agent.run_conversation(conversation_history)
        return jsonify({"response": final_response.content, "request_id": data.get("Request_id")})
    except Exception as e:
        print(f"An error occurred during conversation: {e}")
        return jsonify({"error": "An internal error occurred while processing the request."}), 500
    new_event = get_new_event_sync(data)
    ist = timezone(timedelta(hours=5, minutes=30))
    curr_time = datetime.now(ist)
    calender_events = get_all_calendar_events(users, curr_time.isoformat(), 
                                                (curr_time + timedelta(weeks=1)).isoformat())
    calender_events.append(new_event)
    set_event_priorities_sync(calender_events)
    # use new_event and calender_events to get scheduled events
    scheduled_events = reschedule_all_meetings(calender_events) 
    # Format the output
    output_formatted = format_to_output(scheduled_events, data, new_event)
    return output_formatted

@app.route('/receive', methods=['POST'])
def receive():
    data = request.get_json()
    print(f"\n Received: {json.dumps(data, indent=2)}")
    new_data = your_meeting_assistant(data)
    print_json(json.dumps(new_data, indent=2))
    return jsonify(new_data)

if __name__ == "__main__":
    # To run this web client:
    # 1. Make sure you have Flask installed: pip install Flask
    # 2. Run the script: python your_script_name.py
    # 3. Send a POST request to http://localhost:5000/receive with a JSON body like:
    #    {
    #        "Request_id": "TC1-BOTH-AVAILABLE-6118b54f",
    #        "Datetime": "2025-07-02T12:34:55",
    #        "Location": "IIT Mumbai",
    #        "From": "userone.amd@gmail.com",
    #        "Attendees": [{"email": "usertwo.amd@gmail.com"}, {"email": "userthree.amd@gmail.com"}],
    #        "Subject": "Goals Discussion",
    #        "EmailContent": "Hi Team. Let's meet next Thursday for 30 minutes and discuss about our Goals."
    #    }
    app.run(port=5000, debug=True)