(function() {
    const scripts = [
        '/static/js/highlight.min.js',
        '/static/js/marked.min.js',
        '/static/js/mermaid.min.js',
        '/static/scripts/globals.js',
        '/static/scripts/theme.js',
        '/static/scripts/rss.js',
        '/static/scripts/models.js',
        '/static/scripts/chat.js',
        '/static/scripts/app.js'
    ];

    function updatePreloader(statusText, percent) {
        const statusEl = document.getElementById('preloaderStatus');
        const progressEl = document.getElementById('preloaderProgressBar');
        if (progressEl && percent !== undefined) {
            progressEl.style.width = `${percent}%`;
        }
        if (statusEl && statusText) {
            statusEl.textContent = statusText;
        }
    }

    function hidePreloader() {
        const preloader = document.getElementById('appPreloader');
        if (preloader) {
            updatePreloader("Ready!", 100);
            setTimeout(() => {
                preloader.classList.add('loaded');
            }, 300);
        }
    }

    async function loadScriptsSequentially(index) {
        const totalSteps = scripts.length + 1;

        if (index >= scripts.length) {
            updatePreloader("Loading language pack & initializing...", 90);

            if (typeof mermaid !== 'undefined') {
                mermaid.initialize({ startOnLoad: false, theme: 'default', suppressErrorRendering: true });
            }

            if (typeof initApp === 'function') {
                try {
                    await initApp();
                } catch (e) {
                    console.error("Initialization error:", e);
                }
            }

            hidePreloader();
            return;
        }

        const fileName = scripts[index].split('/').pop();
        const currentPct = Math.round((index / totalSteps) * 100);
        updatePreloader(`Loading: ${fileName}`, currentPct);

        const scriptEl = document.createElement('script');
        scriptEl.src = scripts[index];
        scriptEl.onload = () => loadScriptsSequentially(index + 1);
        scriptEl.onerror = () => {
            console.error(`Script load error: ${scripts[index]}`);
            loadScriptsSequentially(index + 1);
        };
        document.body.appendChild(scriptEl);
    }

    loadScriptsSequentially(0);
})();