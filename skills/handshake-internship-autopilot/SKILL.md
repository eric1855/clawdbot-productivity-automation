---
name: handshake-internship-autopilot
description: End-to-end Handshake SWE internship application workflow using OpenClaw browser automation with tailored resumes and QA defaults.
metadata: {"openclaw":{"emoji":"🎯","requires":{"bins":["python3"],"config":["browser.enabled"]}}}
---

# Handshake Internship Autopilot (OpenClaw)

Use this skill when the user asks to find/apply to Handshake internship roles.

## Primary Flow

1. Load and obey:
   - `config/application.yaml`
   - `config/qa_defaults.yaml`
   - `config/resume_template.md`
2. Use `browser` tool on profile `openclaw`.
3. Open Handshake login page and pause for manual SSO/2FA completion.
4. Discover SWE internship roles using filters in `config/application.yaml`.
5. For each role, generate a tailored resume:

```bash
./.venv/bin/python scripts/build_resume_for_job.py --config config/application.yaml --job-id <id> --title <title> --company <company> --location <location> --description-file <path> --json
```

6. For each application question, answer with defaults + optional LLM:

```bash
./.venv/bin/python scripts/answer_application_question.py --config config/application.yaml --prompt "<question>" --input-type "<type>" --choices "<option1|option2|...>" --title "<job title>" --company "<company>"
```

7. Respect run mode from `config/application.yaml`:
   - if `application.dry_run: true` OR `application.auto_submit: false`: stop before final submit
   - if `application.dry_run: false` AND `application.auto_submit: true`: submit

## Hard Rules

- Never fabricate eligibility/work authorization data.
- If a prompt asks for unknown personal/legal information, ask the user.
- Keep applications truthful; do not invent experience.
- Record outcomes in `artifacts/application_results.jsonl`.

## Reporting Format

At the end of each run, report:
- jobs discovered
- jobs attempted
- jobs submitted
- jobs skipped + reason
- resume file paths created for each attempted job
