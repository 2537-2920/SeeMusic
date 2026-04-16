const container = document.getElementById('decoration-container');
const notes = ['solar:music-note-bold', 'solar:music-note-2-bold', 'solar:music-note-3-bold', 'solar:music-notes-bold'];
const markings = ['p', 'f', 'ff', 'mf', 'pp', 'mf'];
const appCommon = window.SeeMusicApp || null;

function createDecorations() {
    for (let i = 0; i < 12; i++) {
        const el = document.createElement('div');
        el.className = 'floating-note';
        
        if (Math.random() > 0.4) {
            const icon = document.createElement('iconify-icon');
            icon.setAttribute('icon', notes[Math.floor(Math.random() * notes.length)]);
            icon.style.fontSize = Math.random() * 20 + 20 + 'px';
            icon.style.color = '#333333'; 
            el.appendChild(icon);
        } else {
            el.innerText = markings[Math.floor(Math.random() * markings.length)];
            el.style.fontFamily = 'serif';
            el.style.fontSize = Math.random() * 20 + 15 + 'px';
            el.style.fontWeight = 'bold';
            el.style.fontStyle = 'italic';
            el.style.color = '#000000';
        }

        let leftPercent = (i % 4 * 25 + Math.random() * 15);
        let topPercent = (Math.floor(i / 4) * 33 + Math.random() * 20);

        if(leftPercent > 20 && leftPercent < 80 && topPercent > 25 && topPercent < 75) {
            leftPercent = leftPercent < 50 ? Math.random() * 20 : 80 + Math.random() * 20;
        }

        el.style.left = leftPercent + '%';
        el.style.top = topPercent + '%';
        el.style.animationDelay = (Math.random() * 5) + 's';
        el.style.opacity = '0.3';
        
        container.appendChild(el);
    }
}

async function resolveServerLoginState() {
    if (!appCommon || !appCommon.getAuthToken || !appCommon.requestJson || !appCommon.clearAuthSession) {
        return false;
    }
    if (!appCommon.getAuthToken()) {
        return false;
    }
    try {
        await appCommon.requestJson('/users/me');
        return true;
    } catch {
        appCommon.clearAuthSession();
        return false;
    }
}

// 核心改动：从空白状态平滑入场
async function setupInitialView() {
    const outView = document.getElementById('logged-out-view');
    const inView = document.getElementById('logged-in-view');
    const btnIn = document.getElementById('btn-mock-in');
    const btnOut = document.getElementById('btn-mock-out');

    const isLoggedIn = await resolveServerLoginState();

    // 给浏览器 50 毫秒的时间确认当前是"空白隐藏"状态，然后再触发动画显示
    setTimeout(() => {
        if (isLoggedIn) {
            inView.classList.remove('state-hidden');
            inView.classList.add('state-active');
            updateMockButtons(true, btnIn, btnOut);
        } else {
            outView.classList.remove('state-hidden');
            outView.classList.add('state-active');
            updateMockButtons(false, btnIn, btnOut);
        }
    }, 50);
}

function toggleLogin(isLoggedIn) {
    if (appCommon && appCommon.clearAuthSession && appCommon.setAuthSession) {
        if (isLoggedIn) {
            appCommon.setAuthSession({
                token: 'demo-token',
                user: { user_id: 'demo', username: 'Demo User' },
            });
        } else {
            appCommon.clearAuthSession();
        }
    }
    const outView = document.getElementById('logged-out-view');
    const inView = document.getElementById('logged-in-view');
    const btnIn = document.getElementById('btn-mock-in');
    const btnOut = document.getElementById('btn-mock-out');

    if (isLoggedIn) {
        localStorage.setItem('seeMusic_isLoggedIn', 'true');
        outView.classList.add('state-hidden');
        outView.classList.remove('state-active');
        inView.classList.add('state-active');
        inView.classList.remove('state-hidden');
    } else {
        localStorage.removeItem('seeMusic_isLoggedIn');
        inView.classList.add('state-hidden');
        inView.classList.remove('state-active');
        outView.classList.add('state-active');
        outView.classList.remove('state-hidden');
    }
    updateMockButtons(isLoggedIn, btnIn, btnOut);
}

function updateMockButtons(isLoggedIn, btnIn, btnOut) {
    if (isLoggedIn) {
        btnIn.className = 'px-4 py-2 rounded-lg bg-[#457b9d] text-white text-xs transition-all ring-2 ring-blue-100';
        btnOut.className = 'px-4 py-2 rounded-lg bg-white text-gray-600 text-xs hover:bg-gray-50 transition-all border border-gray-100';
    } else {
        btnOut.className = 'px-4 py-2 rounded-lg bg-[#457b9d] text-white text-xs transition-all ring-2 ring-blue-100';
        btnIn.className = 'px-4 py-2 rounded-lg bg-white text-gray-600 text-xs hover:bg-gray-50 transition-all border border-gray-100';
    }
}

// 立即执行状态判定与动画触发
setupInitialView();

window.addEventListener('load', () => {
    createDecorations();
});