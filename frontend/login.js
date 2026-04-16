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

document.getElementById('auth-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const submitBtn = document.getElementById('submit-btn');
    const submitText = document.getElementById('submit-text');
    
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();
    const confirmPassword = document.getElementById('confirm-password')?.value?.trim();

    submitText.innerText = '验证中...';
    submitBtn.disabled = true;

    try {
        const isLogin = submitText.innerText.includes('登录');
        let response;

        if (isLogin) {
            // ✅ 调用后端登录接口
            response = await fetch("http://127.0.0.1:8000/api/v1/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password })
            });
        } else {
            // ✅ 调用后端注册接口
            if (password !== confirmPassword) {
                alert("两次密码不一致！");
                return;
            }
            response = await fetch("http://127.0.0.1:8000/api/v1/auth/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password })
            });
        }

        if (response.ok) {
            const data = await response.json();
            alert(isLogin ? "登录成功！" : "注册成功！");
            localStorage.setItem('seeMusic_isLoggedIn', 'true');
            window.location.href = 'index.html';
        } else {
            alert("验证失败，请检查账号密码！");
        }
    } catch (error) {
        alert("后端服务未启动,请先启动Python后端!");
    } finally {
        // 恢复按钮
        submitText.innerText = isLogin ? '立即登录' : '注册账号';
        submitBtn.disabled = false;
    }
});

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