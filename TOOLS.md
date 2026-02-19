# TOOLS.md

## OpenClaw Runtime

- Setup: `./scripts/openclaw_setup.sh`
- Gateway status: `openclaw gateway status`
- Browser profile status: `openclaw browser --browser-profile openclaw status`
- Skill eligibility: `openclaw skills list --eligible`

## Handshake Autopilot Helpers

- Run autopilot:
  - Dry-run: `./scripts/openclaw_apply_handshake.sh 25 dry-run`
  - Live: `./scripts/openclaw_apply_handshake.sh 25 live`
- Build tailored resume:
  - `python3 scripts/build_resume_for_job.py --help`
- Answer one application question:
  - `python3 scripts/answer_application_question.py --help`

