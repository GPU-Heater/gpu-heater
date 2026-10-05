@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

set "PROJECT_DIR=%~dp0"
set "HF_HOME=%PROJECT_DIR%models_cache\huggingface"
set "TRANSFORMERS_CACHE=%PROJECT_DIR%models_cache\huggingface"
set "TORCH_HOME=%PROJECT_DIR%models_cache\torch"
set "XDG_CACHE_HOME=%PROJECT_DIR%models_cache"

set "HF_HUB_OFFLINE=1"
set "TRANSFORMERS_OFFLINE=1"

if not exist "models_cache\huggingface" mkdir "models_cache\huggingface"
if not exist "models_cache\torch" mkdir "models_cache\torch"

for /f %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
set "RED=%ESC%[91m"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "CYAN=%ESC%[96m"
set "RESET=%ESC%[0m"

if exist ".\venv\Scripts\python.exe" (
    for /f "tokens=2" %%V in ('.\venv\Scripts\python.exe --version 2^>^&1') do (
        echo %%V | findstr /R "^3\.10\. ^3\.11\. ^3\.12\." >NUL
        if not errorlevel 1 (
            goto :RunApp
        )
    )
    echo %YELLOW%Existing venv uses an unsupported Python version. Removing venv...%RESET%
    rd /s /q "venv"
)

echo %CYAN%=========================================%RESET%
echo %CYAN%           GPU-Heater Setup              %RESET%
echo %CYAN%=========================================%RESET%

set "PYTHON_CMD="
for %%C in (python3.11 python3.12 python3.10 python py) do (
    where %%C >NUL 2>&1
    if not errorlevel 1 (
        for /f "tokens=2" %%V in ('%%C --version 2^>^&1') do (
            echo %%V | findstr /R "^3\.10\. ^3\.11\. ^3\.12\." >NUL
            if not errorlevel 1 (
                set "PYTHON_CMD=%%C"
                goto :PythonFound
            )
        )
    )
)

:PythonFound
if not defined PYTHON_CMD (
    echo.
    echo %YELLOW%[Prerequisite] Python 3.10-3.12 was not detected.%RESET%
    set /p "INSTALL_PY=Download and install Python 3.11? (Y/N): "
    if /i "!INSTALL_PY!"=="Y" (
        echo %GREEN%Downloading Python 3.11...%RESET%
        curl -L -o "%TEMP%\python-3.11.9-amd64.exe" https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
        echo %YELLOW%Installing Python 3.11...%RESET%
        start /wait "" "%TEMP%\python-3.11.9-amd64.exe" /quiet InstallAllUsers=0 PrependPath=1
        del "%TEMP%\python-3.11.9-amd64.exe"
        set "PYTHON_CMD=python"
    ) else (
        echo %RED%Please install Python 3.10, 3.11, or 3.12 manually.%RESET%
        pause
        exit /b 1
    )
)

echo.
echo %YELLOW%[Prerequisite] Checking Git...%RESET%
where git >NUL 2>&1
if errorlevel 1 (
    echo %RED%-> Git is missing.%RESET%
    set /p "INSTALL_GIT=Download and install Git? (Y/N): "
    if /i "!INSTALL_GIT!"=="Y" (
        echo %GREEN%Downloading Git...%RESET%
        curl -L -o "%TEMP%\GitSetup.exe" https://github.com/git-for-windows/git/releases/download/v2.45.0.windows.1/Git-2.45.0-64-bit.exe
        start /wait "" "%TEMP%\GitSetup.exe" /VERYSILENT /NORESTART
        del "%TEMP%\GitSetup.exe"
    )
) else (
    echo %GREEN%-> Git is installed.%RESET%
)

echo.
echo %YELLOW%[Prerequisite] Checking Ollama...%RESET%
where ollama >NUL 2>&1
if errorlevel 1 (
    echo %RED%-> Ollama is missing.%RESET%
    set /p "INSTALL_OLLAMA=Download and install Ollama? (Y/N): "
    if /i "!INSTALL_OLLAMA!"=="Y" (
        echo %GREEN%Downloading Ollama...%RESET%
        curl -L -o "%TEMP%\OllamaSetup.exe" https://ollama.com/download/OllamaSetup.exe
        start /wait "" "%TEMP%\OllamaSetup.exe"
        del "%TEMP%\OllamaSetup.exe"
    )
) else (
    echo %GREEN%-> Ollama is installed.%RESET%
)

echo.
echo %YELLOW%Please select the PyTorch hardware target:%RESET%
echo %YELLOW%1) NVIDIA GPU (CUDA 12.4 - Recommended)%RESET%
echo %YELLOW%2) CPU%RESET%
set /p "TARGET_CHOICE=Enter choice (1 or 2): "

echo.
echo %YELLOW%[Optional] Chatterbox TTS (Text-to-Speech) Model (~1-2 GB)%RESET%
echo %YELLOW%Note: This model is used for generating spoken audio responses.%RESET%
echo %YELLOW%If you skip this, text chat and voice recognition (STT) will work fine,%RESET%
echo %YELLOW%but you will not be able to listen to voice responses.%RESET%
set /p "INSTALL_TTS=Do you want to download Chatterbox TTS model? (Y/N, Default: N): "
set "ENABLE_CHATTERBOX=0"
if /i "!INSTALL_TTS!"=="Y" set "ENABLE_CHATTERBOX=1"

echo.
echo %YELLOW%Please select Whisper (STT) model size:%RESET%
echo %YELLOW%1) Small (Fast / Low VRAM)%RESET%
echo %YELLOW%2) Medium (Balanced - Default)%RESET%
echo %YELLOW%3) Large (High Accuracy / High VRAM)%RESET%
set /p "STT_CHOICE=Enter choice (1, 2, or 3): "

set "WHISPER_SIZE=medium"
if "!STT_CHOICE!"=="1" set "WHISPER_SIZE=small"
if "!STT_CHOICE!"=="3" set "WHISPER_SIZE=large-v3"
echo !WHISPER_SIZE!> "%PROJECT_DIR%whisper_model.txt"

echo.
echo %YELLOW%Please select Embedding model (Knowledge Base):%RESET%
echo %YELLOW%1) Nomic Embed Text  (~274 MB - Fast, English, Code focused)%RESET%
echo %YELLOW%2) BGE-M3            (~1.2 GB - High Accuracy, Best Multilingual)%RESET%
echo %YELLOW%3) MXBAI Embed Large (~670 MB - High Accuracy, English Semantic Search)%RESET%
echo %YELLOW%4) All-MiniLM        (~120 MB - Ultra Lightweight, Basic Matching)%RESET%
set /p "EMB_CHOICE=Enter choice (1, 2, 3, or 4): "

set "EMB_MODEL=nomic-embed-text"
if "!EMB_CHOICE!"=="2" set "EMB_MODEL=bge-m3"
if "!EMB_CHOICE!"=="3" set "EMB_MODEL=mxbai-embed-large"
if "!EMB_CHOICE!"=="4" set "EMB_MODEL=all-minilm"
echo !EMB_MODEL!> "%PROJECT_DIR%embedding_model.txt"

echo.
echo %GREEN%[1/4] Creating virtual environment...%RESET%
!PYTHON_CMD! -m venv venv

set "PIP_PATH=.\venv\Scripts\pip.exe"
set "PYTHON_PATH=.\venv\Scripts\python.exe"

!PIP_PATH! install --upgrade pip

echo.
echo %GREEN%[2/4] Installing requirements...%RESET%
!PIP_PATH! install -r requirements.txt

echo.
echo %GREEN%[3/4] Installing PyTorch...%RESET%
if "!TARGET_CHOICE!"=="1" (
    !PIP_PATH! install torch==2.6.0+cu124 torchaudio==2.6.0+cu124 torchvision==0.21.0+cu124 --extra-index-url https://download.pytorch.org/whl/cu124
) else (
    !PIP_PATH! install torch==2.6.0 torchaudio==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
)

echo.
echo %GREEN%[4/4] Pre-caching models and initializing database...%RESET%
set "HF_HUB_OFFLINE="
set "TRANSFORMERS_OFFLINE="
!PYTHON_PATH! -c "import sys, os, warnings; warnings.filterwarnings('ignore'); sys.path.insert(0, os.getcwd()); import torch; device = 'cuda' if torch.cuda.is_available() else 'cpu'; print('-> PyTorch Target Device:', device); from faster_whisper import WhisperModel; WhisperModel('!WHISPER_SIZE!', device='cpu', compute_type='int8', download_root=os.path.join(os.getcwd(), 'models_cache', 'whisper')); from transformers import pipeline; pipeline('audio-classification', model='MIT/ast-finetuned-audioset-10-10-0.4593'); exec('if os.getenv(\x27INSTALL_CHATTERBOX\x27) == \x271\x27:\n try:\n  from chatterbox.mtl_tts import ChatterboxMultilingualTTS\n  ChatterboxMultilingualTTS.from_pretrained(device=device)\n except Exception as e:\n  print(f\x27-> Chatterbox TTS note: {e}\x27)\nelse:\n print(\x27-> Skipping Chatterbox TTS download.\x27)'); from blueprints.database import init_db; init_db(); print('-> Database ready.')"
set "HF_HUB_OFFLINE=1"
set "TRANSFORMERS_OFFLINE=1"

echo.
echo %CYAN%Initial pull for Ollama model...%RESET%
ollama pull !EMB_MODEL!

echo.
echo %GREEN%Setup completed successfully!%RESET%
echo.

:RunApp
echo %CYAN%Starting GPU-Heater...%RESET%

tasklist /fi "imagename eq ollama.exe" 2>NUL | find /i "ollama.exe" >NUL
if errorlevel 1 (
    where ollama >NUL 2>&1
    if not errorlevel 1 (
        echo %CYAN%Starting Ollama service...%RESET%
        start /b "" ollama serve >NUL 2>&1
        timeout /t 3 /nobreak >NUL
    )
)

if not exist "user\logs" mkdir "user\logs"
for /f "usebackq tokens=*" %%I in (`powershell -NoProfile -Command "Get-Date -Format 'yyyyMMdd_HHmmss'"`) do set "DT=%%I"
set "LOGFILE=user\logs\gpu_heater_%DT%.log"

echo %CYAN%Logs are being written to %LOGFILE%%RESET%
powershell -NoProfile -Command "$PSNativeCommandUseErrorActionPreference = $false; .\venv\Scripts\python.exe -u app.py 2>&1 | ForEach-Object { $_.ToString() } | Tee-Object -FilePath '%LOGFILE%'"
pause