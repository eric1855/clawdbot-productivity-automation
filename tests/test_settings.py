from pathlib import Path

from clawdbot_internship_automation.settings import load_config


def test_load_config(tmp_path: Path) -> None:
    config_file = tmp_path / "application.yaml"
    config_file.write_text(
        """
handshake:
  email: "test@example.com"
  password: "secret"
application:
  dry_run: true
  max_applications: 7
        """.strip()
    )
    config = load_config(config_file)
    assert config.handshake.email == "test@example.com"
    assert config.application.dry_run is True
    assert config.application.max_applications == 7

