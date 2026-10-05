function changeAccentColor(colorId) {
    currentAccentColor = colorId;
    localStorage.setItem('heater_accent_color', colorId);
    
    const root = document.documentElement;
    root.style.setProperty('--accent', accentColors[colorId].main);
    root.style.setProperty('--accent-hover', accentColors[colorId].hover);
    root.style.setProperty('--accent-light', accentColors[colorId].light);
}

function hexToRgb(hex) {
    let r = parseInt(hex.slice(1, 3), 16),
        g = parseInt(hex.slice(3, 5), 16),
        b = parseInt(hex.slice(5, 7), 16);
    return `${r}, ${g}, ${b}`;
}

function initCanvasBg() {
    canvas = document.getElementById('bgCanvas');
    if (!canvas) return;
    ctx = canvas.getContext('2d');
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    particles = [];
    let numParticles = (window.innerWidth * window.innerHeight) / 25000;
    for (let i = 0; i < numParticles; i++) {
        particles.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            vx: (Math.random() - 0.5) * 0.5,
            vy: (Math.random() - 0.5) * 0.5,
            size: Math.random() * 2 + 1
        });
    }
    animateCanvas();
}

function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}

function changeCanvasTheme(theme) {
    currentCanvasTheme = theme;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    if (theme === 'xp_bezier') {
        bezierLines = [];
        for (let i = 0; i < 4; i++) {
            let line = { points: [], hue: Math.random() * 360 };
            for (let j = 0; j < 4; j++) {
                line.points.push({
                    x: Math.random() * canvas.width,
                    y: Math.random() * canvas.height,
                    vx: (Math.random() - 0.5) * 6,
                    vy: (Math.random() - 0.5) * 6
                });
            }
            bezierLines.push(line);
        }
    } else if (theme === 'particles') {
        initCanvasBg();
    }
}

function animateCanvas() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

    if (currentCanvasTheme === 'particles') {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const rgbStr = hexToRgb(accentColors[currentAccentColor].main);
        const pColor = `rgba(${rgbStr}, 0.75)`;
        const lColor = `rgba(${rgbStr}, 0.35)`;

        for (let i = 0; i < particles.length; i++) {
            let p = particles[i];
            p.x += p.vx; p.y += p.vy;

            if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
            if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fillStyle = pColor; ctx.fill();

            for (let j = i + 1; j < particles.length; j++) {
                let p2 = particles[j];
                let dist = Math.hypot(p.x - p2.x, p.y - p2.y);
                if (dist < 120) {
                    ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p2.x, p2.y);
                    ctx.strokeStyle = lColor; ctx.lineWidth = 1.0; ctx.stroke();
                }
            }
        }
    } 
    else if (currentCanvasTheme === 'xp_bezier') {
        ctx.fillStyle = isDark ? 'rgba(15, 23, 42, 0.12)' : 'rgba(248, 250, 252, 0.12)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        bezierLines.forEach(line => {
            line.hue = (line.hue + 0.8) % 360;
            ctx.beginPath();
            ctx.moveTo(line.points[0].x, line.points[0].y);
            ctx.bezierCurveTo(
                line.points[1].x, line.points[1].y,
                line.points[2].x, line.points[2].y,
                line.points[3].x, line.points[3].y
            );
            ctx.strokeStyle = `hsl(${line.hue}, 100%, 65%)`;
            ctx.lineWidth = 2.5;
            ctx.stroke();

            line.points.forEach(p => {
                p.x += p.vx; p.y += p.vy;
                if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
                if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
            });
        });
    }
    else if (currentCanvasTheme === 'waves') {
        ctx.fillStyle = isDark ? 'rgba(15, 23, 42, 0.1)' : 'rgba(248, 250, 252, 0.1)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        waveTime += 0.015;

        for (let i = 0; i < 4; i++) {
            ctx.beginPath();
            for (let x = 0; x <= canvas.width; x += 30) {
                let y = canvas.height / 2 + Math.sin(x * 0.005 + waveTime + i * 0.5) * 180 * Math.sin(waveTime * 0.8);
                if (x === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.strokeStyle = `hsl(${(waveTime * 100 + i * 60) % 360}, 100%, 65%)`;
            ctx.lineWidth = 2;
            ctx.stroke();
        }
    }
    requestAnimationFrame(animateCanvas);
}

function changeUITheme(theme) {
    currentUITheme = theme;
    localStorage.setItem('heater_ui_theme', theme);
    document.documentElement.setAttribute('data-ui-theme', theme);
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const icon = document.getElementById('themeIcon');
    if(icon) {
        if(theme === 'dark') {
            icon.classList.remove('fa-moon');
            icon.classList.add('fa-sun');
        } else {
            icon.classList.remove('fa-sun');
            icon.classList.add('fa-moon');
        }
    }
}

function toggleTheme() {
    currentTheme = currentTheme === 'light' ? 'dark' : 'light';
    localStorage.setItem('heater_theme', currentTheme);
    applyTheme(currentTheme);
}
