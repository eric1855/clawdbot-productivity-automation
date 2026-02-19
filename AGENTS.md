# AGENTS.md

Workspace mission: operate OpenClaw/clawDBot to automatically apply to Handshake SWE internships.

## Startup Checklist

On each run, read:

1. `config/application.yaml`
2. `config/qa_defaults.yaml`
3. `config/resume_template.md`
4. `skills/handshake-internship-autopilot/SKILL.md`

## Execution Policy

- OpenClaw-first only: use `openclaw agent` + OpenClaw `browser` tool flow.
- Keep browser profile `openclaw`; never use personal browser profiles.
- Login is manual if SSO/2FA appears. Pause and wait.
- Generate one tailored resume per target role before applying.
- Use defaults from `config/qa_defaults.yaml` for recurring form questions.
- Be truthful. Never invent work authorization, GPA, or experience.
- Respect run mode:
  - `application.dry_run: true` or `application.auto_submit: false`: do not click final submit.
  - `application.dry_run: false` and `application.auto_submit: true`: submit completed applications.

## Safety

- Ask before answering ambiguous legal/eligibility prompts.
- Skip roles that violate configured filters.
- Record outputs under `artifacts/` only.
- Save run outcomes to `artifacts/application_results.jsonl`.

