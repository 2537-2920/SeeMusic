let isLoginMode = true;

const {
    requestJson,
    setAuthSession,
    clearAuthSession,
    getCurrentUser,
} = window.SeeMusicApp;

function setStatus(message, isError = false) {
    const status = document.getElementById("auth-status");
    if (!message) {
        status.classList.add("hidden");
        status.textContent = "";
        status.className = "hidden text-xs rounded-xl px-4 py-3";
        return;
    }
    status.textContent = message;
    status.className = `text-xs rounded-xl px-4 py-3 ${isError ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-700"}`;
}

function toggleMode() {
    isLoginMode = !isLoginMode;

    const title = document.getElementById("page-title");
    const subtitle = document.getElementById("page-subtitle");
    const emailContainer = document.getElementById("email-container");
    const confirmPass = document.getElementById("confirm-password-container");
    const submitText = document.getElementById("submit-text");
    const switchText = document.getElementById("switch-text");
    const switchIcon = document.querySelector("#switch-mode-btn iconify-icon");
    const submitIcon = document.querySelector("#submit-btn iconify-icon");

    if (isLoginMode) {
        title.innerText = "欢迎回来";
        subtitle.innerText = "让灵感在五线谱上自由流淌";
        emailContainer.classList.add("hidden-section");
        confirmPass.classList.add("hidden-section");
        submitText.innerText = "立即登录";
        switchText.innerText = "创建新账号";
        switchIcon.setAttribute("icon", "solar:user-plus-bold-duotone");
        submitIcon.setAttribute("icon", "solar:login-3-bold-duotone");
    } else {
        title.innerText = "加入 SeeMusic";
        subtitle.innerText = "开启您的智能音乐创作之旅";
        emailContainer.classList.remove("hidden-section");
        confirmPass.classList.remove("hidden-section");
        submitText.innerText = "注册账号";
        switchText.innerText = "已有账号？登录";
        switchIcon.setAttribute("icon", "solar:login-3-bold-duotone");
        submitIcon.setAttribute("icon", "solar:user-plus-bold-duotone");
    }
    setStatus("");
}

function initMode() {
    const urlParams = new URLSearchParams(window.location.search);
    const currentUser = getCurrentUser();
    if (currentUser && !urlParams.has("mode")) {
        setStatus(`当前已登录：${currentUser.username}。继续操作会覆盖本地登录状态。`);
    }
    if (urlParams.get("mode") === "register") {
        toggleMode();
    }
}

document.getElementById('auth-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const submitBtn = document.getElementById('submit-btn');
    const submitText = document.getElementById('submit-text');
    
    // 【关键修改】在修改按钮文字之前，先记录当前的模式
    // 我们假设你的按钮里有一个能区分登录/注册的状态，或者通过是否存在 confirm-password 输入框来判断
    const confirmInput = document.getElementById('confirm-password');
    const isLogin = !confirmInput || confirmInput.offsetParent === null; // 如果没有确认密码框，或者框被隐藏了，就是登录模式
    
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();
    const confirmPassword = confirmInput ? confirmInput.value.trim() : "";

    submitText.innerText = '验证中...';
    submitBtn.disabled = true;

    try {
        let response;
        if (isLogin) {
            // ✅ 登录逻辑
            response = await fetch("http://127.0.0.1:8000/api/v1/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password })
            });
        } else {
            // ✅ 注册逻辑
            if (password !== confirmPassword) {
                alert("两次密码不一致！");
                // 恢复按钮状态，否则用户无法再次点击
                submitText.innerText = '注册账号'; 
                submitBtn.disabled = false;
                return;
            }
            response = await fetch("http://127.0.0.1:8000/api/v1/auth/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password })
            });
        }

        if (response.ok) {
            alert(isLogin ? "登录成功！" : "注册成功！");
            localStorage.setItem('seeMusic_isLoggedIn', 'true');
            window.location.href = 'index.html';
        } else {
            alert("验证失败，请检查账号密码！");
        }
    } catch (error) {
        alert("后端服务未启动或接口报错！");
    } finally {
        submitText.innerText = isLogin ? '立即登录' : '注册账号';
        submitBtn.disabled = false;
    }
});
function createDecorations() {
    const container = document.getElementById("decoration-container");
    const notes = ["solar:music-note-bold", "solar:music-note-2-bold", "solar:music-note-3-bold", "solar:music-notes-bold"];
    const markings = ["p", "f", "ff", "mf", "pp", "mf"];

    for (let i = 0; i < 15; i += 1) {
        const el = document.createElement("div");
        el.className = "floating-note";

        if (Math.random() > 0.4) {
            const icon = document.createElement("iconify-icon");
            icon.setAttribute("icon", notes[Math.floor(Math.random() * notes.length)]);
            icon.style.fontSize = `${Math.random() * 20 + 20}px`;
            icon.style.color = "#457b9d";
            el.appendChild(icon);
        } else {
            el.innerText = markings[Math.floor(Math.random() * markings.length)];
            el.style.fontFamily = "serif";
            el.style.fontSize = `${Math.random() * 20 + 15}px`;
            el.style.fontWeight = "bold";
            el.style.fontStyle = "italic";
            el.style.color = "#1d3557";
        }

        el.style.left = `${Math.random() * 100}%`;
        el.style.top = `${Math.random() * 100}%`;
        el.style.animationDelay = `${Math.random() * 5}s`;
        el.style.opacity = "0.3";
        container.appendChild(el);
    }
}

document.getElementById("auth-form").addEventListener("submit", handleSubmit);

window.addEventListener("load", () => {
    createDecorations();
    initMode();
});
