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
from clawdbot_internship_automation.resume_builder import ResumeBuilder
from clawdbot_internship_automation.settings import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a tailored resume for one Handshake job using project config."
    )
    parser.add_argument("--config", default="config/application.yaml")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--company", default="")
    parser.add_argument("--location", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--description", default="")
    parser.add_argument("--description-file", default="")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _read_base_resume_text(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    if file_path.suffix.lower() in {".txt", ".md"}:
        return file_path.read_text()
    return ""


def _get_description(args: argparse.Namespace) -> str:
    if args.description_file:
        path = Path(args.description_file)
        if path.exists():
            return path.read_text()
    return args.description


def main() -> int:
    args = parse_args()
    config = load_config(args.config)

    llm_client = LLMClient(config.llm)
    question_answerer = QuestionAnswerer(config.qa, llm_client)
    resume_builder = ResumeBuilder(config.resume, config.qa, llm_client)
    base_resume_text = _read_base_resume_text(config.resume.base_resume_path)

    job = JobPosting(
        job_id=args.job_id,
        title=args.title,
        company=args.company,
        location=args.location,
        description=_get_description(args),
        url=args.url,
    )
    resume_pdf = resume_builder.build(
        job=job,
        defaults=question_answerer.defaults,
        base_resume_text=base_resume_text,
    )

    payload = {
        "job_id": job.job_id,
        "title": job.title,
        "company": job.company,
        "resume_pdf": str(resume_pdf),
        "resume_markdown": str(resume_pdf.with_suffix(".md")),
    }

    if args.json:
        print(json.dumps(payload))
    else:
        print(payload["resume_pdf"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

