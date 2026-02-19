from __future__ import annotations

import re
import shutil
import textwrap
from pathlib import Path
from string import Template

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from .llm import LLMClient
from .models import JobPosting
from .settings import QAConfig, ResumeConfig


def _safe_slug(value: str, limit: int = 60) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return cleaned[:limit] or "job"


def _markdown_to_plain_text(markdown: str) -> str:
    text = re.sub(r"^#+\s*", "", markdown, flags=re.MULTILINE)
    text = re.sub(r"[*_`>-]", "", text)
    return text.strip()


class ResumeBuilder:
    def __init__(self, config: ResumeConfig, qa_config: QAConfig, llm: LLMClient):
        self.config = config
        self.qa_config = qa_config
        self.llm = llm

    def build(
        self,
        job: JobPosting,
        defaults: dict[str, str],
        base_resume_text: str,
    ) -> Path:
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        slug = _safe_slug(f"{job.company}-{job.title}-{job.job_id}")

        if self.config.mode == "copy_pdf":
            src = Path(self.config.base_resume_path)
            if src.suffix.lower() != ".pdf":
                raise ValueError("resume.mode=copy_pdf requires a .pdf base_resume_path")
            target = output_dir / f"{slug}.pdf"
            shutil.copyfile(src, target)
            return target

        template_path = Path(self.config.template_path)
        if not template_path.exists():
            raise FileNotFoundError(f"Resume template not found: {template_path}")

        template_text = template_path.read_text()
        sections = self.llm.generate_resume_sections(job, base_resume_text)
        rendered_markdown = Template(template_text).safe_substitute(
            FULL_NAME=defaults.get("full_name", ""),
            EMAIL=defaults.get("email", ""),
            PHONE=defaults.get("phone", ""),
            LINKEDIN=defaults.get("linkedin", ""),
            GITHUB=defaults.get("github", ""),
            ROLE=job.title,
            COMPANY=job.company,
            GRADUATION_MONTH_YEAR=defaults.get("graduation_month_year", ""),
            SUMMARY=sections["summary"],
            TOP_SKILLS="\n".join(f"- {skill}" for skill in sections["top_skills"]),
            EXPERIENCE_HIGHLIGHTS="\n".join(
                f"- {item}" for item in sections["experience_highlights"]
            ),
        )

        md_path = output_dir / f"{slug}.md"
        pdf_path = output_dir / f"{slug}.pdf"
        md_path.write_text(rendered_markdown)
        self._render_pdf(_markdown_to_plain_text(rendered_markdown), pdf_path)
        return pdf_path

    @staticmethod
    def _render_pdf(text: str, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(output_path), pagesize=LETTER)
        width, height = LETTER
        margin = 48
        y = height - margin
        line_height = 14

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                y -= line_height
                if y < margin:
                    c.showPage()
                    y = height - margin
                continue

            wrapped = textwrap.wrap(line, width=95) or [""]
            for segment in wrapped:
                c.drawString(margin, y, segment)
                y -= line_height
                if y < margin:
                    c.showPage()
                    y = height - margin

        c.save()

