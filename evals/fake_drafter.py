"""A stand-in drafting model for Inspect, so the live eval's whole pipeline (prompt, generate,
parse, screen, scorers) runs in CI with no API key and no cost:

    python evals/run.py pipeline

It answers with radar.brief.fake_llm.FakeLLM: the brief built only from the context in the prompt.
It never follows a note, so it shows that the scorers can pass; a real model is what the eval is
for. Registered when evals/run.py imports it, before any model is resolved.
"""
from __future__ import annotations

import sys
from pathlib import Path

from inspect_ai.model import ChatMessage, GenerateConfig, ModelAPI, ModelOutput, modelapi

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from radar.brief.fake_llm import FakeLLM  # noqa: E402


class FakeDrafter(ModelAPI):
    def __init__(self, model_name: str, base_url: str | None = None, api_key: str | None = None,
                 config: GenerateConfig = GenerateConfig(), **model_args):
        super().__init__(model_name, base_url, api_key, [], config)

    async def generate(self, input: list[ChatMessage], tools, tool_choice, config) -> ModelOutput:
        system = next((m.text for m in input if m.role == "system"), "")
        user = next((m.text for m in reversed(input) if m.role == "user"), "")
        return ModelOutput.from_content(model=self.model_name, content=FakeLLM().complete(system, user))


@modelapi(name="fakedrafter")
def fakedrafter():
    return FakeDrafter
