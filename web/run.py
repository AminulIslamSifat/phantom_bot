
"""Standalone entry point for the web admin panel.

Usage:
    python -m web.run              # debug mode
    gunicorn web.app:create_app    # production
"""

from web.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
