from app.domain.matching import match_app, normalize_name


def test_normalization_handles_case_punctuation_and_whitespace():
    assert normalize_name("  Google-Chrome__  ") == "google chrome"
    assert normalize_name("Ｆｉｌｅ　Explorer") == "file explorer"


def test_application_matching_normalizes_traditional_and_simplified_chinese():
    from app.domain.app_models import AppEntry, AppType, LaunchMethod, LaunchSource, ProcessSpec

    app = AppEntry(
        app_id="app_netease_music_12345678",
        display_name="網易雲音樂",
        normalized_name="網易雲音樂",
        aliases=("百度網盤",),
        launch_method=LaunchMethod.EXECUTABLE,
        launch_target="C:\\Apps\\music.exe",
        executable_path="C:\\Apps\\music.exe",
        process=ProcessSpec(executable_names=("music.exe",), reliable=True),
        source="manual_apps",
        app_type=AppType.PORTABLE,
        launch_source=LaunchSource.MANUAL,
        launch_confidence=1.0,
        metadata_confidence=1.0,
    )

    assert match_app("网易云音乐", [app]).best_match is not None
    assert match_app("百度网盘", [app]).best_match is not None


def test_alias_and_fuzzy_matching(sample_entries):
    result = match_app("photoshop", sample_entries)
    assert result.best_match is not None
    assert result.best_match.display_name == "Adobe Photoshop 2026"
    assert result.best_match.matched_by == "exact_alias"


def test_chinese_builtin_alias_is_supported(sample_entries):
    from app.domain.app_models import AppType, AppEntry, LaunchMethod, LaunchSource

    task_manager = AppEntry(
        app_id="app_task_manager_12345678",
        display_name="Task Manager",
        normalized_name="task manager",
        aliases=("工作管理員",),
        launch_method=LaunchMethod.EXECUTABLE,
        launch_target="taskmgr.exe",
        source="system_apps",
        app_type=AppType.SYSTEM,
        confidence=0.99,
        launch_source=LaunchSource.TRUSTED,
        launch_confidence=0.99,
        metadata_confidence=0.99,
    )
    result = match_app("工作管理員", [task_manager])
    assert result.best_match and result.best_match.display_name == "Task Manager"


def test_visual_studio_prefix_is_ambiguous(sample_entries):
    result = match_app("Visual Studio", sample_entries)
    assert result.ambiguous is True
    assert result.best_match is None
    assert {candidate.display_name for candidate in result.candidates} >= {"Visual Studio 2026", "Visual Studio Code"}


def test_same_name_apps_prefer_a_direct_executable(sample_entries):
    direct = sample_entries[0].model_copy(
        update={
            "app_id": "app_discord_direct_12345678",
            "display_name": "Discord",
            "normalized_name": "discord",
            "aliases": ("discord",),
            "launch_target": "C:\\Users\\tester\\AppData\\Local\\Discord\\Discord.exe",
            "executable_path": "C:\\Users\\tester\\AppData\\Local\\Discord\\Discord.exe",
            "source": "start_menu_shortcuts",
        }
    )
    updater = direct.model_copy(
        update={
            "app_id": "app_discord_updater_12345678",
            "launch_target": "C:\\Users\\tester\\AppData\\Local\\Discord\\Update.exe",
            "executable_path": "C:\\Users\\tester\\AppData\\Local\\Discord\\Update.exe",
        }
    )

    result = match_app("Discord", [direct, updater])

    assert result.ambiguous is False
    assert result.best_match is not None
    assert result.best_match.app_id == "app_discord_direct_12345678"


def test_builtin_alias_beats_packaged_same_name_entry():
    from app.domain.app_models import AppType, AppEntry, LaunchMethod, LaunchSource, ProcessSpec

    notepad = AppEntry(
        app_id="app_notepad_system_12345678",
        display_name="Notepad",
        normalized_name="notepad",
        aliases=("記事本",),
        launch_method=LaunchMethod.EXECUTABLE,
        launch_target="C:\\Windows\\System32\\notepad.exe",
        executable_path="C:\\Windows\\System32\\notepad.exe",
        process=ProcessSpec(executable_names=("notepad.exe",), reliable=True),
        source="system_apps",
        app_type=AppType.SYSTEM,
        confidence=0.99,
        launch_source=LaunchSource.TRUSTED,
        launch_confidence=0.99,
        metadata_confidence=0.99,
    )
    packaged = AppEntry(
        app_id="app_notepad_packaged_12345678",
        display_name="記事本",
        normalized_name="記事本",
        launch_method=LaunchMethod.SHELL_URI,
        launch_target="shell:AppsFolder\\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App",
        source="apps_folder",
        app_type=AppType.PACKAGED,
        confidence=0.94,
        launch_source=LaunchSource.TRUSTED,
        launch_confidence=0.94,
        metadata_confidence=0.9,
    )

    result = match_app("記事本", [notepad, packaged])

    assert result.ambiguous is False
    assert result.best_match is not None
    assert result.best_match.app_id == "app_notepad_system_12345678"


def test_metadata_only_entry_is_not_launchable(sample_entries):
    metadata = next(item for item in sample_entries if item.display_name == "Installed Only")
    assert metadata.launchable is False
