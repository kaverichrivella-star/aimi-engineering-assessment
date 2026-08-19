import os
import sys
from pathlib import Path


def main():
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    app_path = bundle_root / "src" / "app.py"
    os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
    sys.argv = ["streamlit", "run", str(app_path), "--server.headless", "true"]
    from streamlit.web.cli import main as streamlit_main
    streamlit_main()


if __name__ == "__main__":
    main()
