async function loadChats() {
    const res = await fetch('/api/chats');
    const chats = await res.json();
    const list = document.getElementById('chatList');
    list.innerHTML = '';
    chats.forEach(chat => {
        const div = document.createElement('div');
        const isActive = currentChatId !== null && String(chat.id) === String(currentChatId);
        div.className = `chat-item ${isActive ? 'active' : ''} ${chat.is_pinned ? 'pinned' : ''}`;
        div.setAttribute('data-chat-id', chat.id);

        const pinClass = chat.is_pinned ? 'active' : '';
        const pinIcon = chat.is_pinned ? '<i class="fas fa-thumbtack" style="color:var(--accent); margin-right:6px; font-size:11px; margin-top:3px;"></i>' : '<i class="far fa-comment-alt" style="color:var(--text-muted); margin-right:6px; font-size:13px; margin-top:3px;"></i>';

        div.innerHTML = `
            <div class="chat-title-container">
                ${pinIcon}
                <span class="chat-title" id="chat-title-text-${chat.id}" title="${chat.title}">${chat.title}</span>
                <input type="text" id="chat-title-input-${chat.id}" value="${chat.title}" 
                       style="display:none; width:100%; background:var(--bg-input); color:var(--text-main); border:1px solid var(--accent); border-radius:4px; padding:3px 6px; font-size:13px; outline:none;" 
                       onblur="saveChatTitle(${chat.id})" 
                       onkeydown="if(event.key === 'Enter') { this.blur(); }">
            </div>
            <div class="chat-actions" id="chat-actions-${chat.id}">
                <button class="chat-action-btn pin ${pinClass}" onclick="togglePinChat(${chat.id}, ${chat.is_pinned}, event)"><i class="fas fa-thumbtack"></i></button>
                <button class="chat-action-btn edit" onclick="editChatTitle(${chat.id}, event)"><i class="fas fa-pen"></i></button>
                <button class="chat-action-btn delete" onclick="deleteChat(${chat.id}, event)"><i class="fas fa-trash-alt"></i></button>
            </div>
        `;
        
        div.onclick = (e) => { 
            if(!e.target.closest('.chat-actions') && e.target.tagName !== 'INPUT') {
                loadChatHistory(chat.id); 
            }
        };
        list.appendChild(div);
    });
}

function filterChats(query) {
    query = query.toLowerCase().trim();
    const chatItems = document.querySelectorAll('#chatList .chat-item');
    
    chatItems.forEach(item => {
        const titleEl = item.querySelector('.chat-title');
        if (titleEl) {
            const title = titleEl.textContent.toLowerCase();
            if (title.includes(query)) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        }
    });
}

function editChatTitle(id, event) {
    if(event) event.stopPropagation();
    document.getElementById(`chat-title-text-${id}`).style.display = 'none';
    
    const actions = document.getElementById(`chat-actions-${id}`);
    if(actions) actions.style.display = 'none';

    const input = document.getElementById(`chat-title-input-${id}`);
    input.style.display = 'block';
    input.focus();
    input.select();
}

async function saveChatTitle(id) {
    const input = document.getElementById(`chat-title-input-${id}`);
    const newTitle = input.value.trim();
    
    if (newTitle) {
        document.getElementById(`chat-title-text-${id}`).textContent = newTitle;
        await fetch(`/api/chat/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title: newTitle})
        });
    }
    
    document.getElementById(`chat-title-text-${id}`).style.display = 'block';
    input.style.display = 'none';
    
    const actions = document.getElementById(`chat-actions-${id}`);
    if(actions) actions.style.display = '';

    loadChats();
}

async function togglePinChat(id, currentState, event) {
    if(event) event.stopPropagation();
    await fetch(`/api/chat/${id}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({is_pinned: currentState ? 0 : 1})
    });
    loadChats();
}

async function deleteChat(id, event) {
    if (event) event.stopPropagation();
    await fetch(`/api/chat/${id}`, { method: 'DELETE' });
    if (currentChatId === id) startNewChat();
    else loadChats();
}

function startNewChat() {
    if(isGenerating) return;
    if(currentAudio) { currentAudio.pause(); currentAudio = null; }
    currentChatId = null;
    
    document.querySelectorAll('.chat-item').forEach(item => item.classList.remove('active'));
    
    document.getElementById('chatWindow').innerHTML = `<div class="welcome-screen"><div class="welcome-icon"><i class="fas fa-robot"></i></div><p>${t('welcome_message')}</p></div>`;
    loadChats();
}

async function loadChatHistory(id) {
    if(currentAudio) { currentAudio.pause(); currentAudio = null; }
    currentChatId = id;

    document.querySelectorAll('.chat-item').forEach(item => {
        if (item.getAttribute('data-chat-id') === String(id)) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    const res = await fetch(`/api/chat/${id}`);
    const messages = await res.json();
    const windowEl = document.getElementById('chatWindow');
    windowEl.innerHTML = '';
    windowChatMessages = {}; 

    messages.forEach(msg => {
        windowChatMessages[msg.id] = msg;
        
        const wrapper = document.createElement('div');
        wrapper.className = `message-wrapper ${msg.role === 'user' ? 'user' : 'bot'}`;
        wrapper.id = `msg-wrap-${msg.id}`;
        
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${msg.role === 'user' ? 'user-msg' : 'bot-msg'}`;
        msgDiv.id = `msg-${msg.id}`;
        
        const actionsHtml = `
            <div class="msg-actions">
                <button class="action-btn" id="tts-btn-${msg.id}" onclick="playTTS(${msg.id})"><i class="fas fa-volume-up"></i></button>
                ${msg.role === 'user' ? `<button class="action-btn" onclick="startEdit(${msg.id})"><i class="fas fa-edit"></i></button>` : ''}
                ${msg.role === 'assistant' ? `<button class="action-btn" onclick="regenerateBotMsg(${msg.id})"><i class="fas fa-sync-alt"></i></button>` : ''}
                <button class="action-btn" onclick="copyMsg(${msg.id})"><i class="fas fa-copy"></i></button>
                <button class="action-btn" onclick="deleteMsg(${msg.id})"><i class="fas fa-trash"></i></button>
            </div>
        `;

        const contentDiv = document.createElement('div');
        contentDiv.id = `msg-content-${msg.id}`;

        if (msg.role === 'user') {
            let displayContent = msg.content;
            const fileIdx = displayContent.indexOf('[File Content]:');
            if(fileIdx !== -1) displayContent = displayContent.substring(0, fileIdx);
            const audioIdx = displayContent.indexOf('[Detected Audio Types]:');
            if(audioIdx !== -1) displayContent = displayContent.substring(0, audioIdx);
            const transcriptIdx = displayContent.indexOf('[Speech Transcript]:');
            if(transcriptIdx !== -1) displayContent = displayContent.substring(0, transcriptIdx);

            displayContent = displayContent.replace(/^\[.*? Request\]\n/, ''); 
            let safeContent = displayContent.replace(/</g, "&lt;").replace(/>/g, "&gt;");

            if(fileIdx !== -1) {
            safeContent += `<br><div class="file-pill"><i class="fas fa-paperclip"></i> ${t('attached_doc_processed')}</div>`;
            }

            safeContent = safeContent.replace(/!\[(.*?)\]\((data:image\/[^)]+)\)/g, '<br><div class="file-pill"><i class="fas fa-image"></i> $1</div>');

            contentDiv.style.whiteSpace = "pre-wrap";
            contentDiv.innerHTML = safeContent;
            msgDiv.appendChild(contentDiv);
            msgDiv.insertAdjacentHTML('beforeend', actionsHtml);
        } else {
            renderStreamingMessage(contentDiv, msg.content, []);
            msgDiv.appendChild(contentDiv);
            msgDiv.insertAdjacentHTML('beforeend', actionsHtml);
        }
        
        wrapper.appendChild(msgDiv);
        windowEl.appendChild(wrapper);
    });

    if (activeGenerations[id] && !activeGenerations[id].isDone) {
        const botWrapper = document.createElement('div');
        botWrapper.className = 'message-wrapper bot';
        const liveBotMsgDiv = document.createElement('div');
        liveBotMsgDiv.className = 'message bot-msg';
        liveBotMsgDiv.id = `live-stream-${id}`;
        botWrapper.appendChild(liveBotMsgDiv);
        windowEl.appendChild(botWrapper);
        renderStreamingMessage(liveBotMsgDiv, activeGenerations[id].fullText, activeGenerations[id].statusLogs);
    }
}

const originalLoadChatHistory = loadChatHistory;
loadChatHistory = async function(id) {
    if (window.innerWidth <= 768) {
        const sidebar = document.getElementById('sidebar');
        if (sidebar && sidebar.classList.contains('open')) {
            toggleSidebar();
        }
    }
    return originalLoadChatHistory(id);
};

async function playTTS(msgId) {
    const btn = document.getElementById(`tts-btn-${msgId}`);
    if (currentAudio && currentAudioMsgId === msgId) {
        currentAudio.pause();
        currentAudio = null;
        currentAudioMsgId = null;
        if(btn) btn.innerHTML = '<i class="fas fa-volume-up"></i>';
        return;
    }

    if (currentAudio) {
        currentAudio.pause();
        const prevBtn = document.getElementById(`tts-btn-${currentAudioMsgId}`);
        if (prevBtn) prevBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
        currentAudio = null;
        currentAudioMsgId = null;
    }

    const msg = windowChatMessages[msgId];
    if (!msg) return;

    let cleanText = msg.content;
    cleanText = cleanText.replace(/<think>[\s\S]*?<\/think>/g, '').replace(/<think>[\s\S]*/g, '');
    const fileIdx = cleanText.indexOf('\n\n[File Content]:');
    if(fileIdx !== -1) cleanText = cleanText.substring(0, fileIdx);
    const audioIdx = cleanText.indexOf('\n\n[Detected Audio Types]:');
    if(audioIdx !== -1) cleanText = cleanText.substring(0, audioIdx);
    const transcriptIdx = cleanText.indexOf('\n\n[Speech Transcript]:');
    if(transcriptIdx !== -1) cleanText = cleanText.substring(0, transcriptIdx);
    cleanText = cleanText.replace(/^\[.*? Request\]\n/, '').replace(/!\[.*?\]\([^)]+\)/g, '').trim();

    if (!cleanText) return;
    if (btn) btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    try {
        const res = await fetch('/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: cleanText })
        });
        const data = await res.json();

        if (data.success && data.audio_url) {
            currentAudio = new Audio(data.audio_url);
            currentAudioMsgId = msgId;
            if (btn) btn.innerHTML = '<i class="fas fa-stop" style="color:var(--accent);"></i>';

            currentAudio.onended = () => {
                if (btn) btn.innerHTML = '<i class="fas fa-volume-up"></i>';
                currentAudio = null;
                currentAudioMsgId = null;
            };
            currentAudio.onerror = () => {
                if (btn) btn.innerHTML = '<i class="fas fa-volume-up"></i>';
                currentAudio = null;
                currentAudioMsgId = null;
            };

            await currentAudio.play();
        } else {
            alert(data.error || 'TTS error occurred.');
            if (btn) btn.innerHTML = '<i class="fas fa-volume-up"></i>';
        }
    } catch (e) {
        if (btn) btn.innerHTML = '<i class="fas fa-volume-up"></i>';
    }
}

function startEdit(id) {
    if(isGenerating) return;
    const msg = windowChatMessages[id];
    if(!msg) return;

    let cleanText = msg.content;
    const fileIdx = cleanText.indexOf('\n\n[File Content]:');
    if(fileIdx !== -1) cleanText = cleanText.substring(0, fileIdx);
    const audioIdx = cleanText.indexOf('\n\n[Detected Audio Types]:');
    if(audioIdx !== -1) cleanText = cleanText.substring(0, audioIdx);
    const transcriptIdx = cleanText.indexOf('\n\n[Speech Transcript]:');
    if(transcriptIdx !== -1) cleanText = cleanText.substring(0, transcriptIdx);
    cleanText = cleanText.replace(/^\[.*? Request\]\n/, '').replace(/!\[.*?\]\(data:image\/[^)]+\)/g, '').trim();

    const msgDiv = document.getElementById(`msg-${id}`);
    msgDiv.innerHTML = `
        <textarea id="edit-textarea-${id}" class="edit-textarea">${cleanText}</textarea>
        <div class="edit-actions-row">
            <button class="btn-secondary" style="padding: 6px 12px; font-size:13px;" onclick="cancelEdit(${id})">${t('cancel_btn')}</button>
            <button class="btn-secondary" style="padding: 6px 12px; font-size:13px; border-color:var(--accent);" onclick="saveEdit(${id})">${t('save_only')}</button>
            <button class="btn-primary" style="width:auto; padding: 6px 14px; font-size:13px;" onclick="saveEditAndResend(${id})"><i class="fas fa-paper-plane"></i> ${t('save_and_resend')}</button>
        </div>
    `;
}

function cancelEdit(id) { loadChatHistory(currentChatId); }

async function saveEdit(id) {
    const newContent = document.getElementById(`edit-textarea-${id}`).value.trim();
    if (!newContent) return cancelEdit(id);
    
    const msg = windowChatMessages[id];
    let originalContent = msg.content;
    let fileContexts = "";
    const fileIdx = originalContent.indexOf('\n\n[File Content]:');
    if(fileIdx !== -1) fileContexts += originalContent.substring(fileIdx);
    else {
        const audioIdx = originalContent.indexOf('\n\n[Detected Audio Types]:');
        if(audioIdx !== -1) fileContexts += originalContent.substring(audioIdx);
        else {
            const transcriptIdx = originalContent.indexOf('\n\n[Speech Transcript]:');
            if(transcriptIdx !== -1) fileContexts += originalContent.substring(transcriptIdx);
        }
    }
    
    let actionStr = "";
    const actionMatch = originalContent.match(/^\[(.*?) Request\]\n/);
    if (actionMatch) actionStr = `[${actionMatch[1]} Request]\n`;
    
    const finalContent = actionStr + newContent + fileContexts;
    
    await fetch(`/api/message/${id}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({content: finalContent}) });
    loadChatHistory(currentChatId);
}

async function saveEditAndResend(id) {
    const newContent = document.getElementById(`edit-textarea-${id}`).value.trim();
    if (!newContent) return cancelEdit(id);
    
    const msg = windowChatMessages[id];
    let originalContent = msg.content;
    let action = 'analyze';
    const actionMatch = originalContent.match(/^\[(.*?) Request\]\n/);
    if (actionMatch) action = actionMatch[1].toLowerCase();

    let fileContexts = "";
    const fileIdx = originalContent.indexOf('\n\n[File Content]:');
    if(fileIdx !== -1) fileContexts += originalContent.substring(fileIdx);
    else {
        const audioIdx = originalContent.indexOf('\n\n[Detected Audio Types]:');
        if(audioIdx !== -1) fileContexts += originalContent.substring(audioIdx);
        else {
            const transcriptIdx = originalContent.indexOf('\n\n[Speech Transcript]:');
            if(transcriptIdx !== -1) fileContexts += originalContent.substring(transcriptIdx);
        }
    }
    
    const imgRegex = /!\[.*?\]\((data:image\/[^)]+)\)/g;
    let match;
    while ((match = imgRegex.exec(originalContent)) !== null) {
        if(!fileContexts.includes(match[0])) {
            fileContexts += `\n\n${match[0]}`;
        }
    }

    await fetch(`/api/message/${id}`, { method: 'DELETE' });
    
    const msgs = Object.values(windowChatMessages);
    const idx = msgs.findIndex(m => m.id === id);
    if (idx !== -1 && idx + 1 < msgs.length) {
         const nextMsg = msgs[idx + 1];
         if (nextMsg.role === 'assistant') {
             await fetch(`/api/message/${nextMsg.id}`, { method: 'DELETE' });
         }
    }
    
    let cleanPromptForCache = newContent.replace(/^\[.*? Request\]\n/, '').trim();
    let cachedFile = sessionFileCache[cleanPromptForCache] || null;

    sendMessage(newContent + fileContexts, action, cachedFile);
}

async function regenerateBotMsg(botMsgId) {
    if(isGenerating) return;
    const msgs = Object.values(windowChatMessages);
    const idx = msgs.findIndex(m => m.id === botMsgId);
    if(idx <= 0) return;

    const prevUserMsg = msgs[idx - 1];
    if(prevUserMsg.role !== 'user') return;

    let action = 'analyze';
    let rawContent = prevUserMsg.content;

    const actionMatch = rawContent.match(/^\[(.*?) Request\]\n/);
    if (actionMatch) action = actionMatch[1].toLowerCase();

    let textContexts = "";
    const fileIdx = rawContent.indexOf('\n\n[File Content]:');
    if(fileIdx !== -1) textContexts += rawContent.substring(fileIdx);
    else {
        const audioIdx = rawContent.indexOf('\n\n[Detected Audio Types]:');
        if(audioIdx !== -1) textContexts += rawContent.substring(audioIdx);
        else {
            const transcriptIdx = rawContent.indexOf('\n\n[Speech Transcript]:');
            if(transcriptIdx !== -1) textContexts += rawContent.substring(transcriptIdx);
        }
    }
    textContexts = textContexts.replace(/!\[.*?\]\((data:image\/[^)]+)\)/g, '').trim();

    let promptOnly = rawContent.replace(/^\[.*? Request\]\n/, '');
    const fIdx = promptOnly.indexOf('\n\n[File Content]:');
    if(fIdx !== -1) promptOnly = promptOnly.substring(0, fIdx);
    const aIdx = promptOnly.indexOf('\n\n[Detected Audio Types]:');
    if(aIdx !== -1) promptOnly = promptOnly.substring(0, aIdx);
    const tIdx = promptOnly.indexOf('\n\n[Speech Transcript]:');
    if(tIdx !== -1) promptOnly = promptOnly.substring(0, tIdx);

    let extractedBase64 = null;
    const imgRegex = /!\[.*?\]\((data:image\/[^;]+;base64,([a-zA-Z0-9+/=]+))\)/g;
    let match = imgRegex.exec(promptOnly);
    if (match) {
        extractedBase64 = match[1];
    }
    promptOnly = promptOnly.replace(/!\[.*?\]\((data:image\/[^)]+)\)/g, '').trim();

    await fetch(`/api/message/${botMsgId}`, { method: 'DELETE' });
    await fetch(`/api/message/${prevUserMsg.id}`, { method: 'DELETE' });

    let cleanPromptForCache = promptOnly.trim();
    let cachedFile = sessionFileCache[cleanPromptForCache] || null;

    if (!cachedFile && extractedBase64) {
        try {
            let arr = extractedBase64.split(',');
            let mime = arr[0].match(/:(.*?);/)[1];
            let bstr = atob(arr[1]);
            let n = bstr.length;
            let u8arr = new Uint8Array(n);
            while(n--){
                u8arr[n] = bstr.charCodeAt(n);
            }
            cachedFile = new File([u8arr], "recovered_image.jpg", {type: mime});
        } catch(e) {}
    }

    let finalPrompt = promptOnly;
    if(textContexts.length > 0) finalPrompt += "\n\n" + textContexts;

    sendMessage(finalPrompt, action, cachedFile);
}

async function copyMsg(id) {
    const msg = windowChatMessages[id];
    if (!msg) return;
    
    let text = msg.content;
    text = text.replace(/<think>[\s\S]*?<\/think>/g, '')
            .replace(/<think>[\s\S]*/g, '')
            .trim();

    if (navigator.clipboard && window.isSecureContext) {
        try {
            await navigator.clipboard.writeText(text);
            showToast(t('toast_copied'), "success");
            return;
        } catch (err) {}
    }

    try {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        textArea.style.top = "-999999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);
        
        if (successful) {
            showToast(t('toast_copied'), "success");
        } else {
            showToast(t('toast_copy_fail'), "warning");
        }
    } catch (err) {
        showToast(t('toast_copy_fail'), "warning");
    }
}

async function deleteMsg(id) {
    document.getElementById(`msg-wrap-${id}`).style.opacity = '0.3';
    await fetch(`/api/message/${id}`, { method: 'DELETE' });
    loadChatHistory(currentChatId); 
}

function renderStreamingMessage(element, fullText, statusHistory = []) {
    let thinkText = "", answerText = fullText;
    let isThinkingClosed = false;

    if (fullText.includes("<think>")) {
        if (fullText.includes("</think>")) {
            let parts = fullText.split("</think>");
            thinkText = parts[0].replace("<think>", "").trim();
            answerText = parts.slice(1).join("</think>").trim();
            isThinkingClosed = true;
        } else {
            thinkText = fullText.replace("<think>", "").trim();
            answerText = "";
            isThinkingClosed = false;
        }
    }
    
    let html = "";

    if (statusHistory && statusHistory.length > 0) {
        const lastStatus = statusHistory[statusHistory.length - 1];
        const shouldOpen = isGenerating ? 'open' : '';
        
        html += `<details class="status-box" ${shouldOpen}>
            <summary><i class="fas fa-tasks" style="color:var(--accent);"></i> <span>${t('activity_tasks')} (${statusHistory.length})</span> <span style="font-size:11px; opacity:0.7; margin-left:auto;">${lastStatus}</span></summary>
            <div class="status-content">
                ${statusHistory.map(st => `<div class="status-entry"><i class="fas fa-chevron-right" style="font-size:9px; color:var(--accent);"></i> ${st}</div>`).join('')}
            </div>
        </details>`;
    }

    if (thinkText) {
        let isOpen = (!answerText || !isThinkingClosed) ? "open" : "";
        let iconClass = !isThinkingClosed && isGenerating ? "fa-spinner fa-spin" : "fa-brain";
        html += `<details class="think-box" ${isOpen}>
            <summary><i class="fas ${iconClass}"></i> ${t('thought_process')} ${!isThinkingClosed && isGenerating ? '(' + t('thinking') + '...)' : ''}</summary>
            <div class="think-content markdown-body">${marked.parse(thinkText)}</div>
        </details>`;
    }

    if (answerText) {
        html += `<div class="markdown-body">${marked.parse(answerText)}</div>`;
    } else if (!thinkText && isGenerating && (!statusHistory || statusHistory.length === 0)) {
        html += `<div style="color: var(--accent); font-style: italic; display:flex; align-items:center; gap:8px;">${t('generating_response')}<span class="dot-typing">...</span></div>`;
    }
    
    element.innerHTML = html;

    element.querySelectorAll('pre').forEach(async (block) => {
        const codeEl = block.querySelector('code');
        if (!codeEl) return;

        if (codeEl.className.includes('language-mermaid') || codeEl.className.includes('mermaid')) {
            if (isGenerating) return; 

            if (!block.dataset.mermaidRendered) {
                block.dataset.mermaidRendered = "true";
                const mermaidCode = codeEl.innerText.trim();
                
                try {
                    const id = 'mermaid-' + Math.random().toString(36).substr(2, 9);
                    const { svg } = await mermaid.render(id, mermaidCode);
                    
                    const container = document.createElement('div');
                    container.style.position = 'relative';
                    container.style.background = '#0d1117';
                    container.style.padding = '40px 16px 16px 16px';
                    container.style.borderRadius = '8px';
                    container.style.border = '1px solid var(--border)';
                    container.style.margin = '1em 0';
                    container.style.overflowX = 'auto';
                    container.style.display = 'flex';
                    container.style.justifyContent = 'center';
                    
                    container.innerHTML = svg;
                    
                    const btnContainer = document.createElement('div');
                    btnContainer.className = 'action-btns';
                    btnContainer.style.position = 'absolute';
                    btnContainer.style.top = '8px';
                    btnContainer.style.right = '8px';
                    btnContainer.style.display = 'flex';
                    btnContainer.style.gap = '5px';

                    const saveBtn = document.createElement('button');
                    saveBtn.className = 'copy-btn';
                    saveBtn.style.position = 'static';
                    saveBtn.innerHTML = `<i class="fas fa-download"></i> ${t('btn_save_svg')}`;
                    saveBtn.onclick = () => {
                        const blob = new Blob([svg], {type: 'image/svg+xml;charset=utf-8'});
                        const a = document.createElement('a');
                        a.href = URL.createObjectURL(blob);
                        a.download = `Diagram_${id}.svg`;
                        a.click();
                        URL.revokeObjectURL(a.href);
                    };

                    const copyBtn = document.createElement('button');
                    copyBtn.className = 'copy-btn';
                    copyBtn.style.position = 'static';
                    copyBtn.innerHTML = `<i class="fas fa-code"></i> ${t('btn_copy_code')}`;
                    copyBtn.onclick = () => { navigator.clipboard.writeText(mermaidCode); };

                    btnContainer.appendChild(copyBtn);
                    btnContainer.appendChild(saveBtn);
                    container.appendChild(btnContainer);
                    
                    block.replaceWith(container);
                    return;

                } catch (e) {
                    document.querySelectorAll('[id^="dmermaid"]').forEach(el => el.remove());
                    block.dataset.skipActions = "true";
                    codeEl.className = 'language-plaintext'; 
                    
                    const errorNotice = document.createElement('div');
                    errorNotice.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${t('mermaid_error')}`;
                    errorNotice.style.cssText = 'color: var(--warning); font-size: 12px; margin-bottom: 10px; font-weight: 500; letter-spacing: 0.5px;';
                    block.insertBefore(errorNotice, codeEl);
                    
                    return;
                }
            } else {
                return;
            }
        }

        if (!block.querySelector('.action-btns') && block.dataset.skipActions !== "true") {
            block.style.position = 'relative';
            
            const btnContainer = document.createElement('div');
            btnContainer.className = 'action-btns';
            btnContainer.style.position = 'absolute';
            btnContainer.style.top = '8px';
            btnContainer.style.right = '8px';
            btnContainer.style.display = 'flex';
            btnContainer.style.gap = '5px';

            const copyBtn = document.createElement('button');
            copyBtn.className = 'copy-btn';
            copyBtn.style.position = 'static';
            copyBtn.innerHTML = `<i class="fas fa-copy"></i> ${t('btn_copy')}`;
            copyBtn.onclick = () => { navigator.clipboard.writeText(block.querySelector('code').innerText); };
            
            const dlBtn = document.createElement('button');
            dlBtn.className = 'copy-btn';
            dlBtn.style.position = 'static';
            dlBtn.innerHTML = `<i class="fas fa-download"></i> ${t('btn_download')}`;
            dlBtn.onclick = async () => {
                const codeText = block.querySelector('code').innerText;
                dlBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                try {
                    const res = await fetch('/api/analyze_code', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({code: codeText}) });
                    const data = await res.json();
                    const a = document.createElement('a');
                    a.href = URL.createObjectURL(new Blob([codeText], { type: 'text/plain' }));
                    a.download = 'generated_code' + (data.ext || '.txt');
                    a.click();
                    dlBtn.innerHTML = `<i class="fas fa-check"></i> ${t('btn_saved')}`;
                } catch(e) { dlBtn.innerHTML = t('btn_error'); }
                setTimeout(() => dlBtn.innerHTML = `<i class="fas fa-download"></i> ${t('btn_download')}`, 3000);
            };

            btnContainer.appendChild(copyBtn);
            btnContainer.appendChild(dlBtn);
            block.appendChild(btnContainer);
        }
    });
}

function cancelGeneration() {
    if (!isGenerating || !currentChatId) return;
    isGenerating = false;
    if (currentAbortController) currentAbortController.abort(); 
    fetch(`/api/cancel/${currentChatId}`, { method: 'POST' });
    document.getElementById('sendBtn').style.display = 'block';
    document.getElementById('cancelBtn').style.display = 'none';
}

async function sendMessage(overridePrompt = null, overrideAction = null, overrideFile = null) {
    const input = document.getElementById('promptInput');
    let prompt = overridePrompt !== null ? overridePrompt : input.value.trim();
    const action = overrideAction !== null ? overrideAction : document.getElementById('processAction').value;
    
    if (!prompt && !attachedRawFile && !overrideFile && action === 'analyze') return;

    const formData = new FormData();
    formData.append('prompt', prompt);
    formData.append('action', action);
    if (currentChatId) formData.append('chatId', currentChatId);
    formData.append('thinking', document.getElementById('thinkingToggle').checked);
    formData.append('webSearch', document.getElementById('searchToggle').checked);
    formData.append('useContext', document.getElementById('useContextToggle').checked);
    formData.append('autoLearn', document.getElementById('autoLearnToggle').checked);
    formData.append('unlimitedToken', document.getElementById('unlimitedToggle').checked);
    formData.append('coderMode', document.getElementById('coderToggle').checked);
    formData.append('workspacePath', document.getElementById('workspacePath') ? document.getElementById('workspacePath').value.trim() : '');
    formData.append('useKnowledgeBase', document.getElementById('kbToggle').checked);
    formData.append('bypassEnhancing', document.getElementById('bypassEnhanceToggle')?.checked || false);
    
    if (action === 'to outpaint') {
        formData.append('op_left', document.getElementById('opLeft').value || 0);
        formData.append('op_right', document.getElementById('opRight').value || 0);
        formData.append('op_top', document.getElementById('opTop').value || 0);
        formData.append('op_bottom', document.getElementById('opBottom').value || 0);
    }

    if (attachedRawFiles && attachedRawFiles.length > 0 && overridePrompt === null) {
        attachedRawFiles.forEach(f => formData.append('file', f));
        sessionFileCache[prompt.trim()] = attachedRawFiles[0];
    } else if (attachedRawFile && overridePrompt === null) { 
        formData.append('file', attachedRawFile);
        sessionFileCache[prompt.trim()] = attachedRawFile;
    } else if (overrideFile !== null) {
        formData.append('file', overrideFile);
    }

    let ephemeralHtml = "";
    if (overridePrompt !== null) {
        let displayPrompt = prompt;
        const fileIdx = displayPrompt.indexOf('\n\n[File Content]:');
        if(fileIdx !== -1) displayPrompt = displayPrompt.substring(0, fileIdx);
        const audioIdx = displayPrompt.indexOf('\n\n[Detected Audio Types]:');
        if(audioIdx !== -1) displayPrompt = displayPrompt.substring(0, audioIdx);
        const transcriptIdx = displayPrompt.indexOf('\n\n[Speech Transcript]:');
        if(transcriptIdx !== -1) displayPrompt = displayPrompt.substring(0, transcriptIdx);
        displayPrompt = displayPrompt.replace(/^\[.*? Request\]\n/, ''); 
        
        ephemeralHtml = displayPrompt.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        if(action !== 'analyze') {
            ephemeralHtml = `<span style="color:var(--bg-main); font-weight:bold; font-size:13px; background:rgba(255,255,255, 0.2); padding: 4px 8px; border-radius: 6px;"><i class="fas fa-magic"></i> Action: ${action.toUpperCase()}</span><br><br>` + ephemeralHtml;
        }

        if(prompt.includes('[File Content]:') || prompt.includes('[Speech Transcript]:') || prompt.includes('[Detected Audio Types]:')) {
            ephemeralHtml += `<br><div class="file-pill"><i class="fas fa-paperclip"></i> ${t('attached_doc_restored')}</div>`;
        }
        
        const imgRegex = /!\[(.*?)\]\((data:image\/[^)]+)\)/g;
        let match;
        while ((match = imgRegex.exec(prompt)) !== null) {
            ephemeralHtml += `<br><div class="file-pill"><i class="fas fa-image"></i> ${match[1] || 'Image'}</div>`;
        }
    } else {
        ephemeralHtml = prompt.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        if(action !== 'analyze') {
            ephemeralHtml = `<span style="color:var(--bg-main); font-weight:bold; font-size:13px; background:rgba(255,255,255, 0.2); padding: 4px 8px; border-radius: 6px;"><i class="fas fa-magic"></i> Action: ${action.toUpperCase()}</span><br><br>` + ephemeralHtml;
        }

        if (attachedRawFile) {
            if (frontendImageBase64) {
                ephemeralHtml += `<br><div class="file-pill"><i class="fas fa-image"></i> ${attachedRawFile.name}</div>`;
            } else if (frontendTextContent) {
                ephemeralHtml += `<br><div class="file-pill"><i class="fas fa-file-alt"></i> ${attachedRawFile.name}</div>`;
            } else {
                ephemeralHtml += `<br><div class="file-pill"><i class="fas fa-paperclip"></i> ${attachedRawFile.name}</div>`;
            }
            attachedRawFile = null;
            removeAttachment();
        }
    }

    const chatWindow = document.getElementById('chatWindow');
    if (chatWindow.innerHTML.includes(t('welcome_message'))) chatWindow.innerHTML = '';

    isGenerating = true;
    document.getElementById('sendBtn').style.display = 'none';
    document.getElementById('cancelBtn').style.display = 'block';
    
    input.value = '';
    input.style.height = '44px';
    input.style.overflowY = 'hidden';

    const userWrapper = document.createElement('div');
    userWrapper.className = 'message-wrapper user';
    userWrapper.innerHTML = `<div class="message user-msg" style="white-space: pre-wrap;">${ephemeralHtml}</div>`;
    chatWindow.appendChild(userWrapper);

    let streamChatId = currentChatId || 'temp_' + Date.now();
    activeGenerations[streamChatId] = {
        fullText: "",
        statusLogs: [],
        isDone: false
    };

    const botWrapper = document.createElement('div');
    botWrapper.className = 'message-wrapper bot';
    const botMsgDiv = document.createElement('div');
    botMsgDiv.className = 'message bot-msg';
    botMsgDiv.id = `live-stream-${streamChatId}`;
    botWrapper.appendChild(botMsgDiv);
    chatWindow.appendChild(botWrapper);
    
    currentAbortController = new AbortController();

    let statusLogs = activeGenerations[streamChatId].statusLogs;
    renderStreamingMessage(botMsgDiv, "", statusLogs);

    try {
        const res = await fetch('/api/generate_stream', { method: 'POST', body: formData, signal: currentAbortController.signal });
        
        if (res.status === 429) {
            const data = await res.json();
            showToast(data.message, 'warning');
            botWrapper.remove();
            isGenerating = false;
            document.getElementById('sendBtn').style.display = 'block';
            document.getElementById('cancelBtn').style.display = 'none';
            return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            if (!isGenerating) break; 
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.toString().split(/\r?\n/);                
            buffer = lines.pop(); 

            for (let line of lines) {
                line = line.trim();
                if (line.startsWith('data: ')) {
                    const dataStr = line.substring(6).trim();
                    if (dataStr === '[DONE]') continue; 
                    if (!dataStr) continue;
                    try {
                        const data = JSON.parse(dataStr);
                        if (data.chat_id) { 
                            const oldKey = streamChatId;
                            currentChatId = data.chat_id;
                            streamChatId = data.chat_id;
                            
                            if (oldKey !== streamChatId && activeGenerations[oldKey]) {
                                activeGenerations[streamChatId] = activeGenerations[oldKey];
                                delete activeGenerations[oldKey];
                            }
                            if (botMsgDiv) botMsgDiv.id = `live-stream-${streamChatId}`;
                            loadChats(); 
                        }
                        
                        const targetEl = document.getElementById(`live-stream-${streamChatId}`) || botMsgDiv;

                        if (data.status) {
                            const logs = activeGenerations[streamChatId].statusLogs;
                            if (data.status.includes("ComfyUI rendering...") && logs.length > 0 && logs[logs.length - 1].includes("ComfyUI rendering...")) {
                                logs[logs.length - 1] = data.status;
                            } else {
                                logs.push(data.status);
                            }
                            
                            if (document.body.contains(targetEl)) {
                                renderStreamingMessage(targetEl, activeGenerations[streamChatId].fullText, logs);
                            }
                        }
                        if (data.chunk) { 
                            activeGenerations[streamChatId].fullText += data.chunk; 
                            if (document.body.contains(targetEl)) {
                                renderStreamingMessage(targetEl, activeGenerations[streamChatId].fullText, activeGenerations[streamChatId].statusLogs);
                            }
                        }
                        if (data.title_update) { loadChats(); }
                        if (data.error) { 
                            activeGenerations[streamChatId].statusLogs.push("❌ Error: " + data.error);
                            if (document.body.contains(targetEl)) {
                                renderStreamingMessage(targetEl, activeGenerations[streamChatId].fullText, activeGenerations[streamChatId].statusLogs);
                            }
                        }
                    } catch (e) {}
                }
            }
        }
    } catch (err) {
        const targetEl = document.getElementById(`live-stream-${streamChatId}`) || botMsgDiv;
        if (err.name === 'AbortError') {
            if (activeGenerations[streamChatId]) {
                activeGenerations[streamChatId].statusLogs.push(`⚠️ ${t('action_canceled')}`);
                activeGenerations[streamChatId].fullText += "\n\n*[Action canceled]*";
            }
            if (document.body.contains(targetEl)) {
                renderStreamingMessage(targetEl, activeGenerations[streamChatId].fullText, activeGenerations[streamChatId].statusLogs);
            }
        } else {
            if (activeGenerations[streamChatId]) {
                activeGenerations[streamChatId].statusLogs.push(t('processing_bg'));
            }
            if (document.body.contains(targetEl)) {
                renderStreamingMessage(targetEl, activeGenerations[streamChatId].fullText, activeGenerations[streamChatId].statusLogs);
            }
        }
    } finally {
        isGenerating = false;
        if (activeGenerations[streamChatId]) {
            activeGenerations[streamChatId].isDone = true;
        }
        document.getElementById('sendBtn').style.display = 'block';
        document.getElementById('cancelBtn').style.display = 'none';
        if (currentChatId) loadChatHistory(currentChatId);
    }
}
