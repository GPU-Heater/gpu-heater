import os
import json
import random
import time
import urllib.request
import urllib.parse
import uuid
from werkzeug.utils import secure_filename

from blueprints.config import COMFYUI_URL, GENERATED_MEDIA_FOLDER
from blueprints.prompt_manager import enhance_generation_prompt

def load_workflow(action):
    base_dir = "workflows"
    
    if action == "to music":
        workflow_file = f"{base_dir}/to_music.json"
    elif action == "to audio":
        workflow_file = f"{base_dir}/to_audio.json"
    elif action == "to 3d model":
        workflow_file = f"{base_dir}/to_3d_model.json"
        
    elif action in ["to image", "to ref image"]:
        workflow_file = f"{base_dir}/to_image_txt2img.json"
    elif action == "to i2i":
        workflow_file = f"{base_dir}/to_image_img2img.json"
        
    elif action in ["to video", "to ref video"]:
        workflow_file = f"{base_dir}/to_video_txt2vid.json"
    elif action == "to i2v":
        workflow_file = f"{base_dir}/to_video_img2vid.json"
    elif action == "to outpaint":
        workflow_file = f"{base_dir}/outpaint.json"
    else:
        raise ValueError(f"Unknown action: {action}")

    if not os.path.exists(workflow_file):
        raise FileNotFoundError(f"Workflow file is missing: {workflow_file}")
        
    with open(workflow_file, "r", encoding="utf-8") as f:
        return json.load(f)
    
def download_comfy_file_to_local(filename, subfolder="", folder_type="output"):
    params = urllib.parse.urlencode({
        "filename": filename,
        "subfolder": subfolder,
        "type": folder_type
    })
    file_url = f"{COMFYUI_URL}/view?{params}"
    
    ext = os.path.splitext(filename)[1].lower()
    local_filename = f"comfy_{uuid.uuid4().hex[:8]}_{secure_filename(filename)}"
    local_filepath = os.path.join(GENERATED_MEDIA_FOLDER, local_filename)
    
    try:
        urllib.request.urlretrieve(file_url, local_filepath)
        return f"/generated_media/{local_filename}", ext
    except Exception:
        return file_url, ext

def handle_comfyui_request(action, prompt, file_path=None, chat_id=None, active_streams=None, **kwargs):
    uploaded_filename = None
    has_image = bool(file_path and os.path.exists(file_path))
    
    if has_image:
        try:
            yield "status", "📤 Uploading file to ComfyUI..."
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            filename = secure_filename(os.path.basename(file_path))
            boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
            
            body = (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"image\"; filename=\"{filename}\"\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n"
            ).encode('utf-8') + file_data + f"\r\n--{boundary}--\r\n".encode('utf-8')
            
            req = urllib.request.Request(f"{COMFYUI_URL}/upload/image", data=body)
            req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
            
            with urllib.request.urlopen(req, timeout=15) as response:
                res_json = json.loads(response.read())
                uploaded_filename = res_json.get("name")
                yield "status", f"✅ File uploaded: {uploaded_filename}"
        except Exception as e:
            yield "chunk", f"<br><span style='color:var(--danger)'>File upload error: {str(e)}</span>"
            return

    if action in ["to 3d model", "to outpaint"] and not uploaded_filename:
        yield "chunk", f"<br><span style='color:var(--danger)'>An image is required for {action}.</span>"
        return

    enhanced_prompt = prompt or ""
    extra_params = {}
    bypass_enhancing = kwargs.get("bypass_enhancing", False)
    
    if prompt and prompt.strip():
        if bypass_enhancing and action not in ["to music", "to ref video", "to ref image"]:
            enhanced_prompt = prompt
            yield "status", "⚡ Prompt enhancing bypassed..."
        else:
            yield "status", "🧠 AI is enhancing your prompt..."
            try:
                enhanced_prompt, extra_params = enhance_generation_prompt(action, prompt)
            except Exception:
                enhanced_prompt = prompt
    
    try:
        workflow = load_workflow(action)

        for node_id, node in workflow.items():
            inputs = node.get("inputs", {})
            meta = node.get("_meta", {})
            title = meta.get("title", "").lower()
            class_type = node.get("class_type", "")
            
            for seed_key in ["seed", "noise_seed"]:
                if seed_key in inputs:
                    inputs[seed_key] = random.randint(1, 999999999999999)
                    
            if class_type == "LoadImage":
                if uploaded_filename:
                    inputs["image"] = uploaded_filename
                elif action not in ["to video", "to i2v", "to i2i"]:
                    raise ValueError(f"An image file is required for this action: {action}")
                    
            if enhanced_prompt and enhanced_prompt.strip() and action != "to outpaint":
                if action == "to music":
                    if class_type == "TextEncodeAceStepAudio1.5":
                        if "|" in prompt:
                            tags_part, lyrics_part = prompt.split("|", 1)
                            inputs["tags"] = tags_part.strip()
                            inputs["lyrics"] = lyrics_part.strip()
                        else:
                            inputs["tags"] = prompt 
                            inputs["lyrics"] = ""
                            
                        if extra_params:
                            inputs["bpm"] = extra_params.get("bpm", inputs.get("bpm"))
                            inputs["duration"] = extra_params.get("duration", inputs.get("duration"))
                            inputs["timesignature"] = str(extra_params.get("timesignature", inputs.get("timesignature")))
                            inputs["language"] = str(extra_params.get("language", inputs.get("language")))
                            inputs["keyscale"] = str(extra_params.get("keyscale", inputs.get("keyscale")))
                            
                    elif class_type == "EmptyAceStep1.5LatentAudio":
                        if extra_params and "duration" in extra_params:
                            inputs["seconds"] = extra_params["duration"]
                else:
                    if class_type == "PrimitiveStringMultiline" and "value" in inputs:
                        inputs["value"] = enhanced_prompt
                    if "text" in inputs and isinstance(inputs["text"], str):
                        if "negative" not in title and "neg" not in title:
                            inputs["text"] = enhanced_prompt
                    if "tags" in inputs and isinstance(inputs["tags"], str):
                        inputs["tags"] = enhanced_prompt
                        
        if action == "to outpaint":
            if "110:75" in workflow:
                workflow["110:75"]["inputs"]["left"] = int(kwargs.get("op_left", 0))
                workflow["110:75"]["inputs"]["right"] = int(kwargs.get("op_right", 0))
                workflow["110:75"]["inputs"]["top"] = int(kwargs.get("op_top", 0))
                workflow["110:75"]["inputs"]["bottom"] = int(kwargs.get("op_bottom", 0))
            if "110:74" in workflow:
                workflow["110:74"]["inputs"]["text"] = enhanced_prompt if enhanced_prompt else ""

    except Exception as e:
        yield "chunk", f"<br><span style='color:var(--danger)'>Workflow processing error: {str(e)}</span>"
        return

    prompt_id = None
    try:
        yield "status", "🚀 Task added to ComfyUI queue..."
        data = json.dumps({"prompt": workflow}).encode('utf-8')
        req = urllib.request.Request(f"{COMFYUI_URL}/prompt", data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as response:
            prompt_res = json.loads(response.read())
            prompt_id = prompt_res.get("prompt_id")
    except Exception as e:
        yield "chunk", f"<br><span style='color:var(--danger)'>ComfyUI connection error: {str(e)}</span>"
        return

    if not prompt_id:
        yield "chunk", "<br><span style='color:var(--danger)'>ComfyUI failed to start the process.</span>"
        return

    try:
        start_time = time.time()
        max_wait = 1800
        
        while True:
            if chat_id and active_streams and not active_streams.get(chat_id, True):
                yield "chunk", "\n\n*[Process canceled by user]*"
                return
                
            elapsed = int(time.time() - start_time)
            if elapsed > max_wait:
                yield "chunk", "<br><span style='color:var(--danger)'>Timeout: ComfyUI processing took too long.</span>"
                return
                
            yield "status", f"⏳ ComfyUI rendering... ({elapsed} s)"
            
            try:
                history_req = urllib.request.Request(f"{COMFYUI_URL}/history/{prompt_id}")
                with urllib.request.urlopen(history_req, timeout=5) as h_res:
                    history_data = json.loads(h_res.read())
            except Exception:
                history_data = {}
                
            if prompt_id in history_data:
                yield "status", "📥 Saving outputs to generated_media..."
                outputs = history_data[prompt_id].get("outputs", {})
                media_elements = []
                
                for node_idx, node_output in outputs.items():
                    if "images" in node_output:
                        for img in node_output["images"]:
                            if img.get("type", "output") == "output":
                                filename = img.get("filename")
                                subfolder = img.get("subfolder", "")
                                folder_type = img.get("type", "output")
                                
                                serve_url, ext = download_comfy_file_to_local(filename, subfolder, folder_type)
                                
                                if ext in ['.mp4', '.webm', '.mov']:
                                    media_elements.append(
                                        f'<div style="margin-top:10px;">'
                                        f'<video controls style="max-width:100%; border-radius:8px;"><source src="{serve_url}">Video load failed.</video><br>'
                                        f'<a href="{serve_url}" download class="copy-btn" style="position:static; display:inline-block; margin-top:5px; text-decoration:none;"><i class="fas fa-download"></i> Download Video</a>'
                                        f'</div>'
                                    )
                                else:
                                    media_elements.append(
                                        f'<div style="margin-top:10px;">'
                                        f'<a href="{serve_url}" target="_blank"><img src="{serve_url}" style="max-width:100%; border-radius:8px;"></a><br>'
                                        f'<a href="{serve_url}" download class="copy-btn" style="position:static; display:inline-block; margin-top:5px; text-decoration:none;"><i class="fas fa-download"></i> Download Image</a>'
                                        f'</div>'
                                    )

                    if "gifs" in node_output or "videos" in node_output:
                        vids = node_output.get("gifs", []) + node_output.get("videos", [])
                        for vid in vids:
                            filename = vid.get("filename")
                            subfolder = vid.get("subfolder", "")
                            folder_type = vid.get("type", "output")
                            
                            serve_url, ext = download_comfy_file_to_local(filename, subfolder, folder_type)
                            media_elements.append(
                                f'<div style="margin-top:10px;">'
                                f'<video controls style="max-width:100%; border-radius:8px;"><source src="{serve_url}">Video load failed.</video><br>'
                                f'<a href="{serve_url}" download class="copy-btn" style="position:static; display:inline-block; margin-top:5px; text-decoration:none;"><i class="fas fa-download"></i> Download Video</a>'
                                f'</div>'
                            )
                                    
                    if "audio" in node_output:
                        for aud in node_output["audio"]:
                            if aud.get("type", "output") == "output":
                                filename = aud.get("filename")
                                subfolder = aud.get("subfolder", "")
                                folder_type = aud.get("type", "output")
                                
                                serve_url, ext = download_comfy_file_to_local(filename, subfolder, folder_type)
                                media_elements.append(
                                    f'<div style="margin-top:10px;">'
                                    f'<audio controls style="width:100%;"><source src="{serve_url}">Audio load failed.</audio><br>'
                                    f'<a href="{serve_url}" download class="copy-btn" style="position:static; display:inline-block; margin-top:5px; text-decoration:none;"><i class="fas fa-download"></i> Download Audio</a>'
                                    f'</div>'
                                )
                                
                    if "mesh" in node_output:
                        for m in node_output["mesh"]:
                            if m.get("type", "output") == "output":
                                filename = m.get("filename")
                                subfolder = m.get("subfolder", "")
                                folder_type = m.get("type", "output")
                                
                                serve_url, ext = download_comfy_file_to_local(filename, subfolder, folder_type)
                                media_elements.append(
                                    f'<div style="margin-top:10px; padding:15px; background:rgba(255,255,255,0.05); border-radius:8px; border:1px solid var(--accent);">'
                                    f'<i class="fas fa-cube" style="color:var(--accent); margin-right:8px;"></i> <b>3D Model Ready:</b> '
                                    f'<a href="{serve_url}" target="_blank" download style="color:var(--accent); text-decoration:underline;">Download Model</a>'
                                    f'</div>'
                                )

                if media_elements:
                    prompt_info = f"*Prompt:* `{enhanced_prompt}`\n\n" if enhanced_prompt else ""
                    final_html = f"**🎨 Action Completed:** `{action}`\n\n{prompt_info}" + "\n".join(media_elements)
                    yield "chunk", final_html
                    return
                else:
                    yield "chunk", "<br><span style='color:var(--danger)'>ComfyUI finished but returned no output file.</span>"
                    return
                    
            time.sleep(3)
    except Exception as e:
        yield "chunk", f"<br><span style='color:var(--danger)'>ComfyUI check error: {str(e)}</span>"
        return