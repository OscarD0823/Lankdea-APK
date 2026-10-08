import sys
from pathlib import Path

from scripts import build_windows


def test_pyinstaller_assets_are_absolute_when_spec_is_in_build(tmp_path, monkeypatch):
    monkeypatch.setattr(build_windows, "ROOT", tmp_path)
    monkeypatch.setattr(build_windows, "INSTALLERS_ROOT", tmp_path / "installers")
    monkeypatch.setattr(build_windows, "source_commit", lambda: "a" * 40)
    monkeypatch.setattr(build_windows, "project_version", lambda: "3.5.0")
    monkeypatch.setattr(sys, "argv", ["build_windows", "--iscc", __file__])
    commands = []
    def run(command, **_kwargs):
        commands.append(command)
        if len(commands) == 1:
            output = tmp_path / "dist/Lankdea-PC.exe"
        else:
            output = tmp_path / "installers/windows/Lankdea-3.5.0-Instalador-Windows-x64.exe"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"MZdummy-test")
    monkeypatch.setattr(build_windows.subprocess, "run", run)
    build_windows.main()
    command = commands[0]
    assert command[command.index("--specpath") + 1] == "build"
    assert Path(command[command.index("--icon") + 1]).is_absolute()
    for index, arg in enumerate(command):
        if arg == "--add-data":
            assert Path(command[index + 1].split(";", 1)[0]).is_absolute()
    assert command[-1] == str(tmp_path / "main.py")
