"""Dashboard entrypoint."""

from apps.dashboard.app import app


def main() -> None:
    app.run(host="0.0.0.0", port=8050, debug=False)


server = app.server
