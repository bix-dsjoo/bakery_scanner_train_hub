from pathlib import Path
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BAKERY_", case_sensitive=False)

    data_dir: Path = Path(r"C:\BakeryScannerData")
    database_url: str = ""

    @model_validator(mode="after")
    def set_default_database_url(self) -> Self:
        if not self.database_url:
            self.database_url = f"sqlite:///{self.database_path.as_posix()}"
        return self

    @property
    def database_path(self) -> Path:
        return self.data_dir / "database" / "app.db"

    @property
    def originals_dir(self) -> Path:
        return self.data_dir / "originals"

    @property
    def thumbnails_dir(self) -> Path:
        return self.data_dir / "thumbnails"

    @property
    def imports_dir(self) -> Path:
        return self.data_dir / "imports"

    @property
    def trash_dir(self) -> Path:
        return self.data_dir / "trash"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def storage_directories(self) -> tuple[Path, ...]:
        return (
            self.database_path.parent,
            self.originals_dir,
            self.thumbnails_dir,
            self.imports_dir,
            self.trash_dir,
            self.logs_dir,
        )
