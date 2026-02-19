#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clawdbot_internship_automation.llm import LLMClient
from clawdbot_internship_automation.models import JobPosting
from clawdbot_internship_automation.question_answerer import QuestionAnswerer
from clawdbot_internship_automation.settings import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Answer one application question using qa defaults + optional LLM."
    )
    parser.add_argument("--config", default="config/application.yaml")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--input-type", default="text")
    parser.add_argument("--choices", default="")
    parser.add_argument("--job-id", default="runtime-job")
    parser.add_argument("--title", default="Software Engineer Intern")
    parser.add_argument("--company", default="")
    parser.add_argument("--location", default="")
    parser.add_argument("--description", default="")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _parse_choices(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []

    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass

    return [part.strip() for part in text.split("|") if part.strip()]


def main() -> int:
    args = parse_args()
    choices = _parse_choices(args.choices)

    config = load_config(args.config)
    llm_client = LLMClient(config.llm)
    question_answerer = QuestionAnswerer(config.qa, llm_client)

    job = JobPosting(
        job_id=args.job_id,
        title=args.title,
        company=args.company,
        location=args.location,
        description=args.description,
    )

    answer = question_answerer.answer(
        prompt=args.prompt,
        input_type=args.input_type,
        job=job,
        choices=choices,
    )

    payload = {
        "prompt": args.prompt,
        "input_type": args.input_type,
        "choices": choices,
        "answer": answer,
    }
    if args.json:
        print(json.dumps(payload))
    else:
        print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

