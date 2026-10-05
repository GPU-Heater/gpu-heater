let pullAbortController = null;
let lastPullBytes = 0;
let lastPullTime = 0;
let currentSpeedText = "";
let isPullPaused = false;

async function fetchSettings() {
    const res = await fetch('/api/settings');
    const data = await res.json();
    document.getElementById('sysPromptInput').value = data.system_prompt || '';
    document.getElementById('personalContextInput').value = data.personal_context || '';
    document.getElementById('timeoutToggleInput').checked = data.timeout_enabled === 'true';
    document.getElementById('timeoutSecInput').value = data.timeout_sec || 300;
    document.getElementById('timeoutSecInput').disabled = data.timeout_enabled !== 'true';
    
    document.getElementById('unloadTimeoutInput').value = data.model_unload_timeout || 300;
    
    const modelRes = await fetch('/api/models/list');
    const modelData = await modelRes.json();
    if(modelData.success) {
        ollamaModels = modelData.models; 
        
        const selects = ['titleModelSelect', 'defaultModelSelect', 'reasoningModelSelect', 'coderModelSelect', 'coderReasoningModelSelect'];
        selects.forEach(selId => {
            const sel = document.getElementById(selId);
            sel.innerHTML = '';
            ollamaModels.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.name; opt.textContent = m.name;
                sel.appendChild(opt);
            });
        });
        
        if (data.title_model) document.getElementById('titleModelSelect').value = data.title_model;
        if (data.default_model) document.getElementById('defaultModelSelect').value = data.default_model;
        if (data.reasoning_model) document.getElementById('reasoningModelSelect').value = data.reasoning_model;
        if (data.coder_model) document.getElementById('coderModelSelect').value = data.coder_model;
        if (data.coder_reasoning_model) document.getElementById('coderReasoningModelSelect').value = data.coder_reasoning_model;

        const listEl = document.getElementById('installedModelsList');
        if (listEl) {
            listEl.innerHTML = '';
            if(ollamaModels.length === 0) {
                listEl.innerHTML = '<div style="font-size:12px; color:var(--text-muted); text-align:center; padding:10px;">No installed models found.</div>';
            }
            ollamaModels.forEach(m => {
                listEl.innerHTML += `
                    <div style="display:flex; justify-content:space-between; align-items:center; background:var(--bg-panel); padding:8px 12px; border-radius:6px; border:1px solid var(--border);">
                        <div style="display:flex; flex-direction:column; gap:2px;">
                            <span style="font-size:13px; font-weight:600; color:var(--text-main);">${m.name}</span>
                            <span style="font-size:11px; color:var(--text-muted);"><i class="fas fa-hdd"></i> ${m.size_gb} GB</span>
                        </div>
                        <button onclick="deleteOllamaModel('${m.name}')" style="background:var(--bg-hover); border:none; color:var(--danger); cursor:pointer; width:30px; height:30px; border-radius:4px; transition:0.2s;" title="Delete Model">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </div>
                `;
            });
        }
    }
    
    await loadAvailableVoices(data.tts_voice);
}

async function loadAvailableVoices(selectedVoice) {
    const res = await fetch('/api/voices');
    const voices = await res.json();
    const select = document.getElementById('ttsVoiceInput');
    select.innerHTML = `<option value="">${t('select_voice')}</option>`;
    voices.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v;
        select.appendChild(opt);
    });
    if (selectedVoice && voices.includes(selectedVoice)) select.value = selectedVoice;
}

async function uploadVoiceFile(input) {
    const file = input.files[0];
    if(!file) return;
    const formData = new FormData();
    formData.append('voice_file', file);
    const res = await fetch('/api/voices', { method: 'POST', body: formData });
    const data = await res.json();
    if(data.success) {
        alert(t('voice_uploaded'));
        await loadAvailableVoices(data.filename);
    }
    input.value = '';
}

function openSettings() { fetchSettings(); document.getElementById('settingsModal').style.display = 'flex'; }
function closeSettings() { document.getElementById('settingsModal').style.display = 'none'; }

async function saveSettings() {
    const sys = document.getElementById('sysPromptInput').value;
    const ctx = document.getElementById('personalContextInput').value;
    const voice = document.getElementById('ttsVoiceInput').value;
    const t_en = document.getElementById('timeoutToggleInput').checked ? 'true' : 'false';
    const t_sec = document.getElementById('timeoutSecInput').value;

    const reqBody = { 
        system_prompt: sys, 
        personal_context: ctx, 
        tts_voice: voice,
        timeout_enabled: t_en,
        timeout_sec: t_sec,
        title_model: document.getElementById('titleModelSelect').value,
        default_model: document.getElementById('defaultModelSelect').value,
        reasoning_model: document.getElementById('reasoningModelSelect').value,
        coder_model: document.getElementById('coderModelSelect').value,
        coder_reasoning_model: document.getElementById('coderReasoningModelSelect').value,
        model_unload_timeout: document.getElementById('unloadTimeoutInput').value || "300"
    };

    await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(reqBody)
    });
    closeSettings();
}

function pullOllamaModel() {
    const modelName = document.getElementById('pullModelInput').value.trim();
    if (!modelName) return;
    
    const statusEl = document.getElementById('pullStatus');
    const progressContainer = document.getElementById('pullProgressBar');
    const progressFill = document.getElementById('pullProgressFill');
    
    setPullUIState('downloading');
    
    if (!isPullPaused) {
        statusEl.innerHTML = `<span>Connecting: <b>${modelName}</b>...</span> <span>0%</span>`;
        progressContainer.style.display = 'block';
        progressFill.style.width = '0%';
        progressFill.style.background = 'var(--accent)';
    }

    pullAbortController = new AbortController();
    lastPullBytes = 0;
    lastPullTime = performance.now();
    currentSpeedText = "";

    fetch('/api/models/pull', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({model: modelName}),
        signal: pullAbortController.signal
    }).then(async response => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const {done, value} = await reader.read();
            if (done) { 
                fetchSettings();
                setPullUIState('idle');
                setTimeout(() => { progressContainer.style.display = 'none'; }, 4000);
                break; 
            }
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            lines.forEach(line => {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.substring(6));
                        
                        if (data.status && data.status !== 'success') {
                            let pct = 0;

                            if (data.total && data.completed) {
                                pct = Math.round((data.completed / data.total) * 100);

                                const now = performance.now();
                                const timeDiff = (now - lastPullTime) / 1000;

                                if (timeDiff >= 0.5) {
                                    const bytesDiff = data.completed - lastPullBytes;
                                    if (lastPullBytes > 0 && bytesDiff > 0) {
                                        const speedMB = (bytesDiff / (1024 * 1024)) / timeDiff;
                                        currentSpeedText = ` (${speedMB.toFixed(1)} MB/s)`;
                                    }
                                    lastPullBytes = data.completed;
                                    lastPullTime = now;
                                }
                            }

                            statusEl.innerHTML = `<span>${data.status}${currentSpeedText}</span> <span>${pct}%</span>`;
                            progressFill.style.width = `${pct}%`;
                        } else if (data.status === 'success') {
                            statusEl.innerHTML = `<span style="color:var(--success);"><i class="fas fa-check-circle"></i> Download Completed</span> <span>100%</span>`;
                            progressFill.style.width = '100%';
                            progressFill.style.background = 'var(--success)';
                            document.getElementById('pullModelInput').value = '';
                        }
                        
                        if (data.error) {
                            statusEl.innerHTML = `<span style="color:var(--danger);"><i class="fas fa-exclamation-triangle"></i> ${data.error}</span>`;
                            setPullUIState('idle');
                        }
                    } catch (e) {}
                }
            });
        }
    }).catch(err => {
        if (err.name !== 'AbortError') {
            statusEl.innerHTML = `<span style="color:var(--danger);"><i class="fas fa-exclamation-triangle"></i> Network/Connection Error</span>`;
            setPullUIState('idle');
        }
    });
}

async function deleteOllamaModel(modelName) {
    const confirmMsg = t('confirm_delete') || "Are you sure you want to completely delete the model:";
    if(!confirm(`${confirmMsg} ${modelName}?`)) return;
    
    const res = await fetch('/api/models/delete', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({model: modelName})
    });
    const data = await res.json();
    if(data.success) { 
        showToast(t('model_deleted') || "Model Deleted.", "success"); 
        fetchSettings(); 
    } else { 
        showToast(data.error, "warning"); 
    }
}

function resetPullUI() {
    document.getElementById('pullStartBtn').style.display = 'inline-flex';
    document.getElementById('pullCancelBtn').style.display = 'none';
    document.getElementById('pullModelInput').disabled = false;
}

function setPullUIState(state) {
    const startBtn = document.getElementById('pullStartBtn');
    const pauseBtn = document.getElementById('pullPauseBtn');
    const resumeBtn = document.getElementById('pullResumeBtn');
    const cancelBtn = document.getElementById('pullCancelBtn');
    const modelInput = document.getElementById('pullModelInput');

    startBtn.style.display = 'none';
    pauseBtn.style.display = 'none';
    resumeBtn.style.display = 'none';
    cancelBtn.style.display = 'none';
    modelInput.disabled = true;

    if (state === 'idle') {
        startBtn.style.display = 'inline-flex';
        modelInput.disabled = false;
    } else if (state === 'downloading') {
        pauseBtn.style.display = 'inline-flex';
        cancelBtn.style.display = 'inline-flex';
    } else if (state === 'paused') {
        resumeBtn.style.display = 'inline-flex';
        cancelBtn.style.display = 'inline-flex';
    }
}

function pauseOllamaPull() {
    isPullPaused = true;
    if (pullAbortController) {
        pullAbortController.abort();
        pullAbortController = null;
    }
    setPullUIState('paused');
    const statusEl = document.getElementById('pullStatus');
    statusEl.innerHTML = `<span style="color:var(--warning);"><i class="fas fa-pause-circle"></i> Download paused.</span>`;
}

function resumeOllamaPull() {
    isPullPaused = false;
    pullOllamaModel();
}

function cancelOllamaPull() {
    isPullPaused = false;
    if (pullAbortController) {
        pullAbortController.abort();
        pullAbortController = null;
    }
    setPullUIState('idle');
    const statusEl = document.getElementById('pullStatus');
    statusEl.innerHTML = `<span style="color:var(--danger);"><i class="fas fa-ban"></i> Download canceled.</span>`;
    
    const progressContainer = document.getElementById('pullProgressBar');
    setTimeout(() => { progressContainer.style.display = 'none'; }, 3000);
}