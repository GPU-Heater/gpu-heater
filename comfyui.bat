@echo off
setlocal enabledelayedexpansion
title ComfyUI Manager

for /f %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
set "RED=%ESC%[91m"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "CYAN=%ESC%[96m"
set "RESET=%ESC%[0m"

set "WORKSPACE=.\ComfyUI"
set "BASE_MODELS_DIR=%WORKSPACE%\models"
set "WORKFLOWS_DEST_DIR=%WORKSPACE%\user\default\workflows"
set "INPUT_DEST_DIR=%WORKSPACE%\input"

if not exist "comfy-env\Scripts\activate.bat" (
    goto :install_phase
) else (
    goto :main_menu
)

:install_phase
echo %CYAN%[Setup]%RESET% Installing requirements...
python -m venv comfy-env
call comfy-env\Scripts\activate.bat
pip install comfy-cli

echo %CYAN%[Setup]%RESET% Downloading ComfyUI (Please select your hardware)...
comfy --workspace "%WORKSPACE%" install

call :copy_files
echo %GREEN%[Setup] Completed! Launching ComfyUI...%RESET%
timeout /t 3 >nul
goto :main_menu

:main_menu
cls
call comfy-env\Scripts\activate.bat
echo %CYAN%========================================%RESET%
echo %CYAN%             COMFYUI MANAGER            %RESET%
echo %CYAN%========================================%RESET%
echo %GREEN%1)%RESET% Run
echo %YELLOW%2)%RESET% Configure (Add/Remove Models)
echo %RED%q)%RESET% Quit
echo %CYAN%========================================%RESET%
set /p main_choice="Enter your choice [1/2/q]: "

if "%main_choice%"=="1" goto :run_comfy
if "%main_choice%"=="2" goto :configure_menu
if /i "%main_choice%"=="q" exit
goto :main_menu

:run_comfy
cls
if not exist "user\logs" mkdir "user\logs"
for /f "usebackq tokens=*" %%I in (`powershell -NoProfile -Command "Get-Date -Format 'yyyyMMdd_HHmmss'"`) do set "DT=%%I"
set "COMFY_LOGFILE=user\logs\comfyui_%DT%.log"

echo %GREEN%Starting ComfyUI...%RESET% %YELLOW%(Press CTRL+C to stop and exit)%RESET%
echo %CYAN%Logs are being written to %COMFY_LOGFILE%%RESET%
powershell -NoProfile -Command "$PSNativeCommandUseErrorActionPreference = $false; comfy --workspace '%WORKSPACE%' launch 2>&1 | ForEach-Object { $_.ToString() } | Tee-Object -FilePath '%COMFY_LOGFILE%'"
exit

:configure_menu
cls
echo %CYAN%========================================%RESET%
echo %CYAN%               CONFIGURE                %RESET%
echo %CYAN%========================================%RESET%
echo %GREEN%1)%RESET% Add New Models
echo %RED%2)%RESET% Delete Existing Models
echo %CYAN%3)%RESET% Verify Workflow Files
echo %YELLOW%b)%RESET% Back to Main Menu
echo %CYAN%========================================%RESET%
set /p conf_choice="Enter your choice [1/2/b]: "

if "%conf_choice%"=="1" goto :download_menu
if "%conf_choice%"=="2" goto :delete_menu
if "%conf_choice%"=="3" (
    call :copy_files
    pause
    goto :configure_menu
)
if /i "%conf_choice%"=="b" goto :main_menu
goto :configure_menu

:download_menu
cls
echo %CYAN%=== Download Models ===%RESET%
echo %GREEN%1)%RESET% Video Models (34.9 GB)
echo %GREEN%2)%RESET% Image Models (34.4 GB)
echo %GREEN%3)%RESET% Outpaint Models (21.5 GB)
echo %GREEN%4)%RESET% Audio Models (9.7 GB)
echo %GREEN%5)%RESET% Music Model (9.3 GB)
echo %GREEN%6)%RESET% 3D Model (6.9 GB)
echo %CYAN%0)%RESET% All Models (116.7 GB)
echo %YELLOW%b)%RESET% Back
set /p dl_choice="Enter your choice: "

if "%dl_choice%"=="1" call :dl_video
if "%dl_choice%"=="2" call :dl_image
if "%dl_choice%"=="3" call :dl_outpaint
if "%dl_choice%"=="4" call :dl_audio
if "%dl_choice%"=="5" call :dl_music
if "%dl_choice%"=="6" call :dl_3d
if "%dl_choice%"=="0" (
    call :dl_video
    call :dl_image
    call :dl_outpaint
    call :dl_audio
    call :dl_music
    call :dl_3d
)
if /i "%dl_choice%"=="b" goto :configure_menu

echo %GREEN%Download operation completed.%RESET%
pause
goto :download_menu

:delete_menu
cls
echo %RED%=== Delete Models ===%RESET%
echo %RED%1)%RESET% Delete Video Models
echo %RED%2)%RESET% Delete Image Models
echo %RED%3)%RESET% Delete Outpaint Models
echo %RED%4)%RESET% Delete Audio Models
echo %RED%5)%RESET% Delete Music Model
echo %RED%6)%RESET% Delete 3D Model
echo %RED%0)%RESET% Delete All Models
echo %YELLOW%b)%RESET% Back
set /p del_choice="Enter your choice: "

if "%del_choice%"=="1" (
    del /q "%BASE_MODELS_DIR%\text_encoders\gemma_3_12B_it_fp4_mixed.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\latent_upscale_models\ltx-2-spatial-upscaler-x2-1.0.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\checkpoints\ltx-2-19b-distilled-fp8.safetensors" 2>nul
    echo %RED%Video models deleted.%RESET%
)
if "%del_choice%"=="2" (
    del /q "%BASE_MODELS_DIR%\controlnet\Qwen-Image-2512-Fun-Controlnet-Union-2602.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\loras\Qwen-Image-Lightning-4steps-V1.0.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\vae\qwen_image_vae.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\text_encoders\qwen_2.5_vl_7b_fp8_scaled.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\diffusion_models\qwen_image_2512_fp8_e4m3fn.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\loras\Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors" 2>nul
    echo %RED%Image models deleted.%RESET%
)
if "%del_choice%"=="3" (
    del /q "%BASE_MODELS_DIR%\vae\ae.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\diffusion_models\flux.1-fill-dev-OneReward-transformer_fp8.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\text_encoders\clip_l.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\text_encoders\t5xxl_fp16.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\loras\removal_timestep_alpha-2-1740.safetensors" 2>nul
    echo %RED%Outpaint models deleted.%RESET%
)
if "%del_choice%"=="4" (
    del /q "%BASE_MODELS_DIR%\text_encoders\t5gemma_b_b_ul2.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\checkpoints\stable_audio_3_medium.safetensors" 2>nul
    echo %RED%Audio models deleted.%RESET%
)
if "%del_choice%"=="5" (
    del /q "%BASE_MODELS_DIR%\checkpoints\ace_step_1.5_turbo_aio.safetensors" 2>nul
    echo %RED%Music model deleted.%RESET%
)
if "%del_choice%"=="6" (
    del /q "%BASE_MODELS_DIR%\checkpoints\hunyuan_3d_v2.1.safetensors" 2>nul
    echo %RED%3D model deleted.%RESET%
)
if "%del_choice%"=="0" (
    del /q "%BASE_MODELS_DIR%\text_encoders\gemma_3_12B_it_fp4_mixed.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\latent_upscale_models\ltx-2-spatial-upscaler-x2-1.0.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\checkpoints\ltx-2-19b-distilled-fp8.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\controlnet\Qwen-Image-2512-Fun-Controlnet-Union-2602.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\loras\Qwen-Image-Lightning-4steps-V1.0.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\vae\qwen_image_vae.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\text_encoders\qwen_2.5_vl_7b_fp8_scaled.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\diffusion_models\qwen_image_2512_fp8_e4m3fn.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\loras\Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\vae\ae.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\diffusion_models\flux.1-fill-dev-OneReward-transformer_fp8.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\text_encoders\clip_l.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\text_encoders\t5xxl_fp16.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\loras\removal_timestep_alpha-2-1740.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\text_encoders\t5gemma_b_b_ul2.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\checkpoints\stable_audio_3_medium.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\checkpoints\ace_step_1.5_turbo_aio.safetensors" 2>nul
    del /q "%BASE_MODELS_DIR%\checkpoints\hunyuan_3d_v2.1.safetensors" 2>nul
    echo %RED%All models deleted.%RESET%
)
if /i "%del_choice%"=="b" goto :configure_menu
pause
goto :delete_menu

:copy_files
echo %CYAN%^>^> Copying asset files...%RESET%
if not exist "%WORKFLOWS_DEST_DIR%" mkdir "%WORKFLOWS_DEST_DIR%"
if not exist "%INPUT_DEST_DIR%" mkdir "%INPUT_DEST_DIR%"

set "workflow_files=3d_hunyuan3d-v2.1.json audio_ace_step_1_5_checkpoint.json audio_stable_audio_3_medium.json image_flux.1_fill_dev_OneReward.json image_qwen_Image_2512.json image_qwen_Image_2512_controlnet.json video_ltx2_i2v_distilled.json video_ltx2_t2v_distilled.json"

for %%F in (%workflow_files%) do (
    if exist "workflows-raw\%%F" (
        copy "workflows-raw\%%F" "%WORKFLOWS_DEST_DIR%\" >nul
        echo %GREEN%Copied %%F -^> %WORKFLOWS_DEST_DIR%\%RESET%
    )
)
if exist "workflows-raw\gpu-heater.png" (
    copy "workflows-raw\gpu-heater.png" "%INPUT_DEST_DIR%\" >nul
    echo %GREEN%Copied gpu-heater.png -^> %INPUT_DEST_DIR%\%RESET%
)
goto :eof

:download
set "URL=%~1"
set "FOLDER=%~2"
set "FILENAME=%~3"
set "DEST=%BASE_MODELS_DIR%\%FOLDER%"
if not exist "%DEST%" mkdir "%DEST%"
echo %CYAN%^>^> Downloading: %FILENAME% -^> %DEST%%RESET%
curl -L -C - -o "%DEST%\%FILENAME%" "%URL%"
goto :eof

:dl_3d
echo %CYAN%=== Downloading 3D Models (6.9 GB) ===%RESET%
call :download "https://huggingface.co/Comfy-Org/hunyuan3D_2.1_repackaged/resolve/main/hunyuan_3d_v2.1.safetensors" "checkpoints" "hunyuan_3d_v2.1.safetensors"
goto :eof

:dl_music
echo %CYAN%=== Downloading Music Models (9.3 GB) ===%RESET%
call :download "https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/checkpoints/ace_step_1.5_turbo_aio.safetensors" "checkpoints" "ace_step_1.5_turbo_aio.safetensors"
goto :eof

:dl_audio
echo %CYAN%=== Downloading Audio Models (9.7 GB) ===%RESET%
call :download "https://huggingface.co/Comfy-Org/stable-audio-3/resolve/main/text_encoders/t5gemma_b_b_ul2.safetensors" "text_encoders" "t5gemma_b_b_ul2.safetensors"
call :download "https://huggingface.co/Comfy-Org/stable-audio-3/resolve/main/checkpoints/stable_audio_3_medium.safetensors" "checkpoints" "stable_audio_3_medium.safetensors"
goto :eof

:dl_image
echo %CYAN%=== Downloading Image Models (34.4 GB) ===%RESET%
call :download "https://huggingface.co/alibaba-pai/Qwen-Image-2512-Fun-Controlnet-Union/resolve/main/Qwen-Image-2512-Fun-Controlnet-Union-2602.safetensors" "controlnet" "Qwen-Image-2512-Fun-Controlnet-Union-2602.safetensors"
call :download "https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-4steps-V1.0.safetensors" "loras" "Qwen-Image-Lightning-4steps-V1.0.safetensors"
call :download "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors" "vae" "qwen_image_vae.safetensors"
call :download "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" "text_encoders" "qwen_2.5_vl_7b_fp8_scaled.safetensors"
call :download "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors" "diffusion_models" "qwen_image_2512_fp8_e4m3fn.safetensors"
call :download "https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors" "loras" "Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors"
goto :eof

:dl_outpaint
echo %CYAN%=== Downloading Outpaint Models (21.5 GB) ===%RESET%
call :download "https://huggingface.co/Comfy-Org/Lumina_Image_2.0_Repackaged/resolve/main/split_files/vae/ae.safetensors" "vae" "ae.safetensors"
call :download "https://huggingface.co/Comfy-Org/OneReward_repackaged/resolve/main/split_files/diffusion_models/flux.1-fill-dev-OneReward-transformer_fp8.safetensors" "diffusion_models" "flux.1-fill-dev-OneReward-transformer_fp8.safetensors"
call :download "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" "text_encoders" "clip_l.safetensors"
call :download "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors" "text_encoders" "t5xxl_fp16.safetensors"
call :download "https://huggingface.co/lrzjason/ObjectRemovalFluxFill/resolve/main/removal_timestep_alpha-2-1740.safetensors" "loras" "removal_timestep_alpha-2-1740.safetensors"
goto :eof

:dl_video
echo %CYAN%=== Downloading Video Models (34.9 GB) ===%RESET%
call :download "https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors" "text_encoders" "gemma_3_12B_it_fp4_mixed.safetensors"
call :download "https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-spatial-upscaler-x2-1.0.safetensors" "latent_upscale_models" "ltx-2-spatial-upscaler-x2-1.0.safetensors"
call :download "https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-distilled-fp8.safetensors" "checkpoints" "ltx-2-19b-distilled-fp8.safetensors"
goto :eof