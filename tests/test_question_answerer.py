from pathlib import Path

from clawdbot_internship_automation.models import JobPosting
from clawdbot_internship_automation.question_answerer import QuestionAnswerer
from clawdbot_internship_automation.settings import QAConfig


class _NoLLM:
    enabled = False

    def answer_application_question(self, **kwargs):
        return kwargs.get("default_answer", "")


def test_alias_answer(tmp_path: Path) -> None:
    defaults_file = tmp_path / "qa_defaults.yaml"
    defaults_file.write_text(
        """
defaults:
  work_authorization_us: "Yes"
prompt_aliases:
  - key: "work_authorization_us"
    patterns:
      - "authorized to work"
        """.strip()
    )
    qa = QuestionAnswerer(
        qa_config=QAConfig(defaults_path=str(defaults_file)),
        llm=_NoLLM(),  # type: ignore[arg-type]
    )
    job = JobPosting(job_id="1", title="SWE Intern")
    answer = qa.answer("Are you legally authorized to work in the US?", "radio", job, ["Yes", "No"])
    assert answer == "Yes"
