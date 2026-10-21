"""Development entry point for Padeli Hyeti."""

import os

from padeli import create_app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("PADELI_HOST", "127.0.0.1"),
        port=int(os.environ.get("PADELI_PORT", "8000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )

