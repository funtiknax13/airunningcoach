from app.services import ai_agent


def test_gemini_is_third_provider_and_gets_reasoning_limits(monkeypatch):
    monkeypatch.setattr(ai_agent.settings, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(ai_agent.settings, "GEMINI_REASONING_EFFORT", "low")
    names = [p["name"] for p in ai_agent._providers()]
    assert names == ["gemini"]                      # ключей Groq/DeepSeek в тестах нет
    p = ai_agent._providers()[0]
    kw = ai_agent._chat_kwargs(p, [], 900, 0.3, {"type": "json_object"})
    assert kw["max_tokens"] == 900 + ai_agent._GEMINI_THINKING_HEADROOM
    assert kw["extra_body"] == {"reasoning_effort": "low"}
    assert kw["response_format"] == {"type": "json_object"}


def test_gemini_reasoning_effort_can_be_disabled(monkeypatch):
    monkeypatch.setattr(ai_agent.settings, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(ai_agent.settings, "GEMINI_REASONING_EFFORT", "")
    kw = ai_agent._chat_kwargs(ai_agent._providers()[0], [], 100, 0.3, None)
    assert "extra_body" not in kw and "response_format" not in kw


def test_other_providers_keep_their_max_tokens(monkeypatch):
    kw = ai_agent._chat_kwargs({"name": "deepseek", "model": "m"}, [], 700, 0.3, None)
    assert kw["max_tokens"] == 700 and "extra_body" not in kw


def test_custom_openai_compatible_provider_goes_first(monkeypatch):
    monkeypatch.setattr(ai_agent.settings, "CUSTOM_AI_API_KEY", "k")
    monkeypatch.setattr(ai_agent.settings, "CUSTOM_AI_BASE_URL", "https://example.test/v1")
    monkeypatch.setattr(ai_agent.settings, "CUSTOM_AI_MODEL", "m")
    monkeypatch.setattr(ai_agent.settings, "GEMINI_API_KEY", "g")
    names = [p["name"] for p in ai_agent._providers()]
    assert names == ["custom", "gemini"]
    kw = ai_agent._chat_kwargs(ai_agent._providers()[0], [], 500, 0.2, None)
    assert kw["model"] == "m" and kw["max_tokens"] == 500 and "extra_body" not in kw


def test_custom_provider_needs_key_url_and_model(monkeypatch):
    monkeypatch.setattr(ai_agent.settings, "CUSTOM_AI_API_KEY", "k")
    monkeypatch.setattr(ai_agent.settings, "CUSTOM_AI_BASE_URL", "")
    assert [p["name"] for p in ai_agent._providers()] == []
