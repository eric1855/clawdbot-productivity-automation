from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(slots=True)
class JobPosting:
    job_id: str
    title: str
    company: str = ""
    location: str = ""
    description: str = ""
    url: str = ""


@dataclass(slots=True)
class ApplicationQuestion:
    prompt: str
    input_type: str
    required: bool = False
    choices: List[str] = field(default_factory=list)


@dataclass(slots=True)
class ApplicationResult:
    job_id: str
    title: str
    company: str
    url: str
    status: str
    reason: str = ""

