import pytest
from pydantic import ValidationError

from app.api.schemas import ActionRequest
from app.domain.actions import ActionName, ValidatedAction


def test_action_schema_has_no_shell_or_path_escape_hatches():
    with pytest.raises(ValidationError):
        ActionRequest(action=ActionName.OPEN_APP, app_name=r"C:\Windows\System32\cmd.exe")
    with pytest.raises(ValidationError):
        ActionRequest(action=ActionName.OPEN_WEBSITE, website_name="https://evil.example")
    with pytest.raises(ValidationError):
        ActionRequest(action=ActionName.OPEN_APP, app_name="Discord", command="whoami")
    with pytest.raises(ValidationError):
        ValidatedAction(action=ActionName.OPEN_APP, app_query="Discord", executable_path="C:\\bad.exe")
    with pytest.raises(ValidationError):
        ActionRequest(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay", track_uri="spotify:track:client_supplied")
    with pytest.raises(ValidationError):
        ActionRequest(action="media_play", app_name="ignored")
