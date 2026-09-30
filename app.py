import os
from app import create_app
from config import DevelopmentConfig, ProductionConfig

config = ProductionConfig if os.getenv("FLASK_ENV") == "production" else DevelopmentConfig
app = create_app(config)

if __name__ == "__main__": app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")))
