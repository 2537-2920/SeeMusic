let isLoginMode = true;

function toggleMode() {
    isLoginMode = !isLoginMode;
    
    const title = document.getElementById('page-title');
    const subtitle = document.getElementById('page-subtitle');
    const confirmPass = document.getElementById('confirm-password-container');
    const submitText = document.getElementById('submit-text');
    const switchText = document.getElementById('switch-text');
    const switchIcon = document.querySelector('#switch-mode-btn iconify-icon');
    const submitIcon = document.querySelector('#submit-btn iconify-icon');

    if (isLoginMode) {
        title.innerText = '欢迎回来';
        subtitle.innerText = '让灵感在五线谱上自由流淌';
        confirmPass.classList.add('hidden-section');
        submitText.innerText = '立即登录';
        switchText.innerText = '创建新账号';
        switchIcon.setAttribute('icon', 'solar:user-plus-bold-duotone');
        submitIcon.setAttribute('icon', 'solar:login-3-bold-duotone');
    } else {
        title.innerText = '加入 SeeMusic';
        subtitle.innerText = '开启您的智能音乐创作之旅';
        confirmPass.classList.remove('hidden-section');
        submitText.innerText = '注册账号';
        switchText.innerText = '已有账号？登录';
        switchIcon.setAttribute('icon', 'solar:login-3-bold-duotone');
        submitIcon.setAttribute('icon', 'solar:user-plus-bold-duotone');
    }
}

function initMode() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('mode') === 'register') {
        toggleMode();
    }
}

// 添加表单提交事件，模拟登录成功后跳转回主页
document.getElementById('auth-form').addEventListener('submit', function(e) {
    e.preventDefault(); // 阻止页面刷新
    const submitBtn = document.getElementById('submit-btn');
    const submitText = document.getElementById('submit-text');
    
    // 按钮变成加载状态
    submitText.innerText = '验证中...';
    submitBtn.style.opacity = '0.7';
    submitBtn.disabled = true;
    
    // 模拟 1 秒后登录成功，跳转回 index.html，并带上参数
    setTimeout(() => {
        window.location.href = 'index.html?logged_in=true';
    }, 1000);
});

// 初始化背景装饰元素
function createDecorations() {
    const container = document.getElementById('decoration-container');
    const notes = ['solar:music-note-bold', 'solar:music-note-2-bold', 'solar:music-note-3-bold', 'solar:music-notes-bold'];
    const markings = ['p', 'f', 'ff', 'mf', 'pp', 'fz'];

    for (let i = 0; i < 15; i++) {
        const el = document.createElement('div');
        el.className = 'floating-note';
        
        if (Math.random() > 0.4) {
            const icon = document.createElement('iconify-icon');
            icon.setAttribute('icon', notes[Math.floor(Math.random() * notes.length)]);
            icon.style.fontSize = Math.random() * 20 + 20 + 'px';
            icon.style.color = '#457b9d';
            el.appendChild(icon);
        } else {
            el.innerText = markings[Math.floor(Math.random() * markings.length)];
            el.style.fontFamily = 'serif';
            el.style.fontSize = Math.random() * 20 + 15 + 'px';
            el.style.fontWeight = 'bold';
            el.style.fontStyle = 'italic';
            el.style.color = '#1d3557';
        }

        el.style.left = (Math.random() * 100) + '%';
        el.style.top = (Math.random() * 100) + '%';
        el.style.animationDelay = (Math.random() * 5) + 's';
        el.style.opacity = '0.3';
        
        container.appendChild(el);
    }
}

window.addEventListener('load', () => {
    createDecorations();
    initMode();
});