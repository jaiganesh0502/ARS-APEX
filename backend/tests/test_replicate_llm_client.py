import pytest

from app.integrations.llm import replicate_client
from app.integrations.llm.replicate_client import (
    LLMConfigurationError,
    LLMProviderError,
    LLMTimeoutError,
    ReplicateLLMClient,
)


def test_replicate_client_builds_safe_input_and_collects_stream():
    captured = {}

    def stream(model, *, input):
        captured.update(model=model, input=input)
        return iter(["DRAFT — ", "REQUIRES PHYSICIAN REVIEW AND SIGN-OFF"])

    client = ReplicateLLMClient(token="test-token", stream=stream)

    result = client.generate_discharge_summary({"primary_diagnosis": "Pneumonia"})

    assert captured["model"] == "openai/gpt-5.6-luna"
    assert captured["input"]["reasoning_effort"] == "low"
    assert "use only" in captured["input"]["system_prompt"].lower()
    assert result == "DRAFT — REQUIRES PHYSICIAN REVIEW AND SIGN-OFF"


def test_replicate_client_rejects_blank_output():
    client = ReplicateLLMClient(
        token="test-token", stream=lambda *_args, **_kwargs: iter(["  "])
    )

    with pytest.raises(LLMProviderError):
        client.generate_discharge_summary({"primary_diagnosis": "Pneumonia"})


def test_replicate_client_requires_token():
    with pytest.raises(LLMConfigurationError):
        ReplicateLLMClient(token="")


def test_replicate_client_maps_provider_timeouts_to_safe_error():
    def stream(*_args, **_kwargs):
        raise TimeoutError("provider timeout details")

    client = ReplicateLLMClient(token="test-token", stream=stream)

    with pytest.raises(LLMTimeoutError, match="timed out"):
        client.generate_discharge_summary({"primary_diagnosis": "Pneumonia"})


def test_replicate_client_hides_provider_error_details():
    def stream(*_args, **_kwargs):
        raise RuntimeError("provider response with private details")

    client = ReplicateLLMClient(token="test-token", stream=stream)

    with pytest.raises(LLMProviderError, match="provider failed") as error:
        client.generate_discharge_summary({"primary_diagnosis": "Pneumonia"})

    assert "private details" not in str(error.value)


def test_replicate_client_binds_supplied_token_to_sdk_client(monkeypatch):
    captured = {}

    class FakeProviderClient:
        def __init__(self, *, api_token):
            captured["api_token"] = api_token

        def stream(self, *_args, **_kwargs):
            return iter(["DRAFT — REQUIRES PHYSICIAN REVIEW AND SIGN-OFF"])

    class FakeReplicate:
        Client = FakeProviderClient

    monkeypatch.setattr(replicate_client, "replicate", FakeReplicate)

    client = ReplicateLLMClient(token="test-token")

    assert captured["api_token"] == "test-token"
    assert client.generate_discharge_summary({"primary_diagnosis": "Pneumonia"}).startswith(
        "DRAFT —"
    )


def test_replicate_client_uses_configured_model_by_default(monkeypatch):
    captured = {}
    monkeypatch.setattr(replicate_client.settings, "LLM_MODEL", "configured-model")

    def stream(model, *, input):
        captured["model"] = model
        return iter(["DRAFT — REQUIRES PHYSICIAN REVIEW AND SIGN-OFF"])

    client = ReplicateLLMClient(token="test-token", stream=stream)

    client.generate_discharge_summary({"primary_diagnosis": "Pneumonia"})

    assert captured["model"] == "configured-model"


def test_replicate_client_does_not_accept_model_override():
    with pytest.raises(TypeError):
        ReplicateLLMClient(token="test-token", model="arbitrary-model")


def test_replicate_client_rejects_output_without_required_draft_heading():
    client = ReplicateLLMClient(
        token="test-token", stream=lambda *_args, **_kwargs: iter(["Clinical draft"])
    )

    with pytest.raises(LLMProviderError, match="review heading"):
        client.generate_discharge_summary({"primary_diagnosis": "Pneumonia"})

