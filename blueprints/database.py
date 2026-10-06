import sqlite3
from blueprints.config import DB_NAME

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, created_at TIMESTAMP, is_pinned INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, role TEXT, content TEXT, timestamp TIMESTAMP, FOREIGN KEY(chat_id) REFERENCES chats(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS rss_feeds (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE, added_at TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS processed_rss_links (link TEXT PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS rss_archive (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, link TEXT, summary TEXT, source TEXT, added_at TIMESTAMP)''')
    
    default_settings = {
        "workspace_path": "",
        "personal_context": "",
        "system_prompt": "You are a helpful assistant. Format your responses in Markdown. Always detect the user's language and respond entirely in the same language as the user's input. Do NOT generate algorithms, workflows, or Mermaid diagrams by default. Only generate and illustrate algorithms, processes, or step-by-step logic using Mermaid.js diagrams (mermaid ... ) when the user explicitly requests a diagram, flowchart, algorithm, or visual workflow.",
        "tts_voice": "",
        "timeout_enabled": "false",
        "timeout_sec": "300",
        "default_model": "qwen3.8:27b",
        "reasoning_model": "qwq:32b",
        "coder_model": "qwen2.5-coder:32b",
        "coder_reasoning_model": "qwq:32b",
        "title_model": "llama3.2:3b",
        "model_unload_timeout": "5"
    }
    for k, v in default_settings.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else ""

def set_setting(key, value):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()