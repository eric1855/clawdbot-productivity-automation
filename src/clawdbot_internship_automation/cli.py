from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .handshake_bot import HandshakeBot
from .llm import LLMClient
from .question_answerer import QuestionAnswerer
from .resume_builder import ResumeBuilder
from .settings import load_config


def _read_base_resume_text(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    if file_path.suffix.lower() in {".txt", ".md"}:
        return file_path.read_text()
    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automate Handshake SWE internship discovery and applications."
    )
    parser.add_argument(
        "--config",
        default="config/application.yaml",
        help="Path to YAML config file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Override config to stop before final submission.",
    )
    parser.add_argument(
        "--max-applications",
        type=int,
        default=None,
        help="Override max applications for this run.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log verbosity.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    config = load_config(args.config)
    if args.dry_run:
        config.application.dry_run = True
        config.application.auto_submit = False
    if args.max_applications is not None:
        config.application.max_applications = args.max_applications
    if args.headless:
        config.browser.headless = True

    llm_client = LLMClient(config.llm)
    question_answerer = QuestionAnswerer(config.qa, llm_client)
    resume_builder = ResumeBuilder(config.resume, config.qa, llm_client)
    base_resume_text = _read_base_resume_text(config.resume.base_resume_path)

    bot = HandshakeBot(
        config=config,
        resume_builder=resume_builder,
        question_answerer=question_answerer,
        base_resume_text=base_resume_text,
    )
    try:
        results = bot.run()
    except Exception as exc:
        logging.error("Automation run failed: %s", exc)
        logging.error(
            "If your school uses SSO/Duo, keep the browser window open and complete authentication."
        )
        raise SystemExit(1) from exc

    status_counts: dict[str, int] = {}
    for result in results:
        status_counts[result.status] = status_counts.get(result.status, 0) + 1

    logging.info("Run complete. Results: %s", status_counts)


if __name__ == "__main__":
    main()
