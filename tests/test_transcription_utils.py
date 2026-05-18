from wkey.groq_model_catalog import classify_groq_model_error


def test_stt_404_model_error_is_recoverable():
    body = '{"error":{"message":"model whisper-old is not supported"}}'

    result = classify_groq_model_error(400, body)

    assert result.is_model_error
    assert result.reason == "model_unavailable_http_400"
