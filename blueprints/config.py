import os

DB_NAME = "user/chat_history.db"
MAX_FILE_SIZE_MB = 100
COMFYUI_URL = "http://127.0.0.1:8188"
OLLAMA_TIMEOUT = None
OLLAMA_HOST = "http://127.0.0.1:11434"

UPLOAD_FOLDER = 'user/uploads'
VOICES_FOLDER = 'user/voices'
GENERATED_AUDIO_FOLDER = 'user/generated_audio'
GENERATED_DOCS_FOLDER = 'user/generated_docs'
GENERATED_MEDIA_FOLDER = 'user/generated_media'

for folder in [UPLOAD_FOLDER, VOICES_FOLDER, GENERATED_AUDIO_FOLDER, GENERATED_DOCS_FOLDER, GENERATED_MEDIA_FOLDER]:
    os.makedirs(folder, exist_ok=True)

VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
AUDIO_EXTS = {'.mp3', '.wav', '.m4a', '.ogg', '.flac'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
TEXT_EXTS  = {'.txt', '.json', '.csv', '.log', '.md', '.py', '.js', '.html', '.css', '.xml', '.yml', '.yaml', '.sh', '.bat', '.php', '.java', '.c', '.cpp', '.h', '.hpp', '.rs', '.go', '.swift', '.kt', '.kts', '.dart', '.ts', '.jsx', '.tsx', '.cs'}
DOC_EXTS   = {'.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx'}
ARCHIVE_EXTS = {'.zip', '.tar', '.gz', '.tgz', '.tar.gz', '.rar'}

IGNORE_DIRS = ['.git', 'node_modules', 'venv', '__pycache__', 'lib', 'vendor', '.idea', '.vscode', '.next', 'dist', 'build']

DEFAULT_EXTS = [
    ".html", ".css", ".js", ".ts", ".php", ".sql", ".xml", ".json", 
    ".csv", ".md", ".yaml", ".yml", ".sh", ".bat", ".pl", ".ps1", 
    ".c", ".cpp", ".h", ".hpp", ".m", ".mm", ".rs", ".dart", 
    ".java", ".py", ".cs", ".rb", ".go", ".swift", ".kt", ".kts", ".jsx", ".tsx"
]

EMBEDDING_FILE = os.path.join(os.path.dirname(__file__), "..", "embedding_model.txt")
if os.path.exists(EMBEDDING_FILE):
    try:
        with open(EMBEDDING_FILE, "r", encoding="utf-8") as f:
            EMBEDDING_MODEL_NAME = f.read().strip() or "nomic-embed-text"
    except Exception:
        EMBEDDING_MODEL_NAME = "nomic-embed-text"
else:
    EMBEDDING_MODEL_NAME = "nomic-embed-text"