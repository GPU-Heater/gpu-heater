import json
import re
from blueprints.database import get_setting
from blueprints.utils import get_ollama_client

def enhance_generation_prompt(action, raw_prompt):
    if not raw_prompt or not raw_prompt.strip():
        return raw_prompt, {}

    system_prompts = {
        "to music": (
            "You are an expert musician and producer. Analyze the user prompt and return ONLY a valid JSON object "
            "defining: 'bpm' (int), 'duration' (int), 'timesignature' (string), 'language' (string, e.g., 'en'), and 'keyscale' (string)."
        ),
        "to image": (
            "You are an expert AI image prompt engineer. Enhance the user's idea into a highly detailed, descriptive, "
            "and vivid image generation prompt in English. Focus on lighting, composition, style, and atmosphere. "
            "Return ONLY the enhanced prompt text, nothing else."
        ),
        "to i2i": (
            "You are an expert AI Image-to-Image prompt engineer. Enhance the user's idea into a targeted transformation prompt in English. "
            "Focus STRICTLY on the desired style transfer, specific modifications, lighting adjustments, and visual alterations while preserving the core composition. "
            "Avoid re-describing elements of the base image that should remain unchanged. Return ONLY the enhanced prompt text, nothing else."
        ),
        "to video": (
            "You are an expert AI video prompt engineer. Enhance the user's idea into a detailed video generation prompt in English. "
            "Describe the motion, camera angle, subject actions, and cinematic lighting. Return ONLY the enhanced prompt text, nothing else."
        ),
        "to i2v": (
            "You are an expert AI video prompt engineer. Enhance the user prompt into simple, direct cinematic movement terms in English. "
            "Describe ONLY clear actions: subject movement, natural speech, crowd reaction, and simple camera motion (zoom, pan). "
            "NEVER use medical/anatomical jargon (like mandibular, flexion, thoracic). "
            "Do NOT mention any text, words, or signs from the image. Return ONLY the concise enhanced prompt."
        ),
        "to 3d model": (
            "You are an expert 3D artist. Enhance the user's idea into a clear, descriptive prompt for 3D model generation in English. "
            "Focus on geometry, texture, material, and object details. Return ONLY the enhanced prompt text, nothing else."
        ),
        "to audio": (
            "You are an expert sound designer. Enhance the user's idea into a descriptive sound effect or audio prompt in English. "
            "Describe the timbre, environment, and acoustics. Return ONLY the enhanced prompt text, nothing else."
        ),
        "to ref video": (
            "You are an expert AI video director. The user provides a reference image description alongside their custom idea. "
            "Synthesize both into a coherent, highly detailed Text-to-Video generation prompt in English. "
            "Describe the overall scene, lighting, subjects, and smooth cinematic motion (such as camera pull-backs or pans). "
            "Do NOT include literal text/slogans on signs unless explicitly required. Return ONLY the enhanced prompt."
        ),
        "to ref image": (
            "You are an expert AI image prompt engineer. The user provides a reference image description alongside their custom idea. "
            "Synthesize both into a rich, descriptive Text-to-Image prompt in English focusing on style, composition, mood, and lighting. "
            "Return ONLY the enhanced prompt."
        )
    }

    sys_prompt = system_prompts.get(action, "Enhance this prompt for AI generation. Return ONLY the prompt.")

    try:
        client = get_ollama_client()
        res = client.chat(model=get_setting("default_model"), messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": raw_prompt}
        ])
        
        content = res['message']['content'].strip()

        if action == "to music":
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return raw_prompt, json.loads(json_match.group(0))
            return raw_prompt, {}
        else:
            return content, {}
            
    except Exception as e:
        print(f"Prompt enhancement failed: {e}")
        return raw_prompt, {}