# --- Pydantic Agent (Updated for Llama) ---

class PydanticAgent:
    """An agent that uses Pydantic models and Google Calendar, powered by a Llama model."""

    def __init__(self, gcal_service: Any, model_name: str, base_url: str, user_map: Dict[str, str], api_key: str = "local-llama"):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.gcal_service = gcal_service
        self.model_name = model_name
        self.user_map = user_map
        self.tools = {
            "parse_email": {"function": parse_email, "args_model": ParseEmailArgs},
            "retrieve_calendar_events": {"function": retrieve_calendar_events, "args_model": RetrieveCalendarEventsArgs},
            "find_available_slots": {"function": find_available_slots, "args_model": FindAvailableSlotsArgs},
        }

    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [{"type": "function", "function": {"name": name, "description": tool["function"].__doc__, "parameters": tool["args_model"].model_json_schema()}} for name, tool in self.tools.items()]

    def run_conversation(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        tool_defs = self._get_tool_definitions()
        response = self.client.chat.completions.create(model=self.model_name, messages=messages, tools=tool_defs, tool_choice="auto")
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if tool_calls:
            messages.append(response_message)
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                args_model = self.tools[function_name]["args_model"]
                try:
                    function_args = args_model.model_validate_json(tool_call.function.arguments)
                    function_to_call = self.tools[function_name]["function"]
                    
                    if function_name == "parse_email":
                        function_response = function_to_call(function_args, self.user_map)
                    elif function_name in ["retrieve_calendar_events", "find_available_slots"]:
                        function_response = function_to_call(self.gcal_service, function_args)
                    else:
                        function_response = function_to_call(function_args)

                    # Serialize the Pydantic model output to a JSON string.
                    content_str = function_response.model_dump_json()
                    messages.append({"tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": content_str})
                except Exception as e:
                    print(f"Error calling tool {function_name}: {e}")
                    messages.append({"tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": f'{{"error": "Failed to execute tool: {e}"}}'})
            
            second_response = self.client.chat.completions.create(model=self.model_name, messages=messages)
            return second_response.choices[0].message
        return response_message