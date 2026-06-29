"""PyInstaller entrypoint for the bundled PaperReady backend sidecar."""

from __future__ import annotations

import uvicorn


def main() -> None:
    """Run the FastAPI app on the local desktop endpoint."""
    uvicorn.run(
        "paper_ready_backend.main:app",
        host="127.0.0.1",
        port=8765,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
