"""`python -m web` starts the tool. Local by default; PUBLIC_MODE=1 for a public deployment."""
from __future__ import annotations

import os
import threading
import webbrowser

import uvicorn

from .app import Settings, create_app


def main() -> None:
    settings = Settings.from_env()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    if not settings.public_mode and host in ("127.0.0.1", "localhost") and not os.environ.get("NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}/")).start()
    uvicorn.run(create_app(settings), host=host, port=port, log_level="info",
                proxy_headers=False, server_header=False)


if __name__ == "__main__":
    main()
