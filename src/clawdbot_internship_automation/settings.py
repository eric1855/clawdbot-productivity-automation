from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_HANDSHAKE_LOGIN_URL = "https://app.joinhandshake.com/login"
DEFAULT_HANDSHAKE_JOBS_URL = "https://app.joinhandshake.com/stu/postings"

DEFAULT_BROWSER_HEADLESS = False
DEFAULT_BROWSER_SLOW_MO_MS = 120
DEFAULT_BROWSER_TIMEOUT_MS = 25000

DEFAULT_FILTER_SEARCH_QUERY = "software engineer intern"
DEFAULT_INCLUDE_KEYWORDS = ["software", "engineer", "intern"]
DEFAULT_EXCLUDE_KEYWORDS: list[str] = []
DEFAULT_PREFERRED_LOCATIONS: list[str] = []
DEFAULT_FILTER_REMOTE_ONLY = False
DEFAULT_FILTER_MAX_DISCOVERED = 150

DEFAULT_APP_DRY_RUN = True
DEFAULT_APP_AUTO_SUBMIT = False
DEFAULT_APP_MAX_APPLICATIONS = 25
DEFAULT_APP_PAUSE_BETWEEN_SEC = 2
DEFAULT_APP_SAVE_HTML_ON_FAILURE = True

DEFAULT_RESUME_MODE = "markdown_template"
DEFAULT_RESUME_BASE_PATH = "artifacts/base_resume.txt"
DEFAULT_RESUME_TEMPLATE_PATH = "config/resume_template.md"
DEFAULT_RESUME_OUTPUT_DIR = "artifacts/resumes"

DEFAULT_LLM_ENABLED = True
DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_LLM_API_KEY_ENV = "OPENAI_API_KEY"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_LLM_TEMPERATURE = 0.2

DEFAULT_QA_DEFAULTS_PATH = "config/qa_defaults.yaml"
DEFAULT_QA_MAX_ANSWER_CHARS = 1000


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


@dataclass(slots=True)
class HandshakeConfig:
    email: str
    password: str
    login_url: str = DEFAULT_HANDSHAKE_LOGIN_URL
    jobs_url: str = DEFAULT_HANDSHAKE_JOBS_URL


@dataclass(slots=True)
class BrowserConfig:
    headless: bool = DEFAULT_BROWSER_HEADLESS
    slow_mo_ms: int = DEFAULT_BROWSER_SLOW_MO_MS
    timeout_ms: int = DEFAULT_BROWSER_TIMEOUT_MS


@dataclass(slots=True)
class FilterConfig:
    search_query: str = DEFAULT_FILTER_SEARCH_QUERY
    include_keywords: list[str] = field(
        default_factory=lambda: list(DEFAULT_INCLUDE_KEYWORDS)
    )
    exclude_keywords: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE_KEYWORDS))
    preferred_locations: list[str] = field(
        default_factory=lambda: list(DEFAULT_PREFERRED_LOCATIONS)
    )
    remote_only: bool = DEFAULT_FILTER_REMOTE_ONLY
    max_discovered_jobs: int = DEFAULT_FILTER_MAX_DISCOVERED


@dataclass(slots=True)
class ApplicationConfig:
    dry_run: bool = DEFAULT_APP_DRY_RUN
    auto_submit: bool = DEFAULT_APP_AUTO_SUBMIT
    max_applications: int = DEFAULT_APP_MAX_APPLICATIONS
    pause_between_apps_sec: int = DEFAULT_APP_PAUSE_BETWEEN_SEC
    save_html_on_failure: bool = DEFAULT_APP_SAVE_HTML_ON_FAILURE


@dataclass(slots=True)
class ResumeConfig:
    mode: str = DEFAULT_RESUME_MODE
    base_resume_path: str = DEFAULT_RESUME_BASE_PATH
    template_path: str = DEFAULT_RESUME_TEMPLATE_PATH
    output_dir: str = DEFAULT_RESUME_OUTPUT_DIR


@dataclass(slots=True)
class LLMConfig:
    enabled: bool = DEFAULT_LLM_ENABLED
    provider: str = DEFAULT_LLM_PROVIDER
    api_key_env: str = DEFAULT_LLM_API_KEY_ENV
    model: str = DEFAULT_LLM_MODEL
    temperature: float = DEFAULT_LLM_TEMPERATURE


@dataclass(slots=True)
class QAConfig:
    defaults_path: str = DEFAULT_QA_DEFAULTS_PATH
    max_answer_chars: int = DEFAULT_QA_MAX_ANSWER_CHARS


@dataclass(slots=True)
class AutomationConfig:
    handshake: HandshakeConfig
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    application: ApplicationConfig = field(default_factory=ApplicationConfig)
    resume: ResumeConfig = field(default_factory=ResumeConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    qa: QAConfig = field(default_factory=QAConfig)


def load_config(config_path: str | Path) -> AutomationConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    raw = yaml.safe_load(path.read_text()) or {}
    if "handshake" not in raw:
        raise ValueError("Missing required section: handshake")

    hs = raw["handshake"] or {}
    if not hs.get("email") or not hs.get("password"):
        raise ValueError("handshake.email and handshake.password are required")

    browser = raw.get("browser", {}) or {}
    filters = raw.get("filters", {}) or {}
    application = raw.get("application", {}) or {}
    resume = raw.get("resume", {}) or {}
    llm = raw.get("llm", {}) or {}
    qa = raw.get("qa", {}) or {}

    return AutomationConfig(
        handshake=HandshakeConfig(
            email=str(hs["email"]),
            password=str(hs["password"]),
            login_url=str(hs.get("login_url", DEFAULT_HANDSHAKE_LOGIN_URL)),
            jobs_url=str(hs.get("jobs_url", DEFAULT_HANDSHAKE_JOBS_URL)),
        ),
        browser=BrowserConfig(
            headless=bool(browser.get("headless", DEFAULT_BROWSER_HEADLESS)),
            slow_mo_ms=int(browser.get("slow_mo_ms", DEFAULT_BROWSER_SLOW_MO_MS)),
            timeout_ms=int(browser.get("timeout_ms", DEFAULT_BROWSER_TIMEOUT_MS)),
        ),
        filters=FilterConfig(
            search_query=str(filters.get("search_query", DEFAULT_FILTER_SEARCH_QUERY)),
            include_keywords=_as_list(
                filters.get("include_keywords", DEFAULT_INCLUDE_KEYWORDS)
            ),
            exclude_keywords=_as_list(
                filters.get("exclude_keywords", DEFAULT_EXCLUDE_KEYWORDS)
            ),
            preferred_locations=_as_list(
                filters.get("preferred_locations", DEFAULT_PREFERRED_LOCATIONS)
            ),
            remote_only=bool(filters.get("remote_only", DEFAULT_FILTER_REMOTE_ONLY)),
            max_discovered_jobs=int(
                filters.get("max_discovered_jobs", DEFAULT_FILTER_MAX_DISCOVERED)
            ),
        ),
        application=ApplicationConfig(
            dry_run=bool(application.get("dry_run", DEFAULT_APP_DRY_RUN)),
            auto_submit=bool(application.get("auto_submit", DEFAULT_APP_AUTO_SUBMIT)),
            max_applications=int(application.get("max_applications", DEFAULT_APP_MAX_APPLICATIONS)),
            pause_between_apps_sec=int(
                application.get(
                    "pause_between_apps_sec", DEFAULT_APP_PAUSE_BETWEEN_SEC
                )
            ),
            save_html_on_failure=bool(
                application.get(
                    "save_html_on_failure", DEFAULT_APP_SAVE_HTML_ON_FAILURE
                )
            ),
        ),
        resume=ResumeConfig(
            mode=str(resume.get("mode", DEFAULT_RESUME_MODE)),
            base_resume_path=str(resume.get("base_resume_path", DEFAULT_RESUME_BASE_PATH)),
            template_path=str(resume.get("template_path", DEFAULT_RESUME_TEMPLATE_PATH)),
            output_dir=str(resume.get("output_dir", DEFAULT_RESUME_OUTPUT_DIR)),
        ),
        llm=LLMConfig(
            enabled=bool(llm.get("enabled", DEFAULT_LLM_ENABLED)),
            provider=str(llm.get("provider", DEFAULT_LLM_PROVIDER)),
            api_key_env=str(llm.get("api_key_env", DEFAULT_LLM_API_KEY_ENV)),
            model=str(llm.get("model", DEFAULT_LLM_MODEL)),
            temperature=float(llm.get("temperature", DEFAULT_LLM_TEMPERATURE)),
        ),
        qa=QAConfig(
            defaults_path=str(qa.get("defaults_path", DEFAULT_QA_DEFAULTS_PATH)),
            max_answer_chars=int(qa.get("max_answer_chars", DEFAULT_QA_MAX_ANSWER_CHARS)),
        ),
    )
