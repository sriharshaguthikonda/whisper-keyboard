"""TODO:
TODO:  we need to make changes to
TODO:
TODO:  redirect_uri_mismatch
TODO:
TODO:   for this function to work, don't use it till then
TODO:"""

import os
import json
import grpc
from flask import Flask, redirect, request, session, url_for
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.assistant.embedded.v1alpha2 import embedded_assistant_pb2
from google.assistant.embedded.v1alpha2 import embedded_assistant_pb2_grpc

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Replace with your secret key

# Load credentials
credentials_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\credentials.json"
scopes = ["https://www.googleapis.com/auth/assistant-sdk-prototype"]


@app.route("/")
def index():
    if "credentials" not in session:
        return redirect(url_for("authorize"))

    credentials = Credentials(**session["credentials"])

    # Refresh the token if expired
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    session["credentials"] = credentials_to_dict(credentials)
    return "Credentials are set up. You can now use the Google Assistant API."


@app.route("/authorize")
def authorize():
    flow = Flow.from_client_secrets_file(credentials_path, scopes=scopes)
    flow.redirect_uri = url_for("oauth2callback", _external=True)
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true"
    )
    session["state"] = state
    return redirect(authorization_url)


@app.route("/oauth2callback")
def oauth2callback():
    state = session["state"]
    flow = Flow.from_client_secrets_file(credentials_path, scopes=scopes, state=state)
    flow.redirect_uri = url_for("oauth2callback", _external=True)

    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    session["credentials"] = credentials_to_dict(credentials)

    return redirect(url_for("index"))


def credentials_to_dict(credentials):
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }


def google_assistant(transcript):
    try:
        if "credentials" not in session:
            raise Exception("Credentials not found in session. Please authorize first.")

        credentials = Credentials(**session["credentials"])

        # Refresh the token if expired
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

        # Create a gRPC channel
        channel = grpc.secure_channel(
            "embeddedassistant.googleapis.com", grpc.ssl_channel_credentials()
        )

        # Create a stub
        assistant = embedded_assistant_pb2_grpc.EmbeddedAssistantStub(channel)

        # Create an AssistRequest
        request = embedded_assistant_pb2.AssistRequest()
        request.config.audio_out_config.encoding = (
            embedded_assistant_pb2.AudioOutConfig.LINEAR16
        )
        request.config.audio_out_config.sample_rate_hertz = 16000
        request.config.dialog_state_in.language_code = "en-US"
        request.config.device_config.device_id = "my-device"
        request.config.device_config.device_model_id = "my-model"
        request.text_query = transcript

        # Send the request and process the response
        response = assistant.Assist(request)
        for resp in response:
            if resp.speech_results:
                print("Transcript: ", resp.speech_results[0].transcript)
            if resp.audio_out.audio_data:
                with open("output.wav", "wb") as audio_file:
                    audio_file.write(resp.audio_out.audio_data)
    except Exception as e:
        print(f"Error communicating with Google Assistant: {e}")


# Example usage
if __name__ == "__main__":
    app.run("localhost", 8080, debug=True)
