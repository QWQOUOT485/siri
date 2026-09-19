from pathlib import Path


def test_start_script_uses_configured_port_in_status_and_error_text():
    script = (Path(__file__).parents[2] / "scripts" / "start.bat").read_text(encoding="utf-8")

    assert 'set "AGENT_PORT=8000"' in script
    assert "SIRI_AGENT_PORT" in script
    assert "http://0.0.0.0:%AGENT_PORT%" in script
    assert "port %AGENT_PORT%" in script
