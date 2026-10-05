import os
import io
import json
import uuid
import re
import sqlite3
import threading
import queue
import time
from datetime import datetime
import hashlib
from flask import Blueprint, request, jsonify, render_template, Response, stream_with_context, send_from_directory, send_file
from langdetect import detect
import tiktoken
import feedparser
import urllib.parse

from blueprints.config import DB_NAME, UPLOAD_FOLDER, VOICES_FOLDER, GENERATED_AUDIO_FOLDER, GENERATED_DOCS_FOLDER, GENERATED_MEDIA_FOLDER, VIDEO_EXTS, AUDIO_EXTS, IMAGE_EXTS, DOC_EXTS, TEXT_EXTS
from blueprints.database import get_setting, set_setting
from blueprints.ai_models import generate_tts_audio, tts_engine
from blueprints.utils import get_ollama_client, extract_and_save_context, search_duckduckgo, generate_chat_title, process_video, analyze_audio, encode_image_to_base64, cleanup_files, clean_markdown_for_tts, extract_urls, scrape_webpage_content, unload_ollama_models
from blueprints.comfyui import handle_comfyui_request
from blueprints.doc_parser import parse_document
from blueprints.pdf_service import export_chat_pdf_buffer, create_document_pdf
from blueprints.coder import scan_workspace
from blueprints.knowledge_base import add_document_to_db, search_knowledge_base, get_all_sources, delete_document_by_source, get_document_content
from blueprints.archive_service import extract_and_analyze_archive, ARCHIVE_EXTS

main_bp = Blueprint('main', __name__)

active_streams = {}
task_queues = {}
is_system_busy = False
active_chat_id = None
last_completed_notification = None

last_ui_ping = time.time()

try:
    tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception:
    tokenizer = tiktoken.encoding_for_model("gpt-4o")

def calculate_comprehensive_tokens(messages, extra_items=None):
    total_tokens = 0
    breakdown = {"text_tokens": 0, "media_vision_tokens": 0, "extra_tokens": 0}

    for m in messages:
        content = m.get("content", "")
        if content:
            t_count = len(tokenizer.encode(content))
            breakdown["text_tokens"] += t_count
            total_tokens += t_count
        total_tokens += 4

        if "images" in m and isinstance(m["images"], list):
            v_count = len(m["images"]) * 1280
            breakdown["media_vision_tokens"] += v_count
            total_tokens += v_count

    if extra_items:
        for item in extra_items:
            if item:
                e_count = len(tokenizer.encode(str(item)))
                breakdown["extra_tokens"] += e_count
                total_tokens += e_count

    total_tokens += 2
    return total_tokens, breakdown

def run_generation_task(chat_id, messages_for_ollama, num_predict, num_ctx, action, user_prompt, is_new_chat, files_to_cleanup, active_model, ollama_options=None, keep_alive_param="300s"):
    global is_system_busy, active_chat_id, last_completed_notification
    full_output = ""
    q = task_queues.get(chat_id)

    if ollama_options is None:
        ollama_options = {"num_predict": num_predict, "num_ctx": num_ctx}

    try:
        client = get_ollama_client()

        if action == "to pdf":
            response = client.chat(model=active_model, messages=messages_for_ollama, stream=True, options=ollama_options, keep_alive=keep_alive_param)
            for chunk in response:
                if not active_streams.get(chat_id, True):
                    full_output += "\n\n*[Process canceled by user]*"
                    break
                c = chunk.get('message', {}).get('content', '')
                full_output += c
                if q: q.put(("chunk", c))
            
            if active_streams.get(chat_id, True):
                if q: q.put(("status", "🖨️ Converting to PDF..."))
                pdf_filename = f"document_{uuid.uuid4().hex[:8]}.pdf"
                pdf_filepath = os.path.join(GENERATED_DOCS_FOLDER, pdf_filename)
                create_document_pdf(full_output, pdf_filepath)
                download_ui = f"\n\n---\n**✅ Process Completed:** <a href='/generated_docs/{pdf_filename}' target='_blank' download style='display:inline-block; margin-top:10px; background-color:#38bdf8; color:white; padding:8px 16px; border-radius:6px; text-decoration:none; font-weight:bold;'><i class='fas fa-file-pdf'></i> Download PDF</a>"
                full_output += download_ui
                if q: q.put(("chunk", download_ui))

        else:
            response = client.chat(model=active_model, messages=messages_for_ollama, stream=True, options=ollama_options, keep_alive=keep_alive_param)
            for chunk in response:
                if not active_streams.get(chat_id, True):
                    full_output += "\n\n*[Process canceled by user]*"
                    break
                c = chunk.get('message', {}).get('content', '')
                full_output += c
                if q: q.put(("chunk", c))

        if full_output.strip():
            conn = sqlite3.connect(DB_NAME)
            conn.execute("INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)", (chat_id, "assistant", full_output, datetime.now()))
            
            if is_new_chat:
                summary_context = f"User: {user_prompt[:250]}\nAI: {full_output[:250]}"
                smart_title = None
                try:
                    smart_title = generate_chat_title(summary_context)
                except Exception:
                    pass
                
                if not smart_title or len(smart_title.strip()) < 2:
                    smart_title = user_prompt[:30].strip() or f"{action.capitalize()} Chat"
                
                conn.execute("UPDATE chats SET title = ? WHERE id = ?", (smart_title, chat_id))
                if q: q.put(("title_update", {"chat_id": chat_id, "title": smart_title}))

            conn.commit()
            conn.close()

        last_completed_notification = {"chat_id": chat_id, "time": datetime.now().strftime("%H:%M:%S")}
        if q: q.put(("done", None))

    except Exception as e:
        if q: q.put(("error", str(e)))
    finally:
        cleanup_files(files_to_cleanup)
        is_system_busy = False
        active_chat_id = None
        active_streams.pop(chat_id, None)
        task_queues.pop(chat_id, None)

def evaluate_news_importance(title, summary):
    prompt = f"Evaluate the importance of this news from 1 to 10. Return ONLY a single number. Title: {title} Summary: {summary}"
    try:
        client = get_ollama_client()
        res = client.chat(model=get_setting("default_model"), messages=[{"role": "user", "content": prompt}], options={"num_predict": 5})
        match = re.search(r'\b(10|[1-9])\b', res['message']['content'])
        score = int(match.group(1)) if match else 0
        return score
    except Exception:
        return 0

def rss_background_worker():
    global last_ui_ping
    while True:
        if time.time() - last_ui_ping < 15:
            time.sleep(5)
            continue
            
        try:
            conn = sqlite3.connect(DB_NAME)
            feeds = conn.execute("SELECT id, url FROM rss_feeds").fetchall()
            
            for feed_id, feed_url in feeds:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    link = entry.get('link', '')
                    
                    if conn.execute("SELECT 1 FROM processed_rss_links WHERE link = ?", (link,)).fetchone():
                        continue
                        
                    title = entry.get('title', '')
                    summary = entry.get('summary', '')
                    score = evaluate_news_importance(title, summary)
                    
                    if score >= 7:
                        formatted_content = f"RSS\nTitle: {title}\nLink: {link}\nSummary: {summary}"
                        add_document_to_db(formatted_content, f"RSS_{link}")
                        domain = urllib.parse.urlparse(link).netloc
                        conn.execute("INSERT INTO rss_archive (title, link, summary, source, added_at) VALUES (?, ?, ?, ?, ?)", (title, link, summary, domain, datetime.now()))

                    conn.execute("INSERT OR IGNORE INTO processed_rss_links (link) VALUES (?)", (link,))
                    conn.commit()
            conn.close()
        except Exception:
            pass
        
        time.sleep(300)

threading.Thread(target=rss_background_worker, daemon=True).start()

@main_bp.route("/api/models/list", methods=["GET"])
def list_models():
    client = get_ollama_client()
    try:
        raw_list = client.list()
        models_data = []
        items = raw_list.get('models', []) if isinstance(raw_list, dict) else getattr(raw_list, 'models', [])
        
        for item in items:
            name = item.get('name') if isinstance(item, dict) else getattr(item, 'model', getattr(item, 'name', ''))
            size_bytes = item.get('size', 0) if isinstance(item, dict) else getattr(item, 'size', 0)
            
            size_gb = round(size_bytes / (1024 ** 3), 2) if size_bytes else 0
            
            if name:
                models_data.append({"name": name, "size_gb": size_gb})
                
        return jsonify({"success": True, "models": models_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "models": []})

@main_bp.route("/api/models/pull", methods=["POST"])
def pull_model():
    model_name = request.json.get("model")
    if not model_name: 
        return jsonify({"success": False, "error": "Model name not provided."})
    
    def generate():
        client = get_ollama_client()
        try:
            for progress in client.pull(model_name, stream=True):
                status = progress.get('status', '')
                completed = progress.get('completed', 0)
                total = progress.get('total', 0)
                yield f"data: {json.dumps({'status': status, 'completed': completed, 'total': total})}\n\n"
            yield f"data: {json.dumps({'status': 'success'})}\n\n"
        except GeneratorExit:
            pass
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@main_bp.route("/api/models/delete", methods=["POST"])
def delete_model():
    model_name = request.json.get("model")
    try:
        client = get_ollama_client()
        client.delete(model_name)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@main_bp.route("/api/rss/archive", methods=["GET"])
def get_rss_archive():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    archive = [dict(row) for row in conn.execute("SELECT * FROM rss_archive ORDER BY added_at DESC").fetchall()]
    conn.close()
    return jsonify({"success": True, "data": archive})

@main_bp.route("/api/ping_ui", methods=["POST"])
def ping_ui():
    global last_ui_ping
    last_ui_ping = time.time()
    return jsonify({"status": "active"})

@main_bp.route("/api/train_url", methods=["POST"])
def api_train_url():
    url = request.json.get("url")
    if not url: return jsonify({"success": False})
    content = scrape_webpage_content(url)
    if content.startswith("[") and "error" in content.lower():
        return jsonify({"success": False})
    add_document_to_db(content, url)
    return jsonify({"success": True})

@main_bp.route("/api/rss", methods=["GET", "POST"])
def manage_rss():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    if request.method == "POST":
        url = request.json.get("url")
        try:
            conn.execute("INSERT INTO rss_feeds (url, added_at) VALUES (?, ?)", (url, datetime.now()))
            conn.commit()
        except Exception:
            pass
        conn.close()
        return jsonify({"success": True})
        
    feeds = [dict(row) for row in conn.execute("SELECT id, url FROM rss_feeds").fetchall()]
    conn.close()
    return jsonify(feeds)

@main_bp.route("/api/rss/<int:feed_id>", methods=["DELETE"])
def delete_rss(feed_id):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM rss_feeds WHERE id = ?", (feed_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@main_bp.route("/api/train_document", methods=["POST"])
def train_document():
    uploaded_file = request.files.get("file")
    if uploaded_file and uploaded_file.filename:
        fp = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
        uploaded_file.save(fp)
        ext = os.path.splitext(fp)[1].lower()
        
        file_content = ""
        
        if ext in IMAGE_EXTS:
            b64 = encode_image_to_base64(fp)
            client = get_ollama_client()
            prompt = "Extract all text from this image and describe its contents in detail so it can be used for a knowledge base search."
            
            try:
                res = client.chat(
                    model=get_setting("default_model"), 
                    messages=[{"role": "user", "content": prompt, "images": [b64]}],
                    options={"num_predict": 1024}
                )
                file_content = f"[Image Description: {uploaded_file.filename}]\n" + res['message']['content'].strip()
            except Exception as e:
                print(f"Image Analysis Error: {e}")
                file_content = ""
        else:
            file_content = parse_document(fp, ext)

        if file_content:
            add_document_to_db(file_content, uploaded_file.filename)
        
        if os.path.exists(fp):
            os.remove(fp)
            
        if file_content:
            return jsonify({"success": True, "message": f"{uploaded_file.filename} added to knowledge base."})
        else:
            return jsonify({"success": False, "error": "Could not extract content from the file."})
        
    return jsonify({"success": False, "error": "Invalid file."})

@main_bp.route("/api/kb/sources", methods=["GET"])
def get_kb_sources():
    sources = get_all_sources()
    return jsonify({"success": True, "sources": sources})

@main_bp.route("/api/kb/source", methods=["DELETE"])
def delete_kb_source():
    source = request.json.get("source")
    if source:
        delete_document_by_source(source)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Source not provided."})

@main_bp.route("/api/kb/source/view", methods=["POST"])
def view_kb_source():
    source = request.json.get("source")
    if source:
        content = get_document_content(source)
        return jsonify({"success": True, "content": content})
    return jsonify({"success": False, "error": "Source not provided."})

@main_bp.route("/api/rss/archive/<int:item_id>", methods=["DELETE"])
def delete_rss_archive_item(item_id):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM rss_archive WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@main_bp.route("/api/system_status", methods=["GET"])
def system_status():
    global last_completed_notification
    completed = last_completed_notification
    last_completed_notification = None
    return jsonify({
        "is_busy": is_system_busy,
        "active_chat_id": active_chat_id,
        "last_completed": completed
    })

@main_bp.route("/")
def index():
    return render_template('index.html')

@main_bp.route("/api/settings", methods=["GET", "POST"])
def manage_settings():
    setting_keys = [
        "system_prompt", 
        "personal_context", 
        "tts_voice", 
        "timeout_enabled", 
        "timeout_sec",
        "title_model",
        "default_model",
        "reasoning_model",
        "coder_model",
        "coder_reasoning_model",
        "model_unload_timeout"
    ]
    
    if request.method == "POST":
        data = request.json or {}
        for k in setting_keys:
            if k in data:
                set_setting(k, str(data[k]))
        return jsonify({"success": True})
        
    return jsonify({k: get_setting(k) for k in setting_keys})

@main_bp.route("/api/voices", methods=["GET", "POST"])
def manage_voices():
    if request.method == "GET":
        files = [f for f in os.listdir(VOICES_FOLDER) if f.endswith('.wav')]
        return jsonify(files)
    
    if request.method == "POST":
        file = request.files.get("voice_file")
        if file and file.filename.endswith('.wav'):
            filepath = os.path.join(VOICES_FOLDER, file.filename)
            file.save(filepath)
            return jsonify({"success": True, "filename": file.filename})
        return jsonify({"success": False, "error": "Invalid file format. Only .wav is accepted."}), 400

@main_bp.route("/api/tts", methods=["POST"])
def generate_tts():
    if not tts_engine:
        return jsonify({"success": False, "error": "Chatterbox model is not installed on the server."}), 500
        
    raw_text = request.json.get("text", "")
    if not raw_text:
        return jsonify({"success": False, "error": "No text provided to read."}), 400
        
    voice_filename = get_setting("tts_voice")
    if not voice_filename:
        return jsonify({"success": False, "error": "You must select a Reference Voice in settings."}), 400
        
    speaker_wav = os.path.join(VOICES_FOLDER, voice_filename)
    if not os.path.exists(speaker_wav):
        return jsonify({"success": False, "error": f"Selected voice ({voice_filename}) not found."}), 400

    clean_text = clean_markdown_for_tts(raw_text)
    if len(clean_text) < 2:
        return jsonify({"success": False, "error": "Could not extract readable clean text."}), 400

    try:
        detected_lang = detect(clean_text)
    except Exception:
        detected_lang = "en"

    try:
        text_hash = hashlib.md5(f"{clean_text}_{detected_lang}_{voice_filename}".encode('utf-8')).hexdigest()
        output_filename = f"tts_{text_hash}.wav"
        output_filepath = os.path.join(GENERATED_AUDIO_FOLDER, output_filename)
        
        if not os.path.exists(output_filepath):
            generate_tts_audio(clean_text, detected_lang, speaker_wav, output_filepath)
        return jsonify({"success": True, "audio_url": f"/generated_audio/{output_filename}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route('/generated_audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory(GENERATED_AUDIO_FOLDER, filename)

@main_bp.route('/generated_docs/<path:filename>')
def serve_doc(filename):
    return send_from_directory(GENERATED_DOCS_FOLDER, filename)

@main_bp.route('/generated_media/<path:filename>')
def serve_generated_media(filename):
    return send_from_directory(GENERATED_MEDIA_FOLDER, filename)

@main_bp.route("/api/chats", methods=["GET"])
def get_chats():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    chats = [dict(row) for row in conn.execute("SELECT id, title, is_pinned FROM chats ORDER BY is_pinned DESC, created_at DESC").fetchall()]
    conn.close()
    return jsonify(chats)

@main_bp.route("/api/chat/<int:chat_id>", methods=["GET", "DELETE", "PUT"])
def manage_chat(chat_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    
    if request.method == "GET":
        msgs = [dict(row) for row in conn.execute("SELECT id, role, content FROM messages WHERE chat_id = ? ORDER BY timestamp ASC", (chat_id,)).fetchall()]
        conn.close()
        return jsonify(msgs)
        
    elif request.method == "PUT":
        data = request.json
        if "title" in data:
            conn.execute("UPDATE chats SET title = ? WHERE id = ?", (data["title"], chat_id))
        if "is_pinned" in data:
            conn.execute("UPDATE chats SET is_pinned = ? WHERE id = ?", (data["is_pinned"], chat_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
        
    conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@main_bp.route("/api/message/<int:msg_id>", methods=["DELETE", "PUT"])
def manage_message(msg_id):
    conn = sqlite3.connect(DB_NAME)
    if request.method == "DELETE":
        conn.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
    elif request.method == "PUT":
        conn.execute("UPDATE messages SET content = ? WHERE id = ?", (request.json.get("content"), msg_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@main_bp.route("/api/cancel/<int:chat_id>", methods=["POST"])
def cancel_stream(chat_id):
    global is_system_busy, active_chat_id
    active_streams[chat_id] = False
    is_system_busy = False
    active_chat_id = None
    return jsonify({"success": True})

@main_bp.route("/api/export_chat/<int:chat_id>")
def export_chat_pdf_route(chat_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT title FROM chats WHERE id = ?", (chat_id,))
    chat_row = c.fetchone()
    if not chat_row:
        return "Chat not found", 404
    chat_title = chat_row[0]
    
    msgs = conn.execute("SELECT role, content FROM messages WHERE chat_id = ? ORDER BY timestamp ASC", (chat_id,)).fetchall()
    conn.close()

    pdf_bytes = export_chat_pdf_buffer(chat_title, msgs)
    return send_file(io.BytesIO(pdf_bytes), download_name=f"Chat_{chat_title[:15]}.pdf", as_attachment=True, mimetype='application/pdf')

@main_bp.route("/api/analyze_code", methods=["POST"])
def analyze_code():
    req_data = request.get_json(silent=True)
    code = req_data.get("code", "") if req_data else ""
    if not code: return jsonify({"ext": ".txt"})
    
    prompt = "Review the following code and return ONLY the most appropriate file extension (e.g., .py, .html, .js, .json). Do not add any extra words, punctuation, or explanations.\n\nCode:\n" + code[:1000] 
    try:
        client = get_ollama_client()
        res = client.chat(model=get_setting("coder_model"), messages=[{"role": "user", "content": prompt}], options={"num_predict": 10})
        ext = res['message']['content'].strip().split()[0].lower()
        if not ext.startswith('.'): 
            ext = '.' + ext
        return jsonify({"ext": ext})
    except Exception:
        return jsonify({"ext": ".txt"})

@main_bp.route("/api/generate_stream", methods=["POST"])
def generate_stream():
    global is_system_busy, active_chat_id
    
    if is_system_busy:
        return jsonify({"error": "BUSY", "message": "There is an active process running in the background. Please wait for it to finish."}), 429

    user_prompt = request.form.get("prompt", "")
    action = request.form.get("action", "analyze")
    chat_id = request.form.get("chatId")
    chat_id = int(chat_id) if chat_id and chat_id != 'null' else None
    
    coder_mode = request.form.get("coderMode") == 'true'
    workspace_path = request.form.get("workspacePath", "").strip()

    thinking_enabled = request.form.get("thinking") == 'true'
    web_search_enabled = request.form.get("webSearch") == 'true'
    use_context = request.form.get("useContext") == 'true'
    auto_learn = request.form.get("autoLearn") == 'true'
    unlimited_token = request.form.get("unlimitedToken") == 'true'
    use_knowledge_base = request.form.get("useKnowledgeBase") == 'true'

    uploaded_files = request.files.getlist("file")
    saved_file_paths = []
    for uploaded_file in uploaded_files:
        if uploaded_file and uploaded_file.filename != '':
            fp = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
            uploaded_file.save(fp)
            saved_file_paths.append((fp, uploaded_file.filename))
            
    is_system_busy = True
    active_chat_id = chat_id

    def stream_generator():
        nonlocal chat_id
        global is_system_busy, active_chat_id
        
        files_to_cleanup = []
        thread_started = False
        
        try:
            yield f"data: {json.dumps({'status': '⏳ Preparing request...'})}\n\n"
            
            transcribed_text, audio_types, file_text_content = "", "", ""
            base64_images = []
            
            for fp, filename in saved_file_paths:
                files_to_cleanup.append(fp)
                
                ext = os.path.splitext(fp)[1].lower()
            
                if ext in VIDEO_EXTS:
                    yield f"data: {json.dumps({'status': '🎬 Parsing video frames and audio...'})}\n\n"
                    audio_path, frame_paths = process_video(fp)
                    if audio_path:
                        files_to_cleanup.append(audio_path)
                        yield f"data: {json.dumps({'status': '🎙️ Transcribing video audio...'})}\n\n"
                        t_text, a_types = analyze_audio(audio_path)
                        transcribed_text += "\n" + t_text
                        audio_types += " " + a_types
                    for frame in frame_paths:
                        files_to_cleanup.append(frame)
                        base64_images.append(encode_image_to_base64(frame))
                        
                elif ext in AUDIO_EXTS:
                    yield f"data: {json.dumps({'status': '🎙️ Analyzing audio file...'})}\n\n"
                    t_text, a_types = analyze_audio(fp)
                    transcribed_text += "\n" + t_text
                    audio_types += " " + a_types
                        
                elif ext in IMAGE_EXTS:
                    yield f"data: {json.dumps({'status': '🖼️ Buffering image...'})}\n\n"
                    base64_images.append(encode_image_to_base64(fp))

                elif any(fp.lower().endswith(a_ext) for a_ext in ARCHIVE_EXTS):
                    yield f"data: {json.dumps({'status': '📦 Unpacking archive and analyzing structure...'})}\n\n"
                    archive_data = extract_and_analyze_archive(fp)
                    file_text_content += f"\n\n--- Archive: {filename} ---\n" + archive_data

                elif ext in DOC_EXTS:
                    yield f"data: {json.dumps({'status': '📄 Reading document...'})}\n\n"
                    file_text_content += f"\n\n--- {filename} ---\n" + parse_document(fp, ext)

                elif ext in TEXT_EXTS:
                    try:
                        with open(fp, 'r', encoding='utf-8') as f:
                            file_text_content += f"\n\n--- {filename} ---\n" + f.read()
                    except Exception as e:
                        file_text_content += f"\n\n--- {filename} ---\n[File read error: {e}]"
        
            db_prompt = user_prompt
            if action != "analyze":
                db_prompt = f"[{action.upper()} Request]\n" + db_prompt
                
            if file_text_content: db_prompt += f"\n\n[File Content]:\n{file_text_content}"
            if audio_types: db_prompt += f"\n\n[Detected Audio Types]: {audio_types}"
            if transcribed_text: db_prompt += f"\n\n[Speech Transcript]: {transcribed_text}"
            for b64 in base64_images: db_prompt += f"\n\n![Attached Image](data:image/jpeg;base64,{b64})"

            if coder_mode and workspace_path:
                workspace_context = scan_workspace(workspace_path=workspace_path)
                if workspace_context:
                    db_prompt += f"\n\n[Workspace Context]:\n{workspace_context}"

            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            
            is_new_chat = False
            if not chat_id:
                is_new_chat = True
                temp_title = "New Chat"
                c.execute("INSERT INTO chats (title, created_at, is_pinned) VALUES (?, ?, ?)", (temp_title, datetime.now(), 0))
                chat_id = c.lastrowid
                active_chat_id = chat_id
            
            c.execute("INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)", (chat_id, "user", db_prompt, datetime.now()))
            conn.commit()

            c.execute("""
                SELECT role, content FROM (
                    SELECT id, role, content, timestamp FROM messages 
                    WHERE chat_id = ? ORDER BY timestamp DESC LIMIT 10
                ) ORDER BY timestamp ASC
            """, (chat_id,))
            history = c.fetchall()
            conn.close()

            yield f"data: {json.dumps({'chat_id': chat_id})}\n\n"
            active_streams[chat_id] = True
            
            if action != "analyze" and action != "to pdf" and not coder_mode:
                unload_ollama_models()
                comfy_prompt = user_prompt
                comfy_action = action
                comfy_file_path = files_to_cleanup[0] if files_to_cleanup else None

                comfy_kwargs = {}
                comfy_kwargs["bypass_enhancing"] = request.form.get("bypassEnhancing") == 'true'
                
                if action == "to outpaint":
                    comfy_kwargs["op_left"] = request.form.get("op_left", 0)
                    comfy_kwargs["op_right"] = request.form.get("op_right", 0)
                    comfy_kwargs["op_top"] = request.form.get("op_top", 0)
                    comfy_kwargs["op_bottom"] = request.form.get("op_bottom", 0)

                if action in ["to ref video", "to ref image"]:
                    yield f"data: {json.dumps({'status': '👁️ Vision AI is analyzing the reference image...'})}\n\n"
                    
                    vision_sys_prompt = (
                        "You are an expert AI prompt engineer. Describe the attached reference image in extreme, meticulous detail "
                        "(subjects, lighting, composition, colors, mood). Then, seamlessly integrate the user's custom request into "
                        "this description to form a single, comprehensive Text-to-Video/Image generation prompt. "
                        "Return ONLY the final prompt text without any conversational filler."
                    )
                    
                    v_messages = [
                        {"role": "system", "content": vision_sys_prompt},
                        {"role": "user", "content": user_prompt if user_prompt else "Describe this image in detail for recreation."}
                    ]
                    
                    if base64_images:
                        v_messages[1]["images"] = base64_images
                        
                    try:
                        v_predict = -1 if unlimited_token else 8192
                        v_ctx = 16384
                        
                        client = get_ollama_client()
                        v_res = client.chat(model=get_setting("default_model"), messages=v_messages, options={"num_predict": v_predict, "num_ctx": v_ctx})
                        comfy_prompt = v_res['message']['content'].strip()
                        
                        comfy_action = "to video" if action == "to ref video" else "to image"
                        comfy_file_path = None 
                        
                    except Exception as e:
                        yield f"data: {json.dumps({'status': f'Vision Error: {str(e)}'})}\n\n"

                yield f"data: {json.dumps({'status': f'Starting ComfyUI ({comfy_action})...'})}\n\n"
                final_res = ""
                
                for msg_type, msg_content in handle_comfyui_request(comfy_action, comfy_prompt, comfy_file_path, chat_id, active_streams, **comfy_kwargs):
                    if msg_type == "status":
                        yield f"data: {json.dumps({'status': msg_content})}\n\n"
                    elif msg_type == "chunk":
                        final_res = msg_content
                        yield f"data: {json.dumps({'chunk': final_res})}\n\n"
                
                conn2 = sqlite3.connect(DB_NAME)
                conn2.execute("INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)", (chat_id, "assistant", final_res, datetime.now()))
                conn2.commit()
                conn2.close()
                
                cleanup_files(files_to_cleanup)
                is_system_busy = False
                active_chat_id = None
                yield "data: [DONE]\n\n"
                return
            
            if auto_learn and user_prompt:
                threading.Thread(target=extract_and_save_context, args=(user_prompt,)).start()
                
            found_urls = extract_urls(user_prompt)
            scraped_url_context = ""
            
            if found_urls:
                target_url = found_urls[0]
                yield f"data: {json.dumps({'status': f'🌐 Reading webpage: {target_url[:35]}...'})}\n\n"
                page_content = scrape_webpage_content(target_url)
                scraped_url_context = f"\n\n[Webpage Content from {target_url}]:\n{page_content}\n"

            search_context = ""
            if web_search_enabled and user_prompt and not found_urls:
                yield f"data: {json.dumps({'status': '🌐 Searching the web...'})}\n\n"
                sr = search_duckduckgo(user_prompt)
                if sr:
                    search_context = f"\n\n[Web Search Results]:\n{sr}\nConsider the above information in your answer."

            combined_web_context = scraped_url_context + search_context

            knowledge_context = ""
            if use_knowledge_base and user_prompt:
                yield f"data: {json.dumps({'status': '📚 Searching knowledge base...'})}\n\n"
                found_docs = search_knowledge_base(user_prompt)
                if found_docs:
                    knowledge_context = f"\n\n[Trained Knowledge Base Data]:\n{found_docs}\n(CRITICAL INSTRUCTION: Use the above trained data to formulate your response. DO NOT mention that you retrieved this information from a document, database, or knowledge base unless the user explicitly commands you to specify your source. Incorporate the information naturally.)"
            combined_web_context = scraped_url_context + search_context + knowledge_context

            messages_for_ollama = []
            
            base_sys = ""
            if action == "to pdf":
                base_sys = "You are an expert document writer. Convert the user's topic or data into a professional, well-structured, detailed Markdown report with headers, paragraphs, and tables if necessary. Do not include any conversational greeting or confirmation, just start writing the document."
            else:
                base_sys = get_setting("system_prompt")
                
                if coder_mode:
                    base_sys = (
                        "You are an expert AI Software Architect and Senior Developer. "
                        "Format your responses in Markdown. Address requests within the framework of security, performance, and clean code. "
                        "Do NOT generate algorithms, workflows, or Mermaid diagrams by default; only generate Mermaid.js diagrams when explicitly requested. "
                        "CRITICAL CODING RULES:\n"
                        "1. ONLY use libraries and classes explicitly imported or defined in the provided context.\n"
                        "2. NEVER invent dummy helper classes (e.g., SqliteHelper, SanitizerHelper) unless defined in the project.\n"
                        "3. Produce high-quality, complete, and compile-ready code blocks directly without unnecessary theoretical filler.\n"
                        "4. If a [Workspace Context] is provided, use it ONLY if the user's request is directly related to that specific project."
                    )
                if transcribed_text or audio_types:
                    base_sys += "\n\nYou are a universal AI assistant. Accept the [Speech Transcript] and [Audio Types] provided to you as raw facts. Do not try to correct the transcript with internal bias."

                if use_context:
                    p_ctx = get_setting("personal_context")
                    if p_ctx.strip(): 
                        base_sys += f"\n\nKNOWN FACTS ABOUT USER:\n{p_ctx}"

            if base_sys.strip(): 
                messages_for_ollama.append({"role": "system", "content": base_sys.strip()})

            for idx, row in enumerate(history):
                role, content = row[0], row[1]
                
                if idx == len(history) - 1: 
                    content += combined_web_context
                    
                imgs = [m.group(2) for m in re.finditer(r'!\[.*?\]\((data:image\/[^;]+;base64,([a-zA-Z0-9+/=]+))\)', content)]
                content = re.sub(r'!\[.*?\]\(data:image\/[^;]+;base64,[a-zA-Z0-9+/=]+\)', '\n[User Attached Media]\n', content)
                    
                msg = {"role": role, "content": content}
                if imgs: 
                    msg["images"] = imgs
                    
                messages_for_ollama.append(msg)

            if coder_mode:
                active_model = get_setting("coder_reasoning_model") if thinking_enabled else get_setting("coder_model")
            else:
                active_model = get_setting("reasoning_model") if thinking_enabled else get_setting("default_model")

            actual_input_tokens, token_breakdown = calculate_comprehensive_tokens(messages_for_ollama)

            if unlimited_token:
                num_predict = -1 
            elif action == "to pdf":
                num_predict = 8192
            elif thinking_enabled:
                num_predict = 16384  
            else:
                num_predict = 4096   

            expected_output_margin = num_predict if num_predict > 0 else 8192
            raw_needed_ctx = int((actual_input_tokens + expected_output_margin) * 1.15)
            num_ctx = max(8192, ((raw_needed_ctx + 1023) // 1024) * 1024)

            unload_timeout_sec = get_setting("model_unload_timeout") or "300"
            keep_alive_param = f"{unload_timeout_sec}s"

            status_text = f"🤖 Scanned: {actual_input_tokens} tokens | Context: {num_ctx} | Predict: {num_predict} | Unload: {keep_alive_param}"
            yield f"data: {json.dumps({'status': status_text})}\n\n"

            ollama_options = {
                "num_predict": num_predict,
                "num_ctx": num_ctx,
                "thinking": thinking_enabled
            }

            q = queue.Queue()
            task_queues[chat_id] = q
            
            t = threading.Thread(
                target=run_generation_task,
                args=(chat_id, messages_for_ollama, num_predict, num_ctx, action, user_prompt, is_new_chat, files_to_cleanup, active_model, ollama_options, keep_alive_param),
                daemon=True
            )
            t.start()
            thread_started = True

            while True:
                try:
                    msg_type, content = q.get(timeout=2.0)
                    if msg_type == "done":
                        break
                    elif msg_type == "error":
                        yield f"data: {json.dumps({'error': content})}\n\n"
                        break
                    elif msg_type == "status":
                        yield f"data: {json.dumps({'status': content})}\n\n"
                    elif msg_type == "chunk":
                        yield f"data: {json.dumps({'chunk': content})}\n\n"
                    elif msg_type == "title_update":
                        yield f"data: {json.dumps({'title_update': content})}\n\n"
                except queue.Empty:
                    yield ": keepalive ping\n\n"
                    
        except GeneratorExit:
            if chat_id:
                active_streams[chat_id] = False
            return
                
        except Exception as e:
            yield f"data: {json.dumps({'error': f'An unknown error occurred: {str(e)}'})}\n\n"            
        finally:
            if not thread_started:
                cleanup_files(files_to_cleanup)
                is_system_busy = False
                active_chat_id = None
                if chat_id:
                    active_streams.pop(chat_id, None)
                    task_queues.pop(chat_id, None)

        yield "data: [DONE]\n\n"

    return Response(stream_with_context(stream_generator()), mimetype='text/event-stream')