import json
import logging
import ollama


from commands_and_tools import (
    COMMAND_MAPPINGS,
    ACTIONS,
    tools,
    ASK_AI_TOOLS,
    extra_tools,
    tool_function_registry,
)


# Configure logging
logging.basicConfig(level=logging.INFO)
CYAN = "\033[96m"
RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"


def _tools_for_llm():
    try:
        from wkey.ask_ai_bridge import is_ask_ai_enabled
    except ImportError:
        from ask_ai_bridge import is_ask_ai_enabled
    return tools + ASK_AI_TOOLS if is_ask_ai_enabled() else tools


# Function to execute commands using Ollama
def execute_command_run_with_tool_local(query, max_retries=3, retry_delay=2):
    # System message to guide the model
    tools_messages = [
        {
            "role": "system",
            "content": """You are a specialized assistant for controlling computer functions. Your role is to:
            1. Carefully analyze user queries to determine the most appropriate tool/function
            2. Select the SINGLE most relevant tool from the available options
            3. Only use tools that exactly match the user's intent
            4. For system controls (volume, media, windows), be very precise in tool selection
            5. If no exact tool matches the query, do not force a tool selection

            Examples:
            - "play music" → use play_song()
            - "volume up" → use volume_up()
            - "skip" → use next_track()
            - "minimize everything" → use minimize_all_windows()
            - "check internet speed" → ping_google()

            Only respond with tool calls, no conversational responses.""",
        },
        {
            "role": "user",
            "content": query,
        },
    ]

    try:
        logging.info(f"Executing command: {query}")

        # Call Ollama's chat API
        response = ollama.chat(
            model="qwen2.5-coder:0.5b",
            messages=tools_messages,
            tools=_tools_for_llm(),
        )

        # Process the response
        tool_calls = response.get("message", {}).get("tool_calls", [])
        if tool_calls:
            for tool_call in tool_calls:
                function_name = tool_call["function"]["name"]
                function_args = tool_call["function"]["arguments"]

                tool_registry = tool_function_registry(globals())
                if function_name in tool_registry:
                    logging.info(
                        f"{CYAN}Executing function: {function_name} with arguments: {function_args}{RESET}"
                    )
                    func = tool_registry[function_name]

                    result = func(**function_args)

                else:
                    logging.error(f"{RED}Function {function_name} not found{RESET}")
                    return False
        else:
            logging.error("No tool calls found in the response")

        return True
    except Exception as e:
        logging.error(
            f"Error in execute_command_run_with_tool: {str(e)}", exc_info=True
        )
        return False


# Test the function
if __name__ == "__main__":
    test_query = "play music"
    execute_command_run_with_tool_local(test_query)
