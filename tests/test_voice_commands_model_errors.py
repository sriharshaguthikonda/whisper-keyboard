from wkey.groq_model_catalog import classify_groq_model_error


def test_tool_use_404_model_error_is_recoverable():
    body = '{"error":{"message":"model moonshotai/kimi-k2-instruct-0905 not found"}}'

    result = classify_groq_model_error(404, body)

    assert result.is_model_error
    assert result.reason == "model_unavailable_http_404"


def test_tool_use_rate_limit_is_not_model_quarantine():
    body = '{"error":{"message":"rate limit exceeded"}}'

    result = classify_groq_model_error(429, body)

    assert result.is_model_error is False
    assert result.is_rate_limit is True


def test_tool_use_failed_generation_is_recoverable():
    body = (
        '{"error":{"message":"Failed to call a function. Please adjust your prompt.",'
        '"type":"invalid_request_error","code":"tool_use_failed",'
        '"failed_generation":"<function=launch_application {\\"app\\": \\"Device Manager\\"}>"}}'
    )

    result = classify_groq_model_error(400, body)

    assert result.is_model_error
    assert result.reason == "tool_use_failed_http_400"
