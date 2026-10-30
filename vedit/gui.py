"""Masaüstü penceresi: yerel sunucuyu başlatır ve arayüzü pywebview ile açar."""
from __future__ import annotations

import socket
import threading
import time
import webbrowser
from pathlib import Path


def _free_port(preferred: int) -> int:
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    return preferred


def _serve(port: int):
    import uvicorn

    from .server.app import app

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    return server


def main(project: str | None = None, browser: bool = False, port: int = 8765, serve_only=False):
    from .server import app as appmod

    if project:
        appmod.open_project(str(Path(project).resolve()))
    port = port if serve_only else _free_port(port)
    server = _serve(port)
    url = f"http://127.0.0.1:{port}/ui/index.html"
    print(f"VEdit arayüzü: {url}", flush=True)
    if browser or serve_only:
        if not serve_only:
            webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        try:
            import webview
        except ImportError:
            webbrowser.open(url)
            while True:
                time.sleep(1)
        window = webview.create_window("VEdit", url, width=1500, height=920, min_size=(1100, 700),
                                       background_color="#141418")

        def dialog(kind, opts):
            ftypes = tuple(opts.get("filters") or ())
            if kind == "save":
                return window.create_file_dialog(webview.SAVE_DIALOG,
                                                 save_filename=opts.get("default") or "",
                                                 file_types=ftypes)
            if kind == "folder":
                return window.create_file_dialog(webview.FOLDER_DIALOG)
            return window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True,
                                             file_types=ftypes)

        appmod.S.dialog = dialog
        webview.start()
    server.should_exit = True
    appmod.shutdown()
