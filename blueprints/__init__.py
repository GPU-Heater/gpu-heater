from blueprints.database import init_db
from blueprints.routes import main_bp
from blueprints.coder import coder_bp

init_db()

__all__ = ["main_bp", "coder_bp"]