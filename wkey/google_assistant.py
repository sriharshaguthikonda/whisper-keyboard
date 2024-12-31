import os
import json
import requests
from google.oauth2.credentials import Credentials
from google.assistant.library import Assistant
from google.assistant.library.event import EventType


def google_assistant(transcript):
    try:
        # Load credentials
        credentials_path = "credentials.json"
        with open(credentials_path, "r") as file:
            credentials_data = json.load(file)

        credentials = Credentials(token=None, **credentials_data)

        # Initialize the Assistant
        with Assistant(credentials) as assistant:
            for event in assistant.start():
                if event.type == EventType.ON_CONVERSATION_TURN_STARTED:
                    assistant.send_text_query(transcript)
                elif event.type == EventType.ON_END_OF_UTTERANCE:
                    assistant.stop_conversation()
                elif event.type == EventType.ON_CONVERSATION_TURN_FINISHED:
                    break
    except Exception as e:
        print(f"Error communicating with Google Assistant: {e}")


# Example usage
if __name__ == "__main__":
    google_assistant("Turn on the lights")
