from pathlib import Path

try:
    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.is_file():
        load_dotenv(_env_path)
    else:
        load_dotenv()
except ImportError:
    pass

__version__ = "1.0.0"

