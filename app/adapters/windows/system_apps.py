"""Fixed, well-known Windows application entry points.

These are the only executable-like targets intentionally known by the source
code.  Third-party applications still come from local discovery or manual_apps.
"""

from __future__ import annotations

import hashlib
import shutil

from app.domain.app_models import AppEntry, AppType, LaunchMethod, LaunchSource, ProcessSpec
from app.domain.matching import aliases_for, normalize_name


SYSTEM_APP_DEFINITIONS: tuple[dict[str, object], ...] = (
    {"name": "Task Manager", "aliases": ("task manager", "工作管理員"), "method": LaunchMethod.EXECUTABLE, "target": "taskmgr.exe", "process": ("taskmgr.exe",)},
    {"name": "File Explorer", "aliases": ("file explorer", "檔案總管", "文件總管"), "method": LaunchMethod.EXECUTABLE, "target": "explorer.exe", "process": ("explorer.exe",)},
    {"name": "Settings", "aliases": ("settings", "設定", "windows 設定"), "method": LaunchMethod.SHELL_URI, "target": "ms-settings:", "process": ("systemsettings.exe",)},
    {"name": "Control Panel", "aliases": ("control panel", "控制台"), "method": LaunchMethod.EXECUTABLE, "target": "control.exe", "process": ("control.exe",)},
    {"name": "Calculator", "aliases": ("calculator", "計算機", "小算盤"), "method": LaunchMethod.EXECUTABLE, "target": "calc.exe", "process": ("calculatorapp.exe", "calc.exe")},
    {"name": "Notepad", "aliases": ("notepad", "記事本"), "method": LaunchMethod.EXECUTABLE, "target": "notepad.exe", "process": ("notepad.exe",)},
    {"name": "Windows Terminal", "aliases": ("windows terminal", "terminal", "終端機", "wt"), "method": LaunchMethod.EXECUTABLE, "target": "wt.exe", "process": ("wt.exe", "windowsterminal.exe")},
    {"name": "Command Prompt", "aliases": ("command prompt", "cmd", "命令提示字元"), "method": LaunchMethod.EXECUTABLE, "target": "cmd.exe", "process": ("cmd.exe",)},
    {"name": "Windows PowerShell", "aliases": ("powershell", "windows powershell", "PowerShell"), "method": LaunchMethod.EXECUTABLE, "target": "powershell.exe", "process": ("powershell.exe",)},
    {"name": "Snipping Tool", "aliases": ("snipping tool", "剪取工具"), "method": LaunchMethod.SHELL_URI, "target": "ms-screenclip:", "process": ("snippingtool.exe",)},
    {"name": "Paint", "aliases": ("paint", "小畫家"), "method": LaunchMethod.EXECUTABLE, "target": "mspaint.exe", "process": ("mspaint.exe",)},
    {"name": "Device Manager", "aliases": ("device manager", "裝置管理員"), "method": LaunchMethod.SHELL_EXECUTE, "target": "devmgmt.msc", "process": ("mmc.exe",)},
    {"name": "Services", "aliases": ("services", "服務"), "method": LaunchMethod.SHELL_EXECUTE, "target": "services.msc", "process": ("mmc.exe",)},
    {"name": "Event Viewer", "aliases": ("event viewer", "事件檢視器"), "method": LaunchMethod.SHELL_EXECUTE, "target": "eventvwr.msc", "process": ("mmc.exe",)},
    {"name": "Disk Management", "aliases": ("disk management", "磁碟管理"), "method": LaunchMethod.SHELL_EXECUTE, "target": "diskmgmt.msc", "process": ("mmc.exe",)},
    {"name": "Task Scheduler", "aliases": ("task scheduler", "工作排程器"), "method": LaunchMethod.SHELL_EXECUTE, "target": "taskschd.msc", "process": ("mmc.exe",)},
)


def stable_app_id(source: str, display_name: str, target: str | None) -> str:
    raw = f"{source}|{normalize_name(display_name)}|{target or ''}".encode("utf-8")
    return "app_" + hashlib.sha256(raw).hexdigest()[:24]


def system_app_entries() -> list[AppEntry]:
    entries: list[AppEntry] = []
    for item in SYSTEM_APP_DEFINITIONS:
        name = str(item["name"])
        target = str(item["target"])
        method = item["method"]
        resolved_target = shutil.which(target) if method is LaunchMethod.EXECUTABLE else None
        launch_target = resolved_target or target
        aliases = aliases_for(name, tuple(str(value) for value in item.get("aliases", ())))
        process_names = tuple(str(value).casefold() for value in item.get("process", ()))
        entries.append(
            AppEntry(
                app_id=stable_app_id("system_apps", name, launch_target),
                display_name=name,
                normalized_name=normalize_name(name),
                aliases=aliases,
                launch_method=method,
                launch_target=launch_target,
                executable_path=launch_target if method is LaunchMethod.EXECUTABLE else None,
                process=ProcessSpec(executable_names=process_names, reliable=bool(process_names)),
                source="system_apps",
                app_type=AppType.SYSTEM,
                confidence=0.99,
                launch_source=LaunchSource.TRUSTED,
                launch_confidence=0.99,
                metadata_confidence=0.99,
            )
        )
    return entries
