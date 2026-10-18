from types import SimpleNamespace

from app import llm


def test_gemini_generate_content(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    request = {}

    def post(url, **kwargs):
        request["url"] = url
        request.update(kwargs)
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"candidates": [{"content": {"parts": [{"text": "{\"ok\": "},
                                                                         {"text": "true}"}]}}]},
        )

    monkeypatch.setattr(llm.requests, "post", post)

    assert llm.complete("system prompt", "user prompt", 800) == '{"ok": true}'
    assert request["url"].endswith("/models/gemini-3.8-flash:generateContent")
    assert request["params"] == {"key": "test-key"}
    assert request["json"]["systemInstruction"]["parts"][0]["text"] == "system prompt"
    assert request["json"]["generationConfig"]["maxOutputTokens"] == 800