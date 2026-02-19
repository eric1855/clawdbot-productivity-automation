from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .llm import LLMClient
from .models import JobPosting
from .settings import QAConfig


@dataclass(slots=True)
class AliasRule:
    key: str
    patterns: list[str]


class QuestionAnswerer:
    def __init__(self, qa_config: QAConfig, llm: LLMClient):
        self.qa_config = qa_config
        self.llm = llm
        self.defaults, self.alias_rules = self._load_defaults(Path(qa_config.defaults_path))

    @staticmethod
    def _load_defaults(path: Path) -> tuple[dict[str, str], list[AliasRule]]:
        if not path.exists():
            return {}, []

        raw = yaml.safe_load(path.read_text()) or {}
        defaults = {str(k): str(v) for k, v in (raw.get("defaults") or {}).items()}

        alias_rules = []
        for item in raw.get("prompt_aliases") or []:
            alias_rules.append(
                AliasRule(
                    key=str(item.get("key", "")),
                    patterns=[str(p).lower() for p in (item.get("patterns") or [])],
                )
            )
        return defaults, alias_rules

    def answer(
        self,
        prompt: str,
        input_type: str,
        job: JobPosting,
        choices: list[str] | None = None,
    ) -> str:
        prompt_norm = (prompt or "").strip().lower()
        choices = [choice.strip() for choice in (choices or []) if choice.strip()]

        key = self._alias_key_for_prompt(prompt_norm)
        default_answer = self.defaults.get(key, "") if key else ""
        if not default_answer:
            default_answer = self._heuristic_default(prompt_norm)

        if choices:
            choice_answer = self._match_choice(default_answer, choices)
            if choice_answer:
                return choice_answer

        if self.llm.enabled:
            llm_answer = self.llm.answer_application_question(
                prompt=prompt,
                job=job,
                default_answer=default_answer,
                allowed_choices=choices,
            )
            if llm_answer:
                if choices:
                    return self._match_choice(llm_answer, choices) or choices[0]
                return llm_answer[: self.qa_config.max_answer_chars]

        if default_answer:
            if choices:
                return self._match_choice(default_answer, choices) or choices[0]
            return default_answer[: self.qa_config.max_answer_chars]

        if choices:
            return choices[0]

        if input_type in {"email"}:
            return self.defaults.get("email", "")
        if input_type in {"tel"}:
            return self.defaults.get("phone", "")
        if "linkedin" in prompt_norm:
            return self.defaults.get("linkedin", "")
        if "github" in prompt_norm:
            return self.defaults.get("github", "")
        if "portfolio" in prompt_norm or "website" in prompt_norm:
            return self.defaults.get("portfolio", "")
        return ""

    def _alias_key_for_prompt(self, prompt: str) -> str:
        for rule in self.alias_rules:
            for pattern in rule.patterns:
                if pattern and pattern in prompt:
                    return rule.key
        return ""

    @staticmethod
    def _match_choice(answer: str, choices: list[str]) -> str:
        if not answer:
            return ""

        lowered = {choice.lower(): choice for choice in choices}
        if answer.lower() in lowered:
            return lowered[answer.lower()]

        for choice in choices:
            if choice.lower() in answer.lower() or answer.lower() in choice.lower():
                return choice
        return ""

    @staticmethod
    def _heuristic_default(prompt: str) -> str:
        if any(token in prompt for token in ("authorized to work", "work authorization")):
            return "Yes"
        if any(token in prompt for token in ("sponsorship", "visa")):
            return "No"
        if "relocate" in prompt:
            return "Yes"
        return ""

