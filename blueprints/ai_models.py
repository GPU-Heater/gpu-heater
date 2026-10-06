import os
import warnings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "models_cache")

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HOME"] = os.path.join(CACHE_DIR, "huggingface")
os.environ["TRANSFORMERS_CACHE"] = os.path.join(CACHE_DIR, "huggingface")
os.environ["TORCH_HOME"] = os.path.join(CACHE_DIR, "torch")
os.environ["XDG_CACHE_HOME"] = CACHE_DIR
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

warnings.filterwarnings("ignore", category=FutureWarning)

import torch
import torchaudio

try:
    import perth
    if not hasattr(perth, "PerthImplicitWatermarker") or perth.PerthImplicitWatermarker is None:
        class DummyWatermarker:
            def __init__(self, *args, **kwargs): pass
            def apply_watermark(self, wav, *args, **kwargs): return wav
        perth.PerthImplicitWatermarker = DummyWatermarker
except Exception:
    pass

_stt_model = None
_audio_classifier = None
_tts_engine = None

whisper_cache = os.path.join(CACHE_DIR, "whisper")

def get_stt_model():
    global _stt_model
    if _stt_model is None:
        try:
            from faster_whisper import WhisperModel
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            
            model_size = "medium"
            size_file_path = os.path.join(BASE_DIR, "whisper_model.txt")
            if os.path.exists(size_file_path):
                with open(size_file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        model_size = content
            
            print(f"-> Loading STT Model: Whisper ({model_size})")
            _stt_model = WhisperModel(model_size, device=device, compute_type=compute_type, download_root=whisper_cache)
        except Exception as e:
            print(f"[STT Load Warning]: {e}")
            _stt_model = None
    return _stt_model

def get_audio_classifier():
    global _audio_classifier
    if _audio_classifier is None:
        try:
            from transformers import pipeline
            device = 0 if torch.cuda.is_available() else -1
            _audio_classifier = pipeline(
                "audio-classification",
                model="MIT/ast-finetuned-audioset-10-10-0.4593",
                device=device
            )
        except Exception as e:
            print(f"[Audio Classifier Load Warning]: {e}")
            _audio_classifier = None
    return _audio_classifier

def get_tts_engine():
    global _tts_engine
    if _tts_engine is None:
        try:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS
            tts_device = "cuda" if torch.cuda.is_available() else "cpu"
            _tts_engine = ChatterboxMultilingualTTS.from_pretrained(device=tts_device)
        except Exception as e:
            print(f"[TTS Engine Load Warning]: {e}")
            _tts_engine = None
    return _tts_engine

tts_engine = True

def get_sanitized_reference_voice(voice_path, max_duration_sec=7.5):
    try:
        waveform, sample_rate = torchaudio.load(voice_path)
        max_samples = int(max_duration_sec * sample_rate)
        if waveform.shape[-1] > max_samples:
            waveform = waveform[:, :max_samples]
            temp_path = voice_path + "_sanitized.wav"
            torchaudio.save(temp_path, waveform, sample_rate)
            return temp_path
    except Exception:
        pass
    return voice_path

def trim_trailing_artifacts(wav_tensor, sample_rate=24000, threshold_db=-35):
    if not isinstance(wav_tensor, torch.Tensor):
        wav_tensor = torch.tensor(wav_tensor)
    amplitude = torch.abs(wav_tensor)
    max_amp = torch.max(amplitude)
    if max_amp == 0:
        return wav_tensor
    threshold = max_amp * (10 ** (threshold_db / 20))
    non_silent_indices = torch.where(amplitude > threshold)[-1]
    if len(non_silent_indices) > 0:
        last_index = non_silent_indices[-1].item()
        cutoff = min(wav_tensor.shape[-1], last_index + int(sample_rate * 0.1))
        return wav_tensor[..., :cutoff]
    return wav_tensor

def generate_tts_audio(text, lang, voice_path, output_path):
    engine = get_tts_engine()
    if not engine:
        raise Exception("Chatterbox model is not available or not installed.")
    
    clean_voice_path = get_sanitized_reference_voice(voice_path)
    try:
        wav = engine.generate(
            text=text,
            language_id=lang,
            audio_prompt_path=clean_voice_path
        )
    finally:
        if clean_voice_path != voice_path and os.path.exists(clean_voice_path):
            try:
                os.remove(clean_voice_path)
            except Exception:
                pass
    
    if not isinstance(wav, torch.Tensor):
        wav = torch.tensor(wav)
    if wav.dim() == 1:
        wav = wav.unsqueeze(0)

    sr = getattr(engine, 'sr', 24000)
    cleaned_wav = trim_trailing_artifacts(wav, sample_rate=sr)
    torchaudio.save(output_path, cleaned_wav.cpu(), sr)