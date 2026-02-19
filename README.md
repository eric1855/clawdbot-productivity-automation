# clawdbot OpenClaw Handshake Autopilot

This project is now OpenClaw-native.

Primary runtime path:

- `openclaw` gateway
- `openclaw agent` orchestration
- OpenClaw `browser` tool for Handshake flow
- Workspace skill: `skills/handshake-internship-autopilot/SKILL.md`

## What This Does

- Uses OpenClaw/clawDBot to find SWE internship postings on Handshake.
- Builds a tailored resume per role.
- Answers common application questions from your defaults.
- Runs in dry-run or live-submit mode.

## 1. Prerequisites

- Node 22+
- Python 3.11+ (for helper scripts)
- Handshake account
- OpenAI API key (optional but recommended for better tailoring)

## 2. One-Time Setup

```bash
./scripts/openclaw_setup.sh
```

This installs/configures OpenClaw, sets this folder as workspace, enables browser automation, and starts the gateway.

## 3. Configure Your Profile

```bash
cp config/application.example.yaml config/application.yaml
cp config/qa_defaults.example.yaml config/qa_defaults.yaml
cp config/resume_template.example.md config/resume_template.md
```

Edit:

- `config/application.yaml`
- `config/qa_defaults.yaml`
- `config/resume_template.md`

Add base resume text:

```bash
mkdir -p artifacts
touch artifacts/base_resume.txt
```

Optional for LLM tailoring:

```bash
export OPENAI_API_KEY=YOUR_KEY
openclaw onboard --auth-choice openai-api-key --openai-api-key "$OPENAI_API_KEY"
```

## 4. Run Through OpenClaw

Dry-run (recommended first):

```bash
./scripts/openclaw_apply_handshake.sh 25 dry-run
```

Live submit:

```bash
./scripts/openclaw_apply_handshake.sh 25 live
```

## 5. Manual Login Behavior

When Handshake redirects to school SSO/Duo:

- Complete login manually in the OpenClaw browser window.
- Keep the browser open while automation continues.

## Outputs

- Tailored resumes: `artifacts/resumes/`
- Application outcomes: `artifacts/application_results.jsonl`
- Failure HTML captures (if enabled): `artifacts/failures/`

## Notes

- Keep answers truthful for legal/eligibility prompts.
- Start in dry-run mode before enabling live submissions.
- OpenClaw/browser selectors may need minor tuning if Handshake UI changes.
