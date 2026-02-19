#!/usr/bin/env bash
set -euo pipefail

MAX_APPLICATIONS="${1:-25}"
MODE="${2:-dry-run}" # dry-run | live

if [[ "$MODE" != "dry-run" && "$MODE" != "live" ]]; then
  echo "Usage: $0 [max_applications] [dry-run|live]"
  exit 1
fi

if ! command -v openclaw >/dev/null 2>&1; then
  echo "openclaw is not installed. Run: ./scripts/openclaw_setup.sh"
  exit 1
fi

AUTH_FILE="${OPENCLAW_STATE_DIR:-$HOME/.openclaw}/agents/main/agent/auth-profiles.json"
if [[ ! -f "$AUTH_FILE" ]]; then
  echo "OpenClaw model auth is not configured for agent 'main'."
  echo "Run:"
  echo "  export OPENAI_API_KEY=YOUR_KEY"
  echo "  openclaw onboard --auth-choice openai-api-key --openai-api-key \"\$OPENAI_API_KEY\""
  exit 1
fi

openclaw gateway start >/dev/null 2>&1 || true
openclaw browser start --browser-profile openclaw >/dev/null 2>&1 || true

SAFETY_NOTE="Stop before final submit and report ready_to_submit state."
if [[ "$MODE" == "live" ]]; then
  SAFETY_NOTE="Submit applications when all required fields are complete."
fi

read -r -d '' PROMPT <<EOF || true
Use the handshake-internship-autopilot skill now.

Goal:
- Find and apply to Software Engineering Internship roles on Handshake.
- Apply to at most ${MAX_APPLICATIONS} jobs this run.

Required config files:
- config/application.yaml
- config/qa_defaults.yaml
- config/resume_template.md

Execution rules:
- Use the OpenClaw browser tool with profile openclaw.
- If redirected to SSO/2FA (Duo), pause and ask the user to complete login manually.
- For each target job, generate a tailored resume by running:
  ./.venv/bin/python scripts/build_resume_for_job.py --config config/application.yaml --job-id <id> --title <title> --company <company> --location <location> --description-file <path> --json
- For each application question, answer via:
  ./.venv/bin/python scripts/answer_application_question.py --config config/application.yaml --prompt "<question>" --input-type "<type>" --choices "<pipe-separated-options>" --title "<job title>" --company "<company>"
- Keep answers truthful and use config defaults when uncertain.
- ${SAFETY_NOTE}

At the end, output:
- jobs discovered
- jobs attempted
- jobs submitted
- jobs skipped (with reason)
- file paths for generated resumes
EOF

openclaw agent --agent main --message "$PROMPT" --thinking medium
