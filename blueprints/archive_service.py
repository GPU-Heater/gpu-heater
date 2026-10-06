import os
import shutil
import tempfile
import zipfile
import tarfile
from blueprints.config import IGNORE_DIRS, DEFAULT_EXTS

try:
    import rarfile
except ImportError:
    rarfile = None

ARCHIVE_EXTS = {'.zip', '.tar', '.gz', '.tgz', '.tar.gz', '.rar'}

def extract_and_analyze_archive(archive_path):
    temp_dir = tempfile.mkdtemp(prefix="archive_workspace_")
    archive_context = ""
    
    try:
        lower_path = archive_path.lower()
        
        if lower_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(temp_dir)
                
        elif lower_path.endswith(('.tar', '.tar.gz', '.tgz', '.gz')):
            with tarfile.open(archive_path, 'r:*') as tf:
                tf.extractall(temp_dir)
                
        elif lower_path.endswith('.rar'):
            if rarfile:
                with rarfile.RarFile(archive_path, 'r') as rf:
                    rf.extractall(temp_dir)
            else:
                return "[ERROR: RAR files cannot be processed because the 'rarfile' library is not installed.]"

        file_tree = []
        file_contents = []

        for root, dirs, files in os.walk(temp_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file in files:
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, temp_dir)
                
                try:
                    with open(filepath, 'rb') as f:
                        if b'\x00' in f.read(1024):
                            continue
                except Exception:
                    continue

                ext = os.path.splitext(file)[1].lower()
                if ext in DEFAULT_EXTS or ext in ['.txt', '.md', '.json', '.xml', '.yaml', '.yml', '.env']:
                    file_tree.append(rel_path)
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            file_contents.append(f"\n--- [Archive File]: {rel_path} ---\n{content}\n")
                    except Exception:
                        pass

        tree_str = "📦 Archive Project File Tree:\n" + "\n".join(file_tree)
        context_str = "".join(file_contents)
        archive_context = f"{tree_str}\n\n📦 Archive File Contents:\n{context_str}"

    except Exception as e:
        archive_context = f"[Archive Extraction/Read Error: {e}]"
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    return archive_context