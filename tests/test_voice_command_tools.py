def test_advertised_voice_tools_have_executor_registry_entries():
    from wkey.commands_and_tools import tools, tool_function_registry

    advertised = {
        item["function"]["name"]
        for item in tools
        if item.get("type") == "function" and "function" in item
    }
    registry = tool_function_registry()

    assert "open_startup_folder" in advertised
    assert "open_startup_folder" in registry
    assert advertised - set(registry) == set()
