from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def register_spa_routes(app: FastAPI, dist_dir: Path) -> None:
    dist_root = dist_dir.resolve()
    index_path = dist_root / "index.html"

    @app.get("/{requested_path:path}", include_in_schema=False)
    def serve_spa(requested_path: str) -> FileResponse:
        if requested_path == "api" or requested_path.startswith("api/"):
            raise HTTPException(status_code=404)

        requested_file = (dist_root / requested_path).resolve()
        try:
            requested_file.relative_to(dist_root)
        except ValueError as error:
            raise HTTPException(status_code=404) from error

        if requested_file.is_file():
            return FileResponse(requested_file)

        if requested_path == "assets" or requested_path.startswith("assets/"):
            raise HTTPException(status_code=404)

        if index_path.is_file():
            return FileResponse(index_path)

        raise HTTPException(status_code=404)
