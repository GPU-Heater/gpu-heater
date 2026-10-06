import os
import base64
import re
import requests
import trafilatura
from bs4 import BeautifulSoup
from ddgs import DDGS
from PIL import Image
from moviepy import VideoFileClip

from ollama import Client

from blueprints.config import OLLAMA_HOST
from blueprints.database import get_setting, set_setting
from blueprints.ai_models import get_stt_model, get_audio_classifier

def get_ollama_client():
    t_en = get_setting("timeout_enabled") == "true"
    
    if t_en:
        t_sec_str = get_setting("timeout_sec")
        try:
            timeout_val = float(t_sec_str)
        except Exception:
            timeout_val = 300.0
    else:
        timeout_val = None 
        
    return Client(host=OLLAMA_HOST, timeout=timeout_val)

def search_duckduckgo(query, max_results=3):
    try:
        results = []
        ddgs = DDGS()
        for r in ddgs.text(query, max_results=max_results):
            results.append(f"Title: {r.get('title')}\nSummary: {r.get('body')}\nSource: {r.get('href')}")
        return "\n\n".join(results)
    except Exception:
        return ""

def extract_and_save_context(user_message):
    current_context = get_setting("personal_context")
    sys_msg = "You are an information extraction tool. Extract PERMANENT, PERSONAL facts or preferences about the user from their message. If none exist, type 'NONE'. If they exist, format them as short bullet points."
    try:
        client = get_ollama_client()
        response = client.chat(model=get_setting("default_model"), messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_message}], options={"num_ctx": 4096})
        extracted = response['message']['content'].strip()
        if extracted and "NONE" not in extracted.upper() and len(extracted) > 4:
            new_context = current_context + "\n- " + extracted if current_context else "- " + extracted
            set_setting("personal_context", new_context.strip())
    except:
        pass

def generate_chat_title(summary_context):
    prompt = (
        "Generate a very concise, descriptive chat title (maximum 3 to 5 words) based on this conversation summary. "
        "Return ONLY the title itself. Do not use quotes, punctuation marks, or introductory phrases.\n\n"
        f"Conversation:\n{summary_context}"
    )
    try:
        title_model = get_setting("title_model")
        
        client = get_ollama_client()
        res = client.chat(
            model=title_model,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 15, "temperature": 0.3},
            keep_alive="0s"
        )
        title = res['message']['content'].strip()
        title = title.replace('"', '').replace("'", "").replace("\n", " ").strip()
        return title[:50]
    except Exception as e:
        print(f"Title Generation Error: {e}")
        return None

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def classify_audio_events(audio_path):
    try:
        classifier = get_audio_classifier()
        if not classifier:
            return "Audio classifier is not available."
        results = classifier(audio_path)
        detected_events = [f"{item['label']} ({int(item['score']*100)}%)" for item in results[:3]]
        return ", ".join(detected_events)
    except Exception:
        return "Audio type could not be detected."

def process_video(video_path, frame_interval_sec=2.0, max_frames=8):
    audio_path = video_path + ".wav"
    extracted_frames = []
    try:
        clip = VideoFileClip(video_path)
        if clip.audio is not None:
            clip.audio.write_audiofile(audio_path, fps=16000, codec='pcm_s16le', ffmpeg_params=["-ac", "1"], logger=None)
        else:
            audio_path = None
        duration = clip.duration
        current_time = 0.0
        frame_count = 0
        while current_time < duration and frame_count < max_frames:
            frame_array = clip.get_frame(current_time)
            img = Image.fromarray(frame_array)
            frame_filename = f"{video_path}_frame_{frame_count}.jpg"
            img.save(frame_filename, "JPEG")
            extracted_frames.append(frame_filename)
            frame_count += 1
            current_time += frame_interval_sec
        clip.close()
    except Exception:
        pass
    return audio_path, extracted_frames

def analyze_audio(audio_path):
    transcribed_text, audio_types = "", ""
    if audio_path and os.path.exists(audio_path):
        try:
            stt = get_stt_model()
            if stt:
                segments, _ = stt.transcribe(audio_path, beam_size=5, vad_filter=False)
                transcribed_text = " ".join([s.text for s in segments]).strip()
        except Exception:
            pass
        audio_types = classify_audio_events(audio_path)
    return transcribed_text, audio_types

def cleanup_files(file_list):
    for filepath in file_list:
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
            
def clean_markdown_for_tts(text):
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'http[s]?://\S+', '', text)
    text = re.sub(r'[*_`#]+', '', text)
    if text and text[-1] not in ['.', '!', '?', '…']:
        text += "."
    return text.strip()

def summarize_chunks_generator(text, user_prompt):
    chunk_size = 12000
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    client = get_ollama_client()
    combined_summary = ""
    
    for i, chunk in enumerate(chunks):
        yield {"status": f"🔍 Reading Part {i+1}/{len(chunks)}..."}
        sys_msg = "You are a data extraction assistant. Read this part of a large document and extract key information relevant to the user's prompt. Be concise and skip conversational filler."
        
        try:
            response = client.chat(model=get_setting("default_model"), messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": f"User's Goal: {user_prompt}\n\nDocument Part {i+1}:\n{chunk}"}
            ], stream=True, options={"num_predict": 1000, "num_ctx": 8192})
            
            chunk_res = ""
            for r in response:
                chunk_res += r['message']['content']
                yield {"ping": True}
                
            combined_summary += f"\n\n--- AI Summary of Part {i+1} ---\n{chunk_res.strip()}"
        except Exception as e:
            combined_summary += f"\n\n[Part {i+1} analysis failed: {e}]"
            
    yield {"done": combined_summary}

def extract_urls(text):
    url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
    return re.findall(url_pattern, text)

def scrape_webpage_content(url, max_chars=12000):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,tr;q=0.8"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return f"[The webpage could not be accessed. HTTP Error Code: {response.status_code}]"

        extracted_text = trafilatura.extract(response.text, include_comments=False, include_tables=True)

        if not extracted_text or len(extracted_text.strip()) < 100:
            soup = BeautifulSoup(response.text, 'html.parser')
            for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
                tag.decompose()
            extracted_text = soup.get_text(separator=' ', strip=True)

        if not extracted_text:
            return "[No readable text content found on the webpage.]"

        return extracted_text[:max_chars].strip()

    except Exception as e:
        return f"[Web scraping error: {str(e)}]"

def unload_ollama_models():
    try:
        res = requests.get(f"{OLLAMA_HOST}/api/ps")
        if res.status_code == 200:
            models = res.json().get("models", [])
            client = get_ollama_client()
            for m in models:
                client.chat(model=m["name"], messages=[], keep_alive=0)
    except Exception as e:
        print(f"Model Unload Error: {e}")