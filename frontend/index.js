const container = document.getElementById('decoration-container');
const notes = ['solar:music-note-bold', 'solar:music-note-2-bold', 'solar:music-note-3-bold', 'solar:music-notes-bold'];
const markings = ['p', 'f', 'ff', 'mf', 'pp', 'mf'];

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

        // 中心避让算法
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

function toggleLogin(isLoggedIn) {
    const outView = document.getElementById('logged-out-view');
    const inView = document.getElementById('logged-in-view');
    const btnIn = document.getElementById('btn-mock-in');
    const btnOut = document.getElementById('btn-mock-out');

    if (isLoggedIn) {
        outView.classList.add('state-hidden');
        outView.classList.remove('state-active');
        inView.classList.add('state-active');
        inView.classList.remove('state-hidden');
        btnIn.className = 'px-4 py-2 rounded-lg bg-[#457b9d] text-white text-xs transition-all ring-2 ring-blue-100';
        btnOut.className = 'px-4 py-2 rounded-lg bg-white text-gray-600 text-xs hover:bg-gray-50 transition-all border border-gray-100';
    } else {
        inView.classList.add('state-hidden');
        inView.classList.remove('state-active');
        outView.classList.add('state-active');
        outView.classList.remove('state-hidden');
        btnOut.className = 'px-4 py-2 rounded-lg bg-[#457b9d] text-white text-xs transition-all ring-2 ring-blue-100';
        btnIn.className = 'px-4 py-2 rounded-lg bg-white text-gray-600 text-xs hover:bg-gray-50 transition-all border border-gray-100';
    }
}

// 检查 URL 中是否有 logged_in=true，如果有则直接展示登录状态
function checkLoginState() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('logged_in') === 'true') {
        toggleLogin(true);
    }
}

window.addEventListener('load', () => {
    createDecorations();
    checkLoginState();
});