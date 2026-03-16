"""
Maintenance-Eye Configuration
Loads environment variables and provides app-wide settings.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# .env is at project root; config.py lives in backend/
_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env")  # project root
load_dotenv()  # also try cwd (if already at root)


class Settings:
    """Application settings loaded from environment variables."""

    # GCP
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "maintenance-eye")
    GCP_REGION: str = os.getenv("GCP_REGION", "us-central1")

    # Gemini
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_LIVE_MODEL: str = os.getenv("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-latest")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip('"').strip("'")

    def __init__(self):
        # ADK / genai client reads GOOGLE_API_KEY from env
        # Set (or overwrite) so only one key is active, avoiding the dual-key warning
        if self.GEMINI_API_KEY:
            os.environ["GOOGLE_API_KEY"] = self.GEMINI_API_KEY
            os.environ.pop("GEMINI_API_KEY", None)
        # Firestore client library reads FIRESTORE_EMULATOR_HOST from os.environ
        if self.FIRESTORE_EMULATOR_HOST and not os.getenv("FIRESTORE_EMULATOR_HOST"):
            os.environ["FIRESTORE_EMULATOR_HOST"] = self.FIRESTORE_EMULATOR_HOST

    # Firestore
    FIRESTORE_DATABASE: str = os.getenv("FIRESTORE_DATABASE", "(default)")
    FIRESTORE_EMULATOR_HOST: str = os.getenv("FIRESTORE_EMULATOR_HOST", "")

    # Cloud Storage
    GCS_BUCKET: str = os.getenv("GCS_BUCKET", "maintenance-eye-storage")

    # Firebase Auth / Security
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "")
    ENABLE_AUTH: bool = os.getenv("ENABLE_AUTH", "").lower() in {"1", "true", "yes"}
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "")

    # App
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_PORT: int = int(os.getenv("APP_PORT", "8080"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Agent
    AGENT_PERSONA_NAME: str = "Max"
    AGENT_CONFIDENCE_THRESHOLD: float = 0.80

    @property
    def use_emulator(self) -> bool:
        """Check if we should use the Firestore emulator."""
        return bool(self.FIRESTORE_EMULATOR_HOST)

    @property
    def auth_enabled(self) -> bool:
        """Enable auth by default in production unless explicitly disabled."""
        if os.getenv("ENABLE_AUTH") is None:
            return self.APP_ENV == "production"
        return self.ENABLE_AUTH

    @property
    def cors_origins(self) -> list[str]:
        """Parse configured CORS origins."""
        if self.ALLOWED_ORIGINS.strip():
            return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        if self.APP_ENV == "production":
            return []
        return [
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]


settings = Settings()
