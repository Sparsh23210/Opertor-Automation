import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings(BaseModel):
    EXECUTION_MODE: str = os.getenv("EXECUTION_MODE", "hybrid")  # hybrid, ai, deterministic
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Workspace directory paths
    WORKSPACE_ROOT: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    OUTPUT_DIR: Path = BASE_DIR / "data" / "outputs"
    POLICIES_DIR: Path = BASE_DIR / "data" / "policies"
    OPERATIONS_DIR: Path = BASE_DIR / "data" / "operations"
    INVOICES_DB_PATH: Path = BASE_DIR / "data" / "invoices.db"
    SYSTEM_DB_PATH: Path = BASE_DIR / "data" / "company_automation.db"

    # Reference date for overdue calculation (deterministic standard baseline)
    REFERENCE_DATE: str = "2026-10-10"

    # Execution limits & safety
    MAX_STEPS_PER_TASK: int = 15
    MAX_RETRIES_PER_STEP: int = 3
    DEFAULT_TIMEOUT_SECONDS: int = 30
    MAX_FILE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB limit

    # Allowed domains for browser automation (strict bounding)
    ALLOWED_BROWSER_DOMAINS: list[str] = ["127.0.0.1", "localhost"]

settings = Settings()

# Ensure required runtime directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
settings.POLICIES_DIR.mkdir(parents=True, exist_ok=True)
settings.OPERATIONS_DIR.mkdir(parents=True, exist_ok=True)

def resolve_safe_path(requested_path: str | Path, allowed_roots: list[Path] = None) -> Path:
    """
    Validates and resolves a path to prevent path traversal attacks.
    Ensures the path stays strictly within allowed directory roots.
    """
    if allowed_roots is None:
        allowed_roots = [settings.DATA_DIR, settings.OUTPUT_DIR, settings.POLICIES_DIR, settings.OPERATIONS_DIR]
    
    path_obj = Path(requested_path)
    if not path_obj.is_absolute():
        path_obj = (settings.WORKSPACE_ROOT / path_obj).resolve()
    else:
        path_obj = path_obj.resolve()
        
    is_safe = any(
        path_obj == root.resolve() or root.resolve() in path_obj.parents 
        for root in allowed_roots
    )
    if not is_safe:
        raise PermissionError(f"Access denied: path '{requested_path}' resolves outside permitted workspace roots.")
    
    return path_obj
