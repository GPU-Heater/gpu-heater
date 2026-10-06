import os
import json
import subprocess
import difflib
from flask import Blueprint, request, jsonify, Response, stream_with_context
from blueprints.utils import get_ollama_client
from blueprints.database import get_setting, set_setting
from blueprints.config import IGNORE_DIRS, DEFAULT_EXTS
from blueprints.knowledge_base import search_knowledge_base, add_document_to_db

coder_bp = Blueprint('coder', __name__)

def scan_workspace(workspace_path=None, only_tree=False):
    if not workspace_path:
        workspace_path = get_setting("workspace_path")
    
    if not workspace_path or not os.path.exists(workspace_path):
        return ""

    map_path = os.path.join(workspace_path, "workspace_map.json")
    if os.path.exists(map_path) and not only_tree:
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                return f"[Project Architectural Map]:\n{f.read()}"
        except Exception:
            pass

    file_tree = []
    file_contents = []

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in DEFAULT_EXTS:
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, workspace_path)
                file_tree.append(rel_path)
                
                if not only_tree:
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            file_contents.append(f"\n--- {rel_path} ---\n{content}\n")
                    except Exception:
                        pass

    tree_str = "Project File Tree:\n" + "\n".join(file_tree)
    if only_tree: 
        return tree_str
    
    context_str = "".join(file_contents)
    return f"{tree_str}\n\nProject File Contents:{context_str}"

@coder_bp.route("/api/coder/create", methods=["POST"])
def create_workspace():
    data = request.json
    path = data.get("path", "")
    if path and os.path.exists(path):
        set_setting("workspace_path", path)
        return jsonify({"success": True, "message": f"Workspace set to: {path}"})
    return jsonify({"success": False, "error": "Invalid directory or path not found."}), 400

@coder_bp.route("/api/coder/inspect", methods=["POST"])
def inspect_workspace():
    data = request.json
    path = data.get("path", "")
    if path and os.path.exists(path):
        set_setting("workspace_path", path)

    result = scan_workspace(only_tree=False)
    if not result:
        return jsonify({"success": False, "error": "Project directory is empty or unreadable."})
        
    return jsonify({
        "success": True, 
        "message": "Workspace scanned successfully.", 
        "data": result[:500] + "...(truncated)"
    })

@coder_bp.route("/api/coder/ide/completion", methods=["POST"])
def ide_completion():
    data = request.json
    current_file = data.get("current_file", "")
    file_content = data.get("file_content", "")
    cursor_context = data.get("cursor_context", "")
    workspace_path = data.get("workspace_path", "")
    
    workspace_ctx = scan_workspace(workspace_path, only_tree=True)
    
    prompt = "You are an expert IDE code completion assistant. Only write the missing code, don't use any Markdown, additional explanations or conversation sentences.\n\n"
    if workspace_ctx: prompt += f"[Project Tree]:\n{workspace_ctx}\n\n"
    prompt += f"[Current File]: {current_file}\n[File Content]:\n{file_content}\n\n"
    prompt += f"Complete/optimize the following section:\n{cursor_context}"

    try:
        client = get_ollama_client()
        res = client.chat(model=get_setting("coder_model"), messages=[{"role": "user", "content": prompt}], options={"num_predict": 1024, "temperature": 0.1})
        completion = res.get('message', {}).get('content', '')
        return jsonify({"success": True, "completion": completion})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@coder_bp.route("/api/coder/ide/fix-error", methods=["POST"])
def ide_fix_error():
    data = request.json
    error_traceback = data.get("error", "")
    current_file = data.get("current_file", "")
    file_content = data.get("file_content", "")
    workspace_path = data.get("workspace_path", "")
    use_kb = data.get("use_knowledge_base", True)
    
    workspace_ctx = scan_workspace(workspace_path, only_tree=False)
    
    kb_context = ""
    if use_kb:
        query = f"{error_traceback}\n{file_content[:300]}"
        found_docs = search_knowledge_base(query, n_results=2)
        if found_docs:
            kb_context = f"\n\n[Trained Knowledge Base Reference]:\n{found_docs}\n"
    
    prompt = "You are an expert Senior Developer and Debugger. Analyze the error, briefly explain the cause, and provide the corrected complete code.\n\n"
    if kb_context: prompt += kb_context
    if workspace_ctx: prompt += f"[Complete Project Context]:\n{workspace_ctx}\n\n"
    prompt += f"[Error-prone File]: {current_file}\n[File Content]:\n{file_content}\n\n"
    prompt += f"[Stacktrace / Error Output]:\n{error_traceback}"

    try:
        client = get_ollama_client()
        res = client.chat(model=get_setting("coder_model"), messages=[{"role": "user", "content": prompt}], options={"num_predict": 4096, "num_ctx": 16384, "temperature": 0.2})
        fix = res.get('message', {}).get('content', '')
        return jsonify({"success": True, "fix": fix})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@coder_bp.route("/api/coder/ide/train-snippet", methods=["POST"])
def train_snippet():
    data = request.json
    content = data.get("content", "")
    filename = data.get("filename", "Snippet")
    
    if not content:
        return jsonify({"success": False, "error": "No content provided to train."}), 400
        
    try:
        add_document_to_db(content, filename)
        return jsonify({"success": True, "message": f"{filename} trained successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@coder_bp.route("/api/coder/apply-files", methods=["POST"])
def apply_files():
    payload = request.json
    workspace_path = get_setting("workspace_path")
    if not workspace_path or not os.path.exists(workspace_path):
        return jsonify({"success": False, "error": "Workspace path is not configured."}), 400

    created_files = []
    for item in payload.get("files", []):
        filepath = item.get("filepath")
        content = item.get("content")
        full_path = os.path.join(workspace_path, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        clean_content = content or "" 
        
        if "```" in clean_content:
            clean_content = clean_content.split("```")[1]
            if "\n" in clean_content:
                clean_content = clean_content[clean_content.find("\n")+1:]
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(clean_content.strip())
        created_files.append(filepath)

    return jsonify({"success": True, "created": created_files})

@coder_bp.route("/api/coder/generate-workspace-map", methods=["POST"])
def generate_workspace_map():
    workspace_path = get_setting("workspace_path")
    if not workspace_path or not os.path.exists(workspace_path):
        return jsonify({"success": False, "error": "Workspace path is not configured."}), 400

    raw_context = scan_workspace(only_tree=False)
    prompt = (
        "You are an expert software architect. Analyze the project file tree and content. "
        "Return a clean JSON object summarizing the project's architecture, hierarchy, and the purpose of each file. "
        "Only output in JSON format, no additional explanations.\n\n"
        f"{raw_context}"
    )

    try:
        client = get_ollama_client()
        response = client.chat(model=get_setting("coder_model"), messages=[{"role": "user", "content": prompt}], options={"num_predict": -1})
        json_content = response.get('message', {}).get('content', '')
        
        if "```json" in json_content:
            json_content = json_content.split("```json")[1].split("```")[0].strip()
        elif "```" in json_content:
            json_content = json_content.split("```")[1].strip()

        map_path = os.path.join(workspace_path, "workspace_map.json")
        with open(map_path, "w", encoding="utf-8") as f:
            f.write(json_content)

        return jsonify({"success": True, "message": "workspace_map.json created successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@coder_bp.route("/api/coder/scaffold_stream", methods=["POST"])
def scaffold_project_stream():
    payload = request.json
    user_prompt = payload.get("prompt", "")
    framework = payload.get("framework", "Fullstack")
    use_kb = payload.get("use_knowledge_base", True)

    kb_context = ""
    if use_kb:
        from blueprints.knowledge_base import search_knowledge_base
        found_docs = search_knowledge_base(f"{framework} {user_prompt}", n_results=2)
        if found_docs:
            kb_context = f"\n\n[Trained Knowledge Base / Best Practices]:\n{found_docs}\n(Please follow these standards while creating the project.)\n"

    def project_generator():
        client = get_ollama_client()
        yield f"data: {json.dumps({'status': '🏗️ Project and file structure planning...'})}\n\n"

        plan_prompt = f"""You are a Lead Software Architect.
Requirement: {user_prompt}
Tech: {framework}
{kb_context}
Return ONLY a valid JSON list of files to generate in creation order. No markdown codeblock wrap.
Example format:
[
  {{"path": "requirements.txt", "description": "Dependencies"}},
  {{"path": "src/main.py", "description": "Entry point"}}
]"""
        try:
            res = client.chat(
                model=get_setting("coder_model"),
                messages=[{"role": "user", "content": plan_prompt}],
                options={"num_predict": 1024, "temperature": 0.1}
            )
            raw_plan = res['message']['content'].replace("```json", "").replace("```", "").strip()
            file_plan = json.loads(raw_plan)
        except Exception:
            file_plan = [{"path": "main_app.py", "description": "Full application code"}]

        yield f"data: {json.dumps({'status': f'📦 Plan created ({len(file_plan)} files). Starting generation...'})}\n\n"

        created_files_context = ""

        for idx, file_info in enumerate(file_plan):
            file_path = file_info.get("path")
            desc = file_info.get("description")

            yield f"data: {json.dumps({'status': f'✍️ Generating [{idx+1}/{len(file_plan)}]: {file_path}...', 'current_file': file_path})}\n\n"

            code_prompt = f"""You are writing the full, production-ready code for the file: `{file_path}`.
Requirement: {user_prompt}
Role of this file: {desc}

Already planned/written files context:
{created_files_context}

CRITICAL RULES:
- Write the 100% COMPLETE code for this file.
- NEVER use placeholders like 'TODO', '// write logic here', or truncate code.
- Enclose the code inside a standard markdown codeblock with appropriate syntax."""

            response = client.chat(
                model=get_setting("coder_model"),
                messages=[{"role": "user", "content": code_prompt}],
                stream=True,
                options={"num_predict": -1, "num_ctx": 16384, "temperature": 0.2}
            )

            yield f"data: {json.dumps({'file_start': file_path})}\n\n"
            
            for chunk in response:
                chunk_text = chunk.get('message', {}).get('content', '')
                yield f"data: {json.dumps({'chunk': chunk_text})}\n\n"

            yield f"data: {json.dumps({'file_end': file_path})}\n\n"
            created_files_context += f"\n- `{file_path}`: {desc} (Generated)"

        yield f"data: {json.dumps({'status': '✅ All files generated successfully!'})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(stream_with_context(project_generator()), mimetype='text/event-stream')

@coder_bp.route("/api/coder/ide/inline-action", methods=["POST"])
def ide_inline_action():
    data = request.get_json(force=True, silent=True) or {}
    
    selected_code = data.get("selected_code", "")
    action_type = data.get("action_type", "refactor")
    language = data.get("language", "plaintext")
    use_kb = data.get("use_knowledge_base", True)
    
    if not selected_code:
        return jsonify({"success": False, "error": "No code provided"}), 400
    
    if action_type == "generateTests":
        action_type = "tests"

    kb_context = ""
    if use_kb:
        found_docs = search_knowledge_base(selected_code[:500], n_results=2)
        if found_docs:
            kb_context = f"\n\n[Trained Knowledge Base Reference]:\n{found_docs}\n"

    prompts = {
        "refactor": f"Refactor the following {language} code to improve readability, efficiency, and adherence to clean architecture principles.{kb_context} Return ONLY the refactored code block:\n\n```{language}\n{selected_code}\n```",
        "tests": f"Write complete unit tests for the following {language} code using standard test frameworks.{kb_context} Return ONLY the unit test code block:\n\n```{language}\n{selected_code}\n```",
        "explain": f"Explain what the following {language} code does step by step in clear bullet points.{kb_context}\n\n```{language}\n{selected_code}\n```",
        "optimize": f"Analyze time/space complexity and optimize the performance of this {language} code.{kb_context} Return ONLY the optimized code:\n\n```{language}\n{selected_code}\n```"
    }

    prompt = prompts.get(action_type, prompts["refactor"])

    try:
        client = get_ollama_client()
        res = client.chat(
            model=get_setting("coder_model"), 
            messages=[{"role": "user", "content": prompt}], 
            options={"num_predict": 4096, "num_ctx": 16384, "temperature": 0.2}
        )
        
        content = res.get('message', {}).get('content', '')
        if not content:
            return jsonify({"success": False, "error": "Model response empty or context limit exceeded."}), 400
            
        return jsonify({"success": True, "result": content.strip()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@coder_bp.route("/api/coder/ide/fim-complete", methods=["POST"])
def ide_fim_complete():
    data = request.json
    prefix = data.get("prefix", "")
    suffix = data.get("suffix", "")
    
    fim_prompt = f"<|fim_prefix|>{prefix}<|fim_suffix|>{suffix}<|fim_middle|>"

    try:
        client = get_ollama_client()
        res = client.generate(
            model=get_setting("coder_model"), 
            prompt=fim_prompt, 
            raw=True, 
            options={"num_predict": 256, "temperature": 0.1, "stop": ["<|fim_prefix|>", "<|fim_suffix|>", "<|fim_middle|>", "<|endoftext|>"]}
        )
        return jsonify({"success": True, "completion": res.get("response", "")})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def run_git_command(args, cwd):
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return res.returncode == 0, res.stdout, res.stderr
    except Exception as e:
        return False, "", str(e)

@coder_bp.route("/api/coder/git/status", methods=["GET"])
def git_status():
    workspace_path = get_setting("workspace_path")
    if not workspace_path or not os.path.exists(workspace_path):
        return jsonify({"success": False, "error": "Workspace path is not set."}), 400

    success, stdout, stderr = run_git_command(["status", "--porcelain"], workspace_path)
    if not success:
        return jsonify({"success": False, "error": f"Git error: {stderr}"}), 500

    changes = []
    for line in stdout.splitlines():
        if line.strip():
            status_code = line[:2].strip()
            file_name = line[3:].strip()
            changes.append({"status": status_code, "file": file_name})

    return jsonify({"success": True, "workspace": workspace_path, "changes": changes})

@coder_bp.route("/api/coder/git/diff-preview", methods=["POST"])
def git_diff_preview():
    data = request.json
    filepath = data.get("filepath", "")
    new_content = data.get("content", "")
    
    workspace_path = get_setting("workspace_path")
    if not workspace_path or not os.path.exists(workspace_path):
        return jsonify({"success": False, "error": "Workspace is not set."}), 400

    full_path = os.path.join(workspace_path, filepath)
    
    original_content = ""
    if os.path.exists(full_path):
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                original_content = f.read()
        except Exception as e:
            return jsonify({"success": False, "error": f"File could not be read: {str(e)}"}), 500

    clean_new_content = new_content
    if "```" in clean_new_content:
        clean_new_content = clean_new_content.split("```")[1]
        if "\n" in clean_new_content:
            clean_new_content = clean_new_content[clean_new_content.find("\n")+1:]
    clean_new_content = clean_new_content.strip()

    orig_lines = original_content.splitlines(keepends=True)
    new_lines = [l + "\n" for l in clean_new_content.splitlines()]
    
    diff = list(difflib.unified_diff(
        orig_lines,
        new_lines,
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
        lineterm=""
    ))

    return jsonify({
        "success": True,
        "filepath": filepath,
        "is_new_file": not os.path.exists(full_path),
        "diff": "".join(diff) if diff else "No changes detected."
    })

@coder_bp.route("/api/coder/git/apply-patch", methods=["POST"])
def git_apply_patch():
    data = request.json
    filepath = data.get("filepath", "")
    content = data.get("content", "")
    
    workspace_path = get_setting("workspace_path")
    if not workspace_path or not os.path.exists(workspace_path):
        return jsonify({"success": False, "error": "Workspace path missing."}), 400

    full_path = os.path.join(workspace_path, filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    clean_content = content
    if "```" in clean_content:
        clean_content = clean_content.split("```")[1]
        if "\n" in clean_content:
            clean_content = clean_content[clean_content.find("\n")+1:]

    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(clean_content.strip())
        return jsonify({"success": True, "message": f"{filepath} updated."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@coder_bp.route("/api/coder/git/commit", methods=["POST"])
def git_commit():
    data = request.json
    commit_msg = data.get("message", "AI refactor updates")
    files = data.get("files", [])
    
    workspace_path = get_setting("workspace_path")
    if not workspace_path or not os.path.exists(workspace_path):
        return jsonify({"success": False, "error": "Workspace path missing."}), 400

    add_targets = files if files else ["."]
    success, _, stderr = run_git_command(["add"] + add_targets, workspace_path)
    if not success:
        return jsonify({"success": False, "error": f"Git add error: {stderr}"}), 500

    success, stdout, stderr = run_git_command(["commit", "-m", commit_msg], workspace_path)
    if not success:
        return jsonify({"success": False, "error": f"Git commit error: {stderr}"}), 500

    return jsonify({"success": True, "output": stdout})