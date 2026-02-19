from __future__ import annotations

import json
import logging
import os
from typing import Any

from .models import JobPosting
from .settings import LLMConfig

LOGGER = logging.getLogger(__name__)

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional import at runtime
    OpenAI = None


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None
        api_key = os.getenv(config.api_key_env, "")
        if config.enabled and config.provider.lower() == "openai" and api_key and OpenAI:
            self._client = OpenAI(api_key=api_key)

        if config.enabled and self._client is None:
            LOGGER.warning(
                "LLM is enabled but client could not initialize. "
                "Set %s to enable tailored resume/question responses.",
                config.api_key_env,
            )

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        if not self._client:
            return ""

        try:
            completion = self._client.chat.completions.create(
                model=self.config.model,
                temperature=self.config.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            message = completion.choices[0].message.content
            return (message or "").strip()
        except Exception as exc:
            LOGGER.warning("LLM request failed: %s", exc)
            return ""

    def generate_resume_sections(
        self, job: JobPosting, base_resume_text: str
    ) -> dict[str, Any]:
        default = {
            "summary": "Motivated software engineering student focused on shipping reliable products.",
            "top_skills": ["Python", "Java", "TypeScript", "SQL", "Testing"],
            "experience_highlights": [
                "Built and shipped production-ready features across backend and frontend stacks.",
                "Improved reliability and observability with metrics, tests, and incident fixes.",
                "Collaborated in agile teams using code reviews and iterative delivery.",
            ],
        }
        if not self.enabled:
            return default

        system = (
            "You tailor internship resumes. Return only strict JSON with keys "
            "'summary', 'top_skills', 'experience_highlights'. "
            "top_skills and experience_highlights must be arrays of short strings."
        )
        user = (
            f"Job Title: {job.title}\n"
            f"Company: {job.company}\n"
            f"Location: {job.location}\n"
            f"Job Description:\n{job.description[:5000]}\n\n"
            f"Candidate Resume Text:\n{base_resume_text[:5000]}\n\n"
            "Create a targeted but truthful internship resume angle."
        )
        raw = self._chat(system, user)
        if not raw:
            return default

        try:
            parsed = json.loads(raw)
            summary = str(parsed.get("summary", default["summary"])).strip()
            top_skills = [
                str(item).strip() for item in parsed.get("top_skills", default["top_skills"])
            ]
            highlights = [
                str(item).strip()
                for item in parsed.get(
                    "experience_highlights", default["experience_highlights"]
                )
            ]
            return {
                "summary": summary or default["summary"],
                "top_skills": [s for s in top_skills if s][:8] or default["top_skills"],
                "experience_highlights": [h for h in highlights if h][:6]
                or default["experience_highlights"],
            }
        except Exception:
            return default

    def answer_application_question(
        self,
        prompt: str,
        job: JobPosting,
        default_answer: str,
        allowed_choices: list[str] | None = None,
    ) -> str:
        if not self.enabled:
            return default_answer

        choices = allowed_choices or []
        system = (
            "You answer internship application questions concisely and truthfully. "
            "If choices are given, answer with one exact choice. "
            "Otherwise keep answer to one sentence."
        )
        user = (
            f"Question: {prompt}\n"
            f"Job: {job.title} at {job.company}\n"
            f"Allowed choices: {choices}\n"
            f"Default answer: {default_answer}\n"
        )
        answer = self._chat(system, user).strip()
        if not answer:
            return default_answer

        if choices:
            lowered = {c.lower(): c for c in choices}
            if answer.lower() in lowered:
                return lowered[answer.lower()]
            for choice in choices:
                if choice.lower() in answer.lower():
                    return choice
            return default_answer if default_answer in choices else choices[0]

        return answer
