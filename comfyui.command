#!/usr/bin/env bash

echo -ne "\033]0;ComfyUI Manager\007"

RED='\033[0;91m'
GREEN='\033[0;92m'
YELLOW='\033[0;93m'
CYAN='\033[0;96m'
RESET='\033[0m'

cd "$(dirname "$0")"
export PROJECT_DIR="$(pwd)"
WORKSPACE="$PROJECT_DIR/ComfyUI"
BASE_MODELS_DIR="$WORKSPACE/models"
WORKFLOWS_DEST_DIR="$WORKSPACE/user/default/workflows"
INPUT_DEST_DIR="$WORKSPACE/input"

download() {
    local URL="$1"
    local FOLDER="$2"
    local FILENAME="$3"
    local DEST="$BASE_MODELS_DIR/$FOLDER"
    
    mkdir -p "$DEST"
    echo -e "${CYAN}>> Downloading: $FILENAME -> $DEST${RESET}"
    curl -L -C - -o "$DEST/$FILENAME" "$URL"
}

dl_3d() {
    echo -e "${CYAN}=== Downloading 3D Models (6.9 GB) ===${RESET}"
    download "https://huggingface.co/Comfy-Org/hunyuan3D_2.1_repackaged/resolve/main/hunyuan_3d_v2.1.safetensors" "checkpoints" "hunyuan_3d_v2.1.safetensors"
}

dl_music() {
    echo -e "${CYAN}=== Downloading Music Models (9.3 GB) ===${RESET}"
    download "https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/checkpoints/ace_step_1.5_turbo_aio.safetensors" "checkpoints" "ace_step_1.5_turbo_aio.safetensors"
}

dl_audio() {
    echo -e "${CYAN}=== Downloading Audio Models (9.7 GB) ===${RESET}"
    download "https://huggingface.co/Comfy-Org/stable-audio-3/resolve/main/text_encoders/t5gemma_b_b_ul2.safetensors" "text_encoders" "t5gemma_b_b_ul2.safetensors"
    download "https://huggingface.co/Comfy-Org/stable-audio-3/resolve/main/checkpoints/stable_audio_3_medium.safetensors" "checkpoints" "stable_audio_3_medium.safetensors"
}

dl_image() {
    echo -e "${CYAN}=== Downloading Image Models (34.4 GB) ===${RESET}"
    download "https://huggingface.co/alibaba-pai/Qwen-Image-2512-Fun-Controlnet-Union/resolve/main/Qwen-Image-2512-Fun-Controlnet-Union-2602.safetensors" "controlnet" "Qwen-Image-2512-Fun-Controlnet-Union-2602.safetensors"
    download "https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-4steps-V1.0.safetensors" "loras" "Qwen-Image-Lightning-4steps-V1.0.safetensors"
    download "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors" "vae" "qwen_image_vae.safetensors"
    download "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" "text_encoders" "qwen_2.5_vl_7b_fp8_scaled.safetensors"
    download "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors" "diffusion_models" "qwen_image_2512_fp8_e4m3fn.safetensors"
    download "https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors" "loras" "Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors"
}

dl_outpaint() {
    echo -e "${CYAN}=== Downloading Outpaint Models (21.5 GB) ===${RESET}"
    download "https://huggingface.co/Comfy-Org/Lumina_Image_2.0_Repackaged/resolve/main/split_files/vae/ae.safetensors" "vae" "ae.safetensors"
    download "https://huggingface.co/Comfy-Org/OneReward_repackaged/resolve/main/split_files/diffusion_models/flux.1-fill-dev-OneReward-transformer_fp8.safetensors" "diffusion_models" "flux.1-fill-dev-OneReward-transformer_fp8.safetensors"
    download "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" "text_encoders" "clip_l.safetensors"
    download "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors" "text_encoders" "t5xxl_fp16.safetensors"
    download "https://huggingface.co/lrzjason/ObjectRemovalFluxFill/resolve/main/removal_timestep_alpha-2-1740.safetensors" "loras" "removal_timestep_alpha-2-1740.safetensors"
}

dl_video() {
    echo -e "${CYAN}=== Downloading Video Models (34.9 GB) ===${RESET}"
    download "https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors" "text_encoders" "gemma_3_12B_it_fp4_mixed.safetensors"
    download "https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-spatial-upscaler-x2-1.0.safetensors" "latent_upscale_models" "ltx-2-spatial-upscaler-x2-1.0.safetensors"
    download "https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-distilled-fp8.safetensors" "checkpoints" "ltx-2-19b-distilled-fp8.safetensors"
}

copy_files() {
    echo -e "${CYAN}>> Copying asset files...${RESET}"
    mkdir -p "$WORKFLOWS_DEST_DIR"
    mkdir -p "$INPUT_DEST_DIR"

    if [ -d "./workflows-raw" ]; then
        local workflow_files=(
            "3d_hunyuan3d-v2.1.json" 
            "audio_ace_step_1_5_checkpoint.json" 
            "audio_stable_audio_3_medium.json" 
            "image_flux.1_fill_dev_OneReward.json" 
            "image_qwen_Image_2512.json" 
            "image_qwen_Image_2512_controlnet.json" 
            "video_ltx2_i2v_distilled.json" 
            "video_ltx2_t2v_distilled.json"
        )

        for f in "${workflow_files[@]}"; do
            if [ -f "./workflows-raw/$f" ]; then
                cp "./workflows-raw/$f" "$WORKFLOWS_DEST_DIR/" 2>/dev/null
                echo -e "${GREEN}Copied $f -> $WORKFLOWS_DEST_DIR/${RESET}"
            fi
        done
        
        if [ -f "./workflows-raw/gpu-heater.png" ]; then
            cp "./workflows-raw/gpu-heater.png" "$INPUT_DEST_DIR/" 2>/dev/null
            echo -e "${GREEN}Copied gpu-heater.png -> $INPUT_DEST_DIR/${RESET}"
        fi
    fi
}

delete_menu() {
    while true; do
        clear
        echo -e "${RED}=== Delete Models ===${RESET}"
        echo -e "${RED}1)${RESET} Delete Video Models"
        echo -e "${RED}2)${RESET} Delete Image Models"
        echo -e "${RED}3)${RESET} Delete Outpaint Models"
        echo -e "${RED}4)${RESET} Delete Audio Models"
        echo -e "${RED}5)${RESET} Delete Music Model"
        echo -e "${RED}6)${RESET} Delete 3D Model"
        echo -e "${RED}0)${RESET} Delete All Models"
        echo -e "${YELLOW}b)${RESET} Back"
        
        read -r -p "Enter your choice: " del_choice

        case "$del_choice" in
            1)
                rm -f "$BASE_MODELS_DIR/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/latent_upscale_models/ltx-2-spatial-upscaler-x2-1.0.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/checkpoints/ltx-2-19b-distilled-fp8.safetensors" 2>/dev/null
                echo -e "${RED}Video models deleted.${RESET}"
                ;;
            2)
                rm -f "$BASE_MODELS_DIR/controlnet/Qwen-Image-2512-Fun-Controlnet-Union-2602.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/loras/Qwen-Image-Lightning-4steps-V1.0.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/vae/qwen_image_vae.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/loras/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors" 2>/dev/null
                echo -e "${RED}Image models deleted.${RESET}"
                ;;
            3)
                rm -f "$BASE_MODELS_DIR/vae/ae.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/diffusion_models/flux.1-fill-dev-OneReward-transformer_fp8.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/text_encoders/clip_l.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/text_encoders/t5xxl_fp16.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/loras/removal_timestep_alpha-2-1740.safetensors" 2>/dev/null
                echo -e "${RED}Outpaint models deleted.${RESET}"
                ;;
            4)
                rm -f "$BASE_MODELS_DIR/text_encoders/t5gemma_b_b_ul2.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/checkpoints/stable_audio_3_medium.safetensors" 2>/dev/null
                echo -e "${RED}Audio models deleted.${RESET}"
                ;;
            5)
                rm -f "$BASE_MODELS_DIR/checkpoints/ace_step_1.5_turbo_aio.safetensors" 2>/dev/null
                echo -e "${RED}Music model deleted.${RESET}"
                ;;
            6)
                rm -f "$BASE_MODELS_DIR/checkpoints/hunyuan_3d_v2.1.safetensors" 2>/dev/null
                echo -e "${RED}3D model deleted.${RESET}"
                ;;
            0)
                rm -f "$BASE_MODELS_DIR/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/latent_upscale_models/ltx-2-spatial-upscaler-x2-1.0.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/checkpoints/ltx-2-19b-distilled-fp8.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/controlnet/Qwen-Image-2512-Fun-Controlnet-Union-2602.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/loras/Qwen-Image-Lightning-4steps-V1.0.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/vae/qwen_image_vae.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/loras/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/vae/ae.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/diffusion_models/flux.1-fill-dev-OneReward-transformer_fp8.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/text_encoders/clip_l.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/text_encoders/t5xxl_fp16.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/loras/removal_timestep_alpha-2-1740.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/text_encoders/t5gemma_b_b_ul2.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/checkpoints/stable_audio_3_medium.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/checkpoints/ace_step_1.5_turbo_aio.safetensors" 2>/dev/null
                rm -f "$BASE_MODELS_DIR/checkpoints/hunyuan_3d_v2.1.safetensors" 2>/dev/null
                echo -e "${RED}All models deleted.${RESET}"
                ;;
            b|B)
                return
                ;;
        esac
        read -n 1 -s -r -p "Press any key to continue..."
    done
}

download_menu() {
    while true; do
        clear
        echo -e "${CYAN}=== Download Models ===${RESET}"
        echo -e "${GREEN}1)${RESET} Video Models (34.9 GB)"
        echo -e "${GREEN}2)${RESET} Image Models (34.4 GB)"
        echo -e "${GREEN}3)${RESET} Outpaint Models (21.5 GB)"
        echo -e "${GREEN}4)${RESET} Audio Models (9.7 GB)"
        echo -e "${GREEN}5)${RESET} Music Model (9.3 GB)"
        echo -e "${GREEN}6)${RESET} 3D Model (6.9 GB)"
        echo -e "${CYAN}0)${RESET} All Models (116.6 GB)"
        echo -e "${YELLOW}b)${RESET} Back"
        
        read -r -p "Enter your choice: " dl_choice

        case "$dl_choice" in
            1) dl_video ;;
            2) dl_image ;;
            3) dl_outpaint ;;
            4) dl_audio ;;
            5) dl_music ;;
            6) dl_3d ;;
            0)
                dl_video; dl_image; dl_outpaint
                dl_audio; dl_music; dl_3d
                ;;
            b|B) return ;;
        esac
        echo -e "${GREEN}Download operation completed.${RESET}"
        read -n 1 -s -r -p "Press any key to continue..."
    done
}

configure_menu() {
    while true; do
        clear
        echo -e "${CYAN}========================================${RESET}"
        echo -e "${CYAN}               CONFIGURE                ${RESET}"
        echo -e "${CYAN}========================================${RESET}"
        echo -e "${GREEN}1)${RESET} Add New Models"
        echo -e "${RED}2)${RESET} Delete Existing Models"
        echo -e "${CYAN}3)${RESET} Verify Workflow Files"
        echo -e "${YELLOW}b)${RESET} Back to Main Menu"
        echo -e "${CYAN}========================================${RESET}"
        
        read -r -p "Enter your choice [1/2/b]: " conf_choice

        case "$conf_choice" in
            1) download_menu ;;
            2) delete_menu ;;
            3) 
               copy_files
               read -n 1 -s -r -p "Press any key to continue..."
               ;;
            b|B) return ;;
        esac
    done
}

run_comfy() {
    clear
    mkdir -p user/logs
    COMFY_LOGFILE="user/logs/comfyui_$(date +'%Y%m%d_%H%M%S').log"
    echo -e "${GREEN}Starting ComfyUI...${RESET} ${YELLOW}(Press CTRL+C to stop and exit)${RESET}"
    echo -e "${CYAN}Logs are being written to $COMFY_LOGFILE${RESET}"
    comfy --workspace "$WORKSPACE" launch 2>&1 | tee "$COMFY_LOGFILE"
    exit 0
}

main_menu() {
    while true; do
        clear
        source comfy-env/bin/activate 2>/dev/null
        echo -e "${CYAN}========================================${RESET}"
        echo -e "${CYAN}             COMFYUI MANAGER            ${RESET}"
        echo -e "${CYAN}========================================${RESET}"
        echo -e "${GREEN}1)${RESET} Run"
        echo -e "${YELLOW}2)${RESET} Configure (Add/Remove Models)"
        echo -e "${RED}q)${RESET} Quit"
        echo -e "${CYAN}========================================${RESET}"
        
        read -r -p "Enter your choice [1/2/q]: " main_choice

        case "$main_choice" in
            1) run_comfy ;;
            2) configure_menu ;;
            q|Q) exit 0 ;;
        esac
    done
}

install_phase() {
    echo -e "${CYAN}[Setup]${RESET} Installing requirements..."
    python3 -m venv comfy-env
    source comfy-env/bin/activate
    pip install comfy-cli

    echo -e "${CYAN}[Setup]${RESET} Downloading ComfyUI (Please select your hardware)..."
    comfy --workspace "$WORKSPACE" install

    copy_files
    echo -e "${GREEN}[Setup] Completed! Launching ComfyUI...${RESET}"
    sleep 3
}

if [ ! -f "comfy-env/bin/activate" ]; then
    install_phase
fi
main_menu