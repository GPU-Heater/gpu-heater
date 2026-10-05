#!/usr/bin/env bash
set -e

RED='\033[0;91m'
GREEN='\033[0;92m'
YELLOW='\033[0;93m'
CYAN='\033[0;96m'
RESET='\033[0m'

cd "$(dirname "$0")"

export PROJECT_DIR="$(pwd)"
export HF_HOME="$PROJECT_DIR/models_cache/huggingface"
export TRANSFORMERS_CACHE="$PROJECT_DIR/models_cache/huggingface"
export TORCH_HOME="$PROJECT_DIR/models_cache/torch"
export XDG_CACHE_HOME="$PROJECT_DIR/models_cache"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

mkdir -p "$HF_HOME" "$TORCH_HOME"

if [ ! -f "./venv/bin/python" ]; then
    echo -e "${CYAN}=========================================${RESET}"
    echo -e "${CYAN}           GPU-Heater Setup              ${RESET}"
    echo -e "${CYAN}=========================================${RESET}"

    install_package() {
        if command -v brew &> /dev/null; then
            brew install "$@"
        elif command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y "$@"
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y "$@"
        elif command -v pacman &> /dev/null; then
            sudo pacman -Sy --noconfirm "$@"
        fi
    }

    find_python() {
        for candidate in \
            "$(brew --prefix python@3.11 2>/dev/null)/bin/python3.11" \
            "$(brew --prefix python@3.12 2>/dev/null)/bin/python3.12" \
            "$(brew --prefix python@3.10 2>/dev/null)/bin/python3.10" \
            python3.11 python3.12 python3.10 python3 python
        do
            if [ -x "$candidate" ] || command -v "$candidate" &> /dev/null; then
                local ver
                ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
                if [[ "$ver" =~ ^3\.(10|11|12)$ ]]; then
                    echo "$candidate"
                    return 0
                fi
            fi
        done
        return 1
    }

    PYTHON_CMD=$(find_python || true)

    if [ -z "$PYTHON_CMD" ]; then
        echo -e "\n${YELLOW}[Prerequisite] Python 3.10-3.12 was not detected.${RESET}"
        read -r -p "Install Python 3.11 now? (Y/N): " install_py_choice
        if [[ "$install_py_choice" =~ ^[Yy]$ ]]; then
            if command -v brew &> /dev/null; then
                brew install python@3.11
            elif command -v apt-get &> /dev/null; then
                sudo apt-get update && sudo apt-get install -y python3.11 python3.11-venv python3-pip
            else
                install_package python3 python3-venv python3-pip
            fi
            PYTHON_CMD=$(find_python || true)
            if [ -z "$PYTHON_CMD" ]; then
                echo -e "${RED}Failed to locate compatible Python after installation.${RESET}"
                exit 1
            fi
        else
            echo -e "${RED}Please install Python 3.10, 3.11, or 3.12 manually.${RESET}"
            exit 1
        fi
    fi

    if ! command -v git &> /dev/null; then
        echo -e "\n${YELLOW}[Prerequisite] Git is missing.${RESET}"
        read -r -p "Install Git now? (Y/N): " install_git_choice
        if [[ "$install_git_choice" =~ ^[Yy]$ ]]; then
            install_package git
        fi
    fi

    if ! command -v ffmpeg &> /dev/null; then
        echo -e "\n${YELLOW}[Prerequisite] FFmpeg is missing.${RESET}"
        read -r -p "Install FFmpeg now? (Y/N): " install_ff_choice
        if [[ "$install_ff_choice" =~ ^[Yy]$ ]]; then
            install_package ffmpeg
        fi
    fi

    if ! command -v ollama &> /dev/null; then
        echo -e "\n${YELLOW}[Prerequisite] Ollama is missing.${RESET}"
        read -r -p "Install Ollama now? (Y/N): " install_ollama_choice
        if [[ "$install_ollama_choice" =~ ^[Yy]$ ]]; then
            curl -fsSL https://ollama.com/install.sh | sh
        fi
    fi

    OS_TYPE="$(uname -s)"
    ARCH_TYPE="$(uname -m)"

    echo -e "\n${YELLOW}Please select the PyTorch hardware target:${RESET}"
    if [ "$OS_TYPE" == "Darwin" ] && [ "$ARCH_TYPE" == "arm64" ]; then
        echo -e "${YELLOW}1) Apple Silicon (MPS - Recommended for M1/M2/M3/M4)${RESET}"
        echo -e "${YELLOW}2) CPU${RESET}"
    else
        echo -e "${YELLOW}1) NVIDIA GPU (CUDA 12.4 - Recommended)${RESET}"
        echo -e "${YELLOW}2) CPU${RESET}"
    fi
    read -r -p "Enter choice (1 or 2): " target_choice

    echo -e "\n${YELLOW}[Optional] Chatterbox TTS (Text-to-Speech) Model (~1-2 GB)${RESET}"
    echo -e "${YELLOW}Note: This model is used for generating spoken audio responses.${RESET}"
    echo -e "${YELLOW}If you skip this, text chat and voice recognition (STT) will work fine,${RESET}"
    echo -e "${YELLOW}but you will not be able to listen to voice responses.${RESET}"
    read -r -p "Do you want to download Chatterbox TTS model? (Y/N, Default: N): " install_tts_choice
    if [[ "$install_tts_choice" =~ ^[Yy]$ ]]; then
        ENABLE_CHATTERBOX=1
    else
        ENABLE_CHATTERBOX=0
    fi
    
    echo -e "\n${YELLOW}Please select Whisper (STT) model size:${RESET}"
    echo -e "${YELLOW}1) Small (Fast / Low VRAM)${RESET}"
    echo -e "${YELLOW}2) Medium (Balanced - Default)${RESET}"
    echo -e "${YELLOW}3) Large (High Accuracy / High VRAM)${RESET}"
    read -r -p "Enter choice (1, 2, or 3): " stt_choice

    case "$stt_choice" in
        1) WHISPER_SIZE="small" ;;
        3) WHISPER_SIZE="large-v3" ;;
        *) WHISPER_SIZE="medium" ;;
    esac

    echo "$WHISPER_SIZE" > "$PROJECT_DIR/whisper_model.txt"

    echo -e "\n${YELLOW}Please select Embedding model (Knowledge Base):${RESET}"
    echo -e "${YELLOW}1) Nomic Embed Text  (~274 MB - Fast, English, Code focused)${RESET}"
    echo -e "${YELLOW}2) BGE-M3            (~1.2 GB - High Accuracy, Best Multilingual)${RESET}"
    echo -e "${YELLOW}3) MXBAI Embed Large (~670 MB - High Accuracy, English Semantic Search)${RESET}"
    echo -e "${YELLOW}4) All-MiniLM        (~120 MB - Ultra Lightweight, Basic Matching)${RESET}"
    read -r -p "Enter choice (1, 2, 3, or 4): " emb_choice

    case "$emb_choice" in
        2) EMB_MODEL="bge-m3" ;;
        3) EMB_MODEL="mxbai-embed-large" ;;
        4) EMB_MODEL="all-minilm" ;;
        *) EMB_MODEL="nomic-embed-text" ;;
    esac

    echo "$EMB_MODEL" > "$PROJECT_DIR/embedding_model.txt"

    echo -e "\n${GREEN}[1/4] Creating virtual environment...${RESET}"
    "$PYTHON_CMD" -m venv venv

    PIP_PATH="./venv/bin/pip"
    PYTHON_PATH="./venv/bin/python"

    "$PIP_PATH" install --upgrade pip

    echo -e "\n${GREEN}[2/4] Installing requirements...${RESET}"
    "$PIP_PATH" install -r requirements.txt

    echo -e "\n${GREEN}[3/4] Installing PyTorch...${RESET}"
    if [ "$target_choice" == "1" ]; then
        if [ "$OS_TYPE" == "Darwin" ] && [ "$ARCH_TYPE" == "arm64" ]; then
            "$PIP_PATH" install torch==2.6.0 torchaudio==2.6.0 torchvision==0.21.0
        else
            "$PIP_PATH" install torch==2.6.0+cu124 torchaudio==2.6.0+cu124 torchvision==0.21.0+cu124 --extra-index-url https://download.pytorch.org/whl/cu124
        fi
    else
        "$PIP_PATH" install torch==2.6.0 torchaudio==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
    fi

    echo -e "\n${GREEN}[4/4] Pre-caching models and initializing database...${RESET}"
    HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 INSTALL_CHATTERBOX="$ENABLE_CHATTERBOX" "$PYTHON_PATH" -c "
import sys, os, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.getcwd())
import torch
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print('-> PyTorch Target Device:', device)
from faster_whisper import WhisperModel
WhisperModel('$WHISPER_SIZE', device='cpu', compute_type='int8', download_root=os.path.join(os.getcwd(), 'models_cache', 'whisper'))
from transformers import pipeline
pipeline('audio-classification', model='MIT/ast-finetuned-audioset-10-10-0.4593')
if os.getenv('INSTALL_CHATTERBOX') == '1':
    try:
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        ChatterboxMultilingualTTS.from_pretrained(device=device)
    except Exception as e:
        print(f'-> Chatterbox TTS note: {e}')
else:
    print('-> Skipping Chatterbox TTS download.')
from blueprints.database import init_db
init_db()
print('-> Database ready.')
"

    if command -v ollama >/dev/null 2>&1; then
        if ! pgrep -x "ollama" >/dev/null; then
            ollama serve >/dev/null 2>&1 &
            sleep 3
        fi
        echo -e "${CYAN}Pulling initial Ollama model ($EMB_MODEL)...${RESET}"
        ollama pull "$EMB_MODEL"
    fi

    echo -e "\n${GREEN}Setup completed successfully!${RESET}\n"
fi

echo -e "${CYAN}Starting GPU-Heater...${RESET}"

if ! pgrep -x "ollama" >/dev/null; then
    if command -v ollama >/dev/null 2>&1; then
        echo -e "${CYAN}Starting Ollama service...${RESET}"
        ollama serve >/dev/null 2>&1 &
        sleep 2
    fi
fi

mkdir -p user/logs
LOGFILE="user/logs/gpu_heater_$(date +'%Y%m%d_%H%M%S').log"

echo -e "${CYAN}Logs are being written to $LOGFILE${RESET}"
./venv/bin/python -u app.py 2>&1 | tee "$LOGFILE"