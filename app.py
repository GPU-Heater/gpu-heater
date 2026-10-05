from flask import Flask
import warnings

from blueprints.config import MAX_FILE_SIZE_MB
from blueprints import main_bp, coder_bp

warnings.filterwarnings("ignore")

app = Flask(__name__)
app.secret_key = "gpu-heater-local-key"
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_MB * 1024 * 1024

app.register_blueprint(main_bp)
app.register_blueprint(coder_bp)

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=2004, threaded=True)