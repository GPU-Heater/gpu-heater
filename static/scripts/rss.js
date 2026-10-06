function openDataManagementModal() {
    const modelMenu = document.getElementById('modelSettingsMenu');
    if (modelMenu) modelMenu.classList.remove('show');
    document.getElementById('dmFileUpload').accept += ',.jpg,.jpeg,.png,.webp';
    document.getElementById('dataManagementModal').style.display = 'flex';
    applyTranslations();
    switchDmTab('file');
}

function switchDmTab(tab) {
    document.querySelectorAll('.dm-tab-content').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.dm-tab-btn').forEach(el => el.classList.remove('active'));
    
    document.getElementById(`dm-tab-${tab}`).style.display = 'block';
    document.getElementById(`tab-btn-${tab}`).classList.add('active');

    if (tab === 'file' || tab === 'url') {
        loadKnowledgeBaseData();
    } else if (tab === 'rss') {
        loadRssFeeds();
        loadRssArchive();
    }
}

async function loadKnowledgeBaseData() {
    try {
        const res = await fetch('/api/kb/sources');
        const data = await res.json();
        if (data.success) {
            kbFilesData = data.sources.filter(s => !s.startsWith('http') && !s.startsWith('RSS_'));
            kbUrlsData = data.sources.filter(s => s.startsWith('http') && !s.startsWith('RSS_'));
            
            kbFilesFiltered = [...kbFilesData];
            kbUrlsFiltered = [...kbUrlsData];
            
            kbFilesPage = 1;
            kbUrlsPage = 1;
            
            renderKbFilesList();
            renderKbUrlsList();
        }
    } catch(e) { 
        console.error("KB Load Error:", e); 
    }
}

function handleKbFileSearch() {
    const query = (document.getElementById('dmFileSearchInput').value || '').toLowerCase().trim();
    kbFilesFiltered = kbFilesData.filter(item => item.toLowerCase().includes(query));
    kbFilesPage = 1;
    renderKbFilesList();
}

function changeKbFilePage(direction) {
    const totalPages = Math.ceil(kbFilesFiltered.length / KB_PAGE_SIZE) || 1;
    const newPage = kbFilesPage + direction;
    if (newPage >= 1 && newPage <= totalPages) {
        kbFilesPage = newPage;
        renderKbFilesList();
    }
}

function renderKbFilesList() {
    renderPaginatedKbList({
        containerId: 'dmFileList',
        items: kbFilesFiltered,
        page: kbFilesPage,
        indicatorId: 'dmFilePageIndicator',
        prevBtnId: 'dmFilePrevBtn',
        nextBtnId: 'dmFileNextBtn',
        type: 'file'
    });
}

function handleKbUrlSearch() {
    const query = (document.getElementById('dmUrlSearchInput').value || '').toLowerCase().trim();
    kbUrlsFiltered = kbUrlsData.filter(item => item.toLowerCase().includes(query));
    kbUrlsPage = 1;
    renderKbUrlsList();
}

function changeKbUrlPage(direction) {
    const totalPages = Math.ceil(kbUrlsFiltered.length / KB_PAGE_SIZE) || 1;
    const newPage = kbUrlsPage + direction;
    if (newPage >= 1 && newPage <= totalPages) {
        kbUrlsPage = newPage;
        renderKbUrlsList();
    }
}

function renderKbUrlsList() {
    renderPaginatedKbList({
        containerId: 'dmUrlList',
        items: kbUrlsFiltered,
        page: kbUrlsPage,
        indicatorId: 'dmUrlPageIndicator',
        prevBtnId: 'dmUrlPrevBtn',
        nextBtnId: 'dmUrlNextBtn',
        type: 'url'
    });
}

function renderPaginatedKbList({ containerId, items, page, indicatorId, prevBtnId, nextBtnId, type }) {
    const list = document.getElementById(containerId);
    list.innerHTML = '';
    
    const totalItems = items.length;
    const totalPages = Math.ceil(totalItems / KB_PAGE_SIZE) || 1;
    const currentPage = Math.min(page, totalPages);
    
    const startIndex = (currentPage - 1) * KB_PAGE_SIZE;
    const pageItems = items.slice(startIndex, startIndex + KB_PAGE_SIZE);

    if (pageItems.length === 0) {
        list.innerHTML = `<div style="text-align:center; opacity:0.5; font-size:12px; padding: 15px;">${t('dm_no_data')}</div>`;
    } else {
        pageItems.forEach(item => {
            list.innerHTML += `
                <div class="dm-list-item">
                    <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:75%;" title="${item}">
                        <i class="fas ${type === 'url' ? 'fa-link' : 'fa-file'}"></i> ${item}
                    </span>
                    <div class="dm-list-actions">
                        <button class="btn-secondary btn-compact" onclick="viewKbSource('${item}')"><i class="fas fa-eye"></i></button>
                        <button class="btn-secondary btn-compact" style="color:var(--danger);" onclick="deleteKbSource('${item}')"><i class="fas fa-trash"></i></button>
                    </div>
                </div>
            `;
        });
    }

    const indicator = document.getElementById(indicatorId);
    if (indicator) indicator.innerText = `${currentPage} / ${totalPages} (${totalItems})`;

    const prevBtn = document.getElementById(prevBtnId);
    if (prevBtn) {
        prevBtn.disabled = (currentPage <= 1);
        prevBtn.style.opacity = (currentPage <= 1) ? '0.3' : '1';
    }

    const nextBtn = document.getElementById(nextBtnId);
    if (nextBtn) {
        nextBtn.disabled = (currentPage >= totalPages);
        nextBtn.style.opacity = (currentPage >= totalPages) ? '0.3' : '1';
    }
}

async function handleDmFileUpload(input) {
    const file = input.files[0];
    if(!file) return;
    showToast(t('toast_training'), "warning");
    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch('/api/train_document', { method: 'POST', body: formData });
        const data = await res.json();
        if(data.success) { 
            showToast(data.message || t('toast_process_success'), "success"); 
            loadKnowledgeBaseData(); 
        } else { 
            showToast(data.error || t('toast_train_error'), "warning"); 
        }
    } catch(e) { showToast(t('toast_train_error'), "warning"); }
    input.value = '';
}

async function handleDmUrlTrain() {
    const url = document.getElementById('dmUrlInput').value;
    if(!url) return;
    document.getElementById('dmUrlInput').value = '';
    showToast(t('toast_training'), "warning");
    try {
        const res = await fetch('/api/train_url', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({url: url}) });
        const data = await res.json();
        if(data.success) { 
            showToast(t('toast_process_success'), "success"); 
            loadKnowledgeBaseData(); 
        } else { 
            showToast(t('toast_train_error'), "warning"); 
        }
    } catch(e) { showToast(t('toast_conn_error'), "warning"); }
}

async function deleteKbSource(source) {
    const confirmMsg = `${t('dm_confirm_delete')} ${source}?`;
    if(!confirm(confirmMsg)) return;
    try {
        await fetch('/api/kb/source', { method: 'DELETE', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({source: source}) });
        loadKnowledgeBaseData();
    } catch(e) {}
}

async function viewKbSource(source) {
    document.getElementById('viewContentTitle').innerHTML = `<i class="fas fa-eye"></i> ${source}`;
    document.getElementById('viewContentBody').innerText = "...";
    document.getElementById('viewContentModal').style.display = 'flex';
    try {
        const res = await fetch('/api/kb/source/view', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({source: source}) });
        const data = await res.json();
        if(data.success) document.getElementById('viewContentBody').innerText = data.content || t('dm_no_data');
        else document.getElementById('viewContentBody').innerText = t('btn_error');
    } catch(e) { document.getElementById('viewContentBody').innerText = t('toast_conn_error'); }
}

async function loadRssFeeds() {
    const list = document.getElementById('rssFeedList');
    list.innerHTML = '<div style="text-align:center; opacity:0.5;"><i class="fas fa-spinner fa-spin"></i></div>';
    try {
        const res = await fetch('/api/rss');
        const data = await res.json();
        list.innerHTML = '';
        if(data.length === 0) {
            list.innerHTML = `<div style="padding:10px; opacity:0.5; font-size:12px; text-align:center;">${t('rss_no_data')}</div>`;
            return;
        }
        data.forEach(feed => {
            const el = document.createElement('div');
            el.style.display = 'flex';
            el.style.justifyContent = 'space-between';
            el.style.alignItems = 'center';
            el.style.padding = '5px';
            el.style.borderBottom = '1px solid var(--border)';
            el.style.fontSize = '12px';
            
            el.innerHTML = `
                <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:80%;" title="${feed.url}">${feed.url}</span>
                <button onclick="deleteRssFeed(${feed.id})" style="background:none; border:none; color:var(--danger); cursor:pointer;"><i class="fas fa-trash"></i></button>
            `;
            list.appendChild(el);
        });
    } catch(e) {}
}

async function addRssFeed() {
    const url = document.getElementById('dmRssInput').value;
    if(!url) return;
    try {
        await fetch('/api/rss', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({url: url}) });
        document.getElementById('dmRssInput').value = '';
        loadRssFeeds();
    } catch(e) {}
}

async function deleteRssFeed(id) {
    try {
        await fetch(`/api/rss/${id}`, { method: 'DELETE' });
        loadRssFeeds();
    } catch(e) {}
}

async function loadRssArchive() {
    rssCurrentPage = 1;
    try {
        const res = await fetch('/api/rss/archive');
        const data = await res.json();
        if (data.success) {
            rssArchiveData = data.data || [];
            rssFilteredData = [...rssArchiveData];
            renderRssArchive();
        }
    } catch (e) {}
}

async function deleteRssArchiveItem(id, link) {
    const confirmMsg = `${t('dm_confirm_delete')} this article?`;
    if(!confirm(confirmMsg)) return;
    try {
        await fetch(`/api/rss/archive/${id}`, { method: 'DELETE' });
        await fetch('/api/kb/source', { method: 'DELETE', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({source: `RSS_${link}`}) });
        loadRssArchive();
    } catch(e) {}
}

function changeRssPage(direction) {
    const totalPages = Math.ceil(rssFilteredData.length / RSS_PAGE_SIZE) || 1;
    const newPage = rssCurrentPage + direction;
    if (newPage >= 1 && newPage <= totalPages) {
        rssCurrentPage = newPage;
        renderRssArchive();
    }
}

function renderRssArchive() {
    const list = document.getElementById('rssArchiveList');
    list.innerHTML = '';
    const totalItems = rssFilteredData.length;
    const totalPages = Math.ceil(totalItems / RSS_PAGE_SIZE) || 1;
    if (rssCurrentPage > totalPages) rssCurrentPage = totalPages;
    const startIndex = (rssCurrentPage - 1) * RSS_PAGE_SIZE;
    const pageItems = rssFilteredData.slice(startIndex, startIndex + RSS_PAGE_SIZE);

    if (pageItems.length === 0) {
        list.innerHTML = `<div style="text-align:center; padding:15px; opacity:0.6; font-size:12px;">${t('rss_no_data')}</div>`;
    } else {
        pageItems.forEach(item => {
            const div = document.createElement('div');
            div.style.cssText = "background:var(--bg-panel); padding:12px; border-radius:6px; border:1px solid var(--border);";
            div.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">
                    <a href="${item.link}" target="_blank" style="color:var(--accent); font-weight:600; font-size:13px; text-decoration:none;">
                        ${item.title || 'Untitled'}
                    </a>
                    <div style="display:flex; gap: 5px;">
                        <button class="btn-secondary btn-compact" onclick="viewKbSource('RSS_${item.link}')"><i class="fas fa-eye"></i></button>
                        <button class="btn-secondary btn-compact" style="color:var(--danger);" onclick="deleteRssArchiveItem(${item.id}, '${item.link}')"><i class="fas fa-trash"></i></button>
                    </div>
                </div>
                <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px;">${item.source || t('rss_unknown_source')}</div>
                <div style="font-size:12px; color:var(--text-main); opacity:0.8;">${item.summary || ''}</div>
            `;
            list.appendChild(div);
        });
    }
    document.getElementById('rssPageIndicator').innerText = `${rssCurrentPage} / ${totalPages} (${totalItems})`;
}