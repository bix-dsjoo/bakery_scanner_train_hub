import os
import subprocess
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
START_DEV_SCRIPT = REPOSITORY_ROOT / "start-dev.ps1"


def test_alembic_head_prepares_fresh_catalog_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "fresh-data"
    monkeypatch.setenv("BAKERY_DATA_DIR", str(data_dir))
    monkeypatch.delenv("BAKERY_DATABASE_URL", raising=False)

    command.upgrade(Config(REPOSITORY_ROOT / "alembic.ini"), "head")

    with TestClient(create_app(Settings(data_dir=data_dir))) as client:
        response = client.post(
            "/api/v1/brands", json={"name": "Fresh Bakery"}
        )

    assert response.status_code == 201
    assert response.json()["name"] == "Fresh Bakery"


def _write_command_shims(
    shim_dir: Path, migration_exit_code: int
) -> Path:
    event_log = shim_dir / "events.log"
    shim_dir.mkdir()
    (shim_dir / "uv.cmd").write_text(
        "\r\n".join(
            (
                "@echo off",
                '>>"%BAKERY_START_DEV_TEST_LOG%" echo uv %*',
                'if "%1"=="run" if "%2"=="alembic" '
                f"exit /b {migration_exit_code}",
                "exit /b 0",
            )
        ),
        encoding="utf-8",
    )
    (shim_dir / "node.cmd").write_text(
        "@echo off\r\necho v24.18.0\r\nexit /b 0\r\n",
        encoding="utf-8",
    )
    (shim_dir / "npm.cmd").write_text(
        "\r\n".join(
            (
                "@echo off",
                '>>"%BAKERY_START_DEV_TEST_LOG%" echo npm %*',
                "exit /b 0",
            )
        ),
        encoding="utf-8",
    )
    return event_log


def _run_start_dev(shim_dir: Path, event_log: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PATH"] = f"{shim_dir}{os.pathsep}{environment['PATH']}"
    environment["BAKERY_START_DEV_TEST_LOG"] = str(event_log)
    command_text = (
        "$OutputEncoding = [Console]::OutputEncoding = "
        "[Text.UTF8Encoding]::new(); "
        f"& '{START_DEV_SCRIPT}'"
    )
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command_text,
        ],
        cwd=shim_dir,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )


@pytest.mark.skipif(os.name != "nt", reason="PowerShell 실행 계약은 Windows 전용입니다.")
def test_start_dev_migrates_after_install_and_before_starting_servers(
    tmp_path: Path,
) -> None:
    shim_dir = tmp_path / "commands"
    event_log = _write_command_shims(shim_dir, migration_exit_code=0)

    result = _run_start_dev(shim_dir, event_log)
    events = event_log.read_text(encoding="utf-8").splitlines()

    sync_index = events.index("uv sync")
    install_index = events.index(f"npm --prefix {REPOSITORY_ROOT / 'frontend'} install")
    migration_index = events.index("uv run alembic upgrade head")
    api_index = next(
        index for index, event in enumerate(events) if event.startswith("uv run uvicorn ")
    )
    frontend_index = next(
        index for index, event in enumerate(events) if event.startswith("npm run dev ")
    )

    assert result.returncode != 0
    assert sync_index < migration_index
    assert install_index < migration_index
    assert migration_index < api_index
    assert migration_index < frontend_index


@pytest.mark.skipif(os.name != "nt", reason="PowerShell 실행 계약은 Windows 전용입니다.")
def test_start_dev_stops_with_actionable_message_when_migration_fails(
    tmp_path: Path,
) -> None:
    shim_dir = tmp_path / "commands"
    event_log = _write_command_shims(shim_dir, migration_exit_code=17)

    result = _run_start_dev(shim_dir, event_log)
    events = event_log.read_text(encoding="utf-8").splitlines()
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "uv run alembic upgrade head" in events
    assert not any("uvicorn" in event for event in events)
    assert not any("npm run dev" in event for event in events)
    assert "데이터베이스" in output
    assert "Alembic 오류 메시지" in output
    assert "다시 실행" in output
