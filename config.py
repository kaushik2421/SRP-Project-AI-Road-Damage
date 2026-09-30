import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    MODEL_PATH = os.getenv("MODEL_PATH", str(BASE_DIR / "models/road_damage/best.pt"))
    AI_CONFIDENCE_THRESHOLD = float(os.getenv("AI_CONFIDENCE_THRESHOLD", "0.35"))
    DUPLICATE_RADIUS_METERS = float(os.getenv("DUPLICATE_RADIUS_METERS", "50"))
    IMAGE_SIMILARITY_THRESHOLD = float(os.getenv("IMAGE_SIMILARITY_THRESHOLD", "0.85"))
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DEV_DATABASE_URL", f"sqlite:///{BASE_DIR / 'road_damage_dev.db'}"
    )


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    MODEL_PATH = ""


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "")

    @classmethod
    def validate(cls):
        if not cls.SQLALCHEMY_DATABASE_URI.startswith("mysql+"):
            raise RuntimeError("Production DATABASE_URL must be a MySQL SQLAlchemy URL.")
