async function toggleWakeLock() {
    const toggle = document.getElementById('wakeLockToggle');
    if (toggle.checked) {
        try {
            wakeLock = await navigator.wakeLock.request('screen');
            showToast("Wake-Lock Active: Screen will not down.", "success");
            document.addEventListener('visibilitychange', handleVisibilityChange);
        } catch (err) {
            showToast("Your Browser does not supports Wake-Lock.", "warning");
            toggle.checked = false;
        }
    } else {
        if (wakeLock !== null) {
            wakeLock.release();
            wakeLock = null;
            document.removeEventListener('visibilitychange', handleVisibilityChange);
            showToast("Wake-Lock Closed.", "warning");
        }
    }
}

async function handleVisibilityChange() {
    if (wakeLock !== null && document.visibilityState === 'visible') {
        wakeLock = await navigator.wakeLock.request('screen');
    }
}

setInterval(() => {
    if (document.visibilityState === 'visible') {
        fetch('/api/ping_ui', { method: 'POST' }).catch(() => {});
    }
}, 10000);
fetch('/api/ping_ui', { method: 'POST' }).catch(() => {});

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('open');
    
    let backdrop = document.getElementById('sidebarBackdrop');
    if (!backdrop) {
        backdrop = document.createElement('div');
        backdrop.id = 'sidebarBackdrop';
        backdrop.className = 'sidebar-backdrop';
        backdrop.onclick = toggleSidebar;
        document.body.appendChild(backdrop);
    }
    backdrop.classList.toggle('active', sidebar.classList.contains('open'));
}

function toggleDropdown(id) {
    document.getElementById(id).classList.toggle('show');
}

function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
    if(textarea.value === '') {
        textarea.style.height = '44px';
    }
}

async function initApp() {
    applyTheme(currentTheme);
    document.documentElement.setAttribute('data-ui-theme', currentUITheme);
    const uiThemeSelectEl = document.getElementById('uiThemeSelect');
    if(uiThemeSelectEl) uiThemeSelectEl.value = currentUITheme;
    initCanvasBg();
    changeAccentColor(currentAccentColor);
    const colorSelectEl = document.getElementById('accentColorSelect');
    if(colorSelectEl) colorSelectEl.value = currentAccentColor;

    document.addEventListener('click', function(event) {
        const dropdown = document.getElementById('modelSettingsMenu');
        const trigger = event.target.closest('.dropdown');
        if (dropdown && dropdown.classList.contains('show') && !trigger) {
            dropdown.classList.remove('show');
        }
    });

    try {
        const res = await fetch('/static/web_lang.json');
        i18nData = await res.json();
        
        const langSelect = document.getElementById('langSelect');
        if (langSelect) langSelect.value = currentLang;

        applyTranslations();
    } catch(e) {
        console.error("Failed to load web_lang.json", e);
    }
    
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            highlight: function(code, lang) {
                const language = hljs.getLanguage(lang) ? lang : 'plaintext';
                return hljs.highlight(code, { language }).value;
            }, breaks: true
        });
    }
    
    loadChats();
    updateActionOptions('text');
    
    const tx = document.getElementById("promptInput");
    if(tx) {
        tx.addEventListener("input", function() { autoResize(this); }, false);
    }
}

function t(key) {
    if (i18nData[currentLang] && i18nData[currentLang][key]) {
        return i18nData[currentLang][key];
    }
    if (i18nData['en'] && i18nData['en'][key]) {
        return i18nData['en'][key];
    }
    return key;
}

function changeLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('heater_lang', lang);
    applyTranslations();
    updateActionOptions('text');
    loadChats();
    
    const chatWindow = document.getElementById('chatWindow');
    if (!currentChatId && chatWindow.innerHTML.includes('fa-robot')) {
        chatWindow.innerHTML = `<div class="welcome-screen"><div class="welcome-icon"><i class="fas fa-robot"></i></div><p>${t('welcome_message')}</p></div>`;
    }
}

function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        el.innerHTML = t(key);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        el.placeholder = t(key);
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        const key = el.getAttribute('data-i18n-title');
        el.title = t(key);
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

function showToast(message, type = 'warning') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icon = type === 'warning' ? 'fa-exclamation-triangle' : 'fa-check-circle';
    toast.innerHTML = `<i class="fas ${icon}"></i> <span>${message}</span>`;
    
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.4s ease forwards';
        setTimeout(() => toast.remove(), 400);
    }, 4000);
}

async function uploadTrainData(input) {
    const file = input.files[0];
    if(!file) return;
    showToast(t('toast_training'), "warning");
    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch('/api/train_document', { method: 'POST', body: formData });
        const data = await res.json();
        if(data.success) {
            showToast(data.message, "success");
        } else {
            showToast(data.error, "warning");
        }
    } catch(e) {
        showToast(t('toast_train_error'), "warning");
    }
    input.value = '';
}

setInterval(async () => {
    try {
        const res = await fetch('/api/system_status');
        const data = await res.json();
        
        if (data.last_completed) {
            showToast(`✅ ${t('toast_process_success')} (${data.last_completed.time})`, 'success');
            loadChats();
            if (currentChatId === data.last_completed.chat_id) {
                loadChatHistory(currentChatId);
            }
        }
    } catch (e) {}
}, 3000);

function updateActionOptions(fileType) {
    const actionSelect = document.getElementById('processAction');
    if(!actionSelect) return;
    actionSelect.innerHTML = '';
    
    let options = [];
    
    if (!fileType || fileType === 'text') {
        options = [
            { value: 'analyze', label: t('opt_analyze') },
            { value: 'to pdf', label: t('opt_pdf') },
            { value: 'to image', label: t('opt_image') },
            { value: 'to video', label: t('opt_video') },
            { value: 'to music', label: t('opt_music') },
            { value: 'to audio', label: t('opt_audio') }
        ];
    } else if (fileType === 'image') {
        options = [
            { value: 'analyze', label: t('opt_analyze') },
            { value: 'to i2i', label: t('opt_i2i') }, 
            { value: 'to i2v', label: t('opt_i2v') }, 
            { value: 'to ref video', label: t('opt_ref_video') },
            { value: 'to ref image', label: t('opt_ref_image') },
            { value: 'to 3d model', label: t('opt_3d') },
            { value: 'to outpaint', label: t('opt_outpaint') }
        ];
    } else if (fileType === 'audio') {
        options = [
            { value: 'analyze', label: t('opt_analyze') },
            { value: 'to sample with text', label: t('opt_sample') }
        ];
    } else if (fileType === 'video') {
        options = [
            { value: 'analyze', label: t('opt_analyze') }
        ];
    }
    
    options.forEach(opt => {
        const el = document.createElement('option');
        el.value = opt.value;
        el.textContent = opt.label;
        if(opt.value === 'analyze') el.selected = true;
        actionSelect.appendChild(el);
    });

    actionSelect.dispatchEvent(new Event('change'));
}

document.getElementById('processAction').addEventListener('change', function() {
    const opDiv = document.getElementById('outpaintOptions');
    if (this.value === 'to outpaint') {
        opDiv.style.display = 'flex';
    } else {
        opDiv.style.display = 'none';
    }
    const bypassRow = document.getElementById('bypassEnhanceRow');
    const bypassToggle = document.getElementById('bypassEnhanceToggle');
    if (['to music', 'to ref video', 'to ref image', 'analyze', 'to pdf'].includes(this.value)) {
        if (bypassRow) bypassRow.style.display = 'none';
        if (bypassToggle) bypassToggle.checked = false;
    } else {
        if (bypassRow) bypassRow.style.display = 'flex';
    }
});

document.getElementById('opRatio').addEventListener('change', function() {
    if (this.value === 'custom') return;
    
    if (!uploadedImageWidth || !uploadedImageHeight) {
        showToast(t('toast_upload_img_first'), "warning");
        this.value = 'custom';
        return;
    }

    const [num, den] = this.value.split('/');
    const targetRatio = parseFloat(num) / parseFloat(den);
    const currentRatio = uploadedImageWidth / uploadedImageHeight;

    let left = 0, right = 0, top = 0, bottom = 0;

    if (currentRatio < targetRatio) {
        const targetWidth = Math.round(uploadedImageHeight * targetRatio);
        const totalDiff = targetWidth - uploadedImageWidth;
        left = Math.floor(totalDiff / 2);
        right = Math.ceil(totalDiff / 2);
    } else if (currentRatio > targetRatio) {
        const targetHeight = Math.round(uploadedImageWidth / targetRatio);
        const totalDiff = targetHeight - uploadedImageHeight;
        top = Math.floor(totalDiff / 2);
        bottom = Math.ceil(totalDiff / 2);
    }

    document.getElementById('opLeft').value = left;
    document.getElementById('opRight').value = right;
    document.getElementById('opTop').value = top;
    document.getElementById('opBottom').value = bottom;
});

function handleEnter(e) { 
    if (e.key === 'Enter' && !e.shiftKey) { 
        e.preventDefault(); 
        if(!isGenerating) sendMessage(); 
    } 
}

function exportChatPDF() {
    if (!currentChatId) { 
        alert(t('alert_start_chat')); 
        return; 
    }
    window.open(`/api/export_chat/${currentChatId}`, '_blank');
}

document.getElementById('fileUpload').onchange = function(e) {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    attachedRawFile = files[0];
    attachedRawFiles = files;
    
    const file = files[0];
    if (file.size > 100 * 1024 * 1024) {
        alert(t('alert_file_too_large'));
        this.value = '';
        return;
    }
    
    frontendImageBase64 = null;
    frontendTextContent = null;
    
    const isImage = file.type.startsWith('image/');
    const isVideo = file.type.startsWith('video/');
    const isAudio = file.type.startsWith('audio/');
    const isText = file.type.match(/text.*/) || file.name.match(/\.(txt|md|py|js|html|css|json|csv)$/i);
    const isDoc = file.name.match(/\.(pdf|doc|docx)$/i);
    
    let icon = isImage ? 'fa-image' : (isVideo ? 'fa-video' : (isAudio ? 'fa-music' : (isDoc ? 'fa-file-pdf' : 'fa-file-alt')));
    let type = isImage ? 'image' : (isVideo ? 'video' : (isAudio ? 'audio' : 'text'));
    
    updateActionOptions(type);
    
    const prev = document.getElementById('attachmentPreview');
    if (isImage) {
        const reader = new FileReader();
        reader.onload = evt => {
            frontendImageBase64 = evt.target.result;
            const img = new Image();
            img.onload = () => {
                uploadedImageWidth = img.width;
                uploadedImageHeight = img.height;
                document.getElementById('opRatio').dispatchEvent(new Event('change'));
            };
            img.src = frontendImageBase64;
        };
        reader.readAsDataURL(file);
    } else if (isText) {
        const reader = new FileReader();
        reader.onload = evt => frontendTextContent = evt.target.result;
        reader.readAsText(file);
    }
    
    if (files.length > 1) {
        prev.innerHTML = `<div class="file-pill">
            <i class="fas fa-copy" style="color:var(--accent);"></i> <span>${files.length} ${t('files_attached')}</span>
            <button onclick="removeAttachment()" style="background:none; border:none; color:var(--danger); cursor:pointer; padding: 2px 6px; margin-left: 5px;"><i class="fas fa-times"></i></button>
        </div>`;
    } else {
        prev.innerHTML = `<div class="file-pill">
            <i class="fas ${icon}" style="color:var(--accent);"></i> <span>${file.name}</span>
            <button onclick="removeAttachment()" style="background:none; border:none; color:var(--danger); cursor:pointer; padding: 2px 6px; margin-left: 5px;"><i class="fas fa-times"></i></button>
        </div>`;
    }
    prev.style.display = 'block';
    this.value = ''; 
};

function removeAttachment() { 
    attachedRawFile = null; 
    attachedRawFiles = []; 
    frontendImageBase64 = null;
    frontendTextContent = null;
    document.getElementById('attachmentPreview').style.display = 'none';
    document.getElementById('fileUpload').value = '';
    updateActionOptions('text');
    uploadedImageWidth = 0;
    uploadedImageHeight = 0;
    document.getElementById('processAction').dispatchEvent(new Event('change'));
}

function toggleCoderMode() {
    const isCoder = document.getElementById('coderToggle').checked;
    const processSelect = document.getElementById('processAction');
    const fileInput = document.getElementById('fileUpload');
    const workspacePanel = document.getElementById('coderWorkspacePanel');
    const opDiv = document.getElementById('outpaintOptions');
    
    if (isCoder) {
        processSelect.value = 'analyze'; 
        processSelect.disabled = true;
        processSelect.style.opacity = '0.5';
        fileInput.multiple = true; 
        workspacePanel.style.display = 'flex';
        if(opDiv) opDiv.style.display = 'none';
    } else {
        processSelect.disabled = false;
        processSelect.style.opacity = '1';
        fileInput.multiple = false;
        workspacePanel.style.display = 'none';
    }
}

async function setWorkspace(actionType) {
    const path = document.getElementById('workspacePath').value;
    if(!path) { showToast(t('toast_enter_path'), "warning"); return; }
    const endpoint = actionType === 'create' ? '/api/coder/create' : '/api/coder/inspect';
    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ path: path })
        });
        const data = await res.json();
        if(data.success) {
            showToast(data.message, "success");
        } else {
            showToast(data.error || "Error", "warning");
        }
    } catch(e) { showToast(t('toast_conn_error'), "warning"); }
}
