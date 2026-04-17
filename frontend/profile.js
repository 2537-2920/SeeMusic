const {
    requestJson,
    getCurrentUser,
    clearAuthSession,
    avatarUrl,
} = window.SeeMusicApp;

const profileState = {
    historyItems: [],
    visibleCount: 6, 
    currentFilter: "all"
};

function applyPreferencesToUI(prefs) {
    const engineSelect = document.getElementById("pref-audio-engine");
    if (engineSelect && prefs.audio_engine) {
        engineSelect.value = prefs.audio_engine;
    }
    const formatsContainer = document.getElementById("pref-export-formats");
    if (formatsContainer && Array.isArray(prefs.export_formats)) {
        formatsContainer.querySelectorAll("input[type=checkbox]").forEach((cb) => {
            cb.checked = prefs.export_formats.includes(cb.value);
        });
    }
}

function collectPreferencesFromUI() {
    const engineSelect = document.getElementById("pref-audio-engine");
    const formatsContainer = document.getElementById("pref-export-formats");
    const exportFormats = [];
    if (formatsContainer) {
        formatsContainer.querySelectorAll("input[type=checkbox]:checked").forEach((cb) => {
            exportFormats.push(cb.value);
        });
    }
    return {
        audio_engine: engineSelect ? engineSelect.value : "default",
        export_formats: exportFormats,
    };
}

async function loadPreferences() {
    if (!getCurrentUser()) {
        return;
    }
    try {
        const prefs = await requestJson("/users/me/preferences");
        applyPreferencesToUI(prefs);
    } catch {
        // Preferences not critical
    }
}

async function savePreferences() {
    if (!getCurrentUser()) {
        setStatus("请先登录后再保存偏好设置。", true);
        return;
    }
    try {
        const prefs = collectPreferencesFromUI();
        const saved = await requestJson("/users/me/preferences", {
            method: "PUT",
            body: prefs,
        });
        applyPreferencesToUI(saved);
        setStatus("偏好设置已保存。");
    } catch (error) {
        setStatus(error.message || "保存偏好设置失败。", true);
    }
}

function setStatus(message, isError = false) {
    const status = document.getElementById("profile-status");
    if (!message) {
        status.className = "hidden mb-8 text-sm rounded-2xl px-5 py-4";
        status.textContent = "";
        return;
    }
    status.className = `mb-8 text-sm rounded-2xl px-5 py-4 ${isError ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-700"}`;
    status.textContent = message;
}

function formatDate(value) {
    if (!value) return "--";
    try { return new Date(value).toLocaleString("zh-CN"); }
    catch { return value; }
}

function updateSecurity(user, historyItems) {
    document.getElementById("security-login-state").textContent = user ? "已登录" : "未登录";
    document.getElementById("security-user-id").textContent = user && user.user_id ? user.user_id : "--";
    document.getElementById("security-history-count").textContent = String(historyItems.length);
}

function renderUser(user) {
    const currentUser = user || getCurrentUser();
<<<<<<< Updated upstream
    document.getElementById("profile-avatar").src = avatarUrl(currentUser && currentUser.username ? currentUser.username : "SeeMusic");
    document.getElementById("profile-name").textContent = currentUser && currentUser.username ? currentUser.username : "未登录用户";
    document.getElementById("profile-email").textContent = currentUser && currentUser.email ? currentUser.email : "登录后可查看记录";
=======
    const avatarElement = document.getElementById("profile-avatar");
    avatarElement.src = avatarUrl(currentUser);
    document.getElementById("profile-name").textContent = (currentUser && currentUser.username) ? currentUser.username : "未登录用户";
    document.getElementById("profile-email").textContent = (currentUser && currentUser.email)
        ? currentUser.email
        : "登录后可查看数据库中的个人记录";
>>>>>>> Stashed changes
}

function renderStats(items) {
    const counts = items.reduce((summary, item) => {
        const key = item.history_type || "unknown";
        summary[key] = (summary[key] || 0) + 1;
        return summary;
    }, {});
    document.getElementById("stat-audio").textContent = String(counts.audio || 0);
    document.getElementById("stat-report").textContent = String(counts.transcription || 0);
    document.getElementById("stat-score").textContent = String(counts.community || 0);
}

function renderHistory(items, filter = "all") {
    const list = document.getElementById("history-list");
    profileState.currentFilter = filter;
    
    const filtered = filter === "all" ? items : items.filter(i => {
        if (filter === "audio") return i.history_type === "audio";
        if (filter === "transcription") return i.history_type === "transcription";
        if (filter === "community") return i.history_type === "community";
        return true;
    });

    const displayItems = filtered.slice(0, profileState.visibleCount);

    if (displayItems.length === 0) {
        list.innerHTML = `
            <div class="col-span-full py-24 flex flex-col items-center justify-center text-gray-300">
                <iconify-icon icon="solar:box-minimalistic-bold-duotone" class="text-6xl mb-4 opacity-10"></iconify-icon>
                <p class="text-[10px] font-black uppercase tracking-[0.2em]">NO RECORDS FOUND</p>
            </div>
        `;
        return;
    }

    let html = displayItems.map((item) => {
        let icon = "solar:music-note-bold-duotone";
        let moduleName = "音频分析";
        let typeClass = "type-audio";
        let metaInfo = "AI 识别结果";

        if (item.history_type === "transcription") {
            icon = "solar:microphone-large-bold-duotone";
            moduleName = "音乐评估";
            typeClass = "type-transcription";
            metaInfo = `等级: ${item.info?.grade || "N/A"}`;
        } else if (item.history_type === "community") {
            icon = "solar:globus-bold-duotone";
            moduleName = "社区贡献";
            typeClass = "type-community";
            metaInfo = "公开分享";
        }

        return `
            <div class="history-card ${typeClass} slide-in">
                <div class="flex items-center justify-between">
                    <div class="history-icon-box">
                        <iconify-icon icon="${icon}"></iconify-icon>
                    </div>
                    <button class="w-8 h-8 rounded-full flex items-center justify-center text-gray-200 hover:text-red-400 hover:bg-red-50 transition-all" onclick="handleDeleteHistory('${item.history_id}')">
                        <iconify-icon icon="solar:trash-bin-minimalistic-linear"></iconify-icon>
                    </button>
                </div>
                <div class="mt-4">
                    <div class="flex items-center gap-2 mb-1.5">
                        <span class="history-meta">${moduleName}</span>
                        <span class="w-1 h-1 rounded-full bg-gray-200"></span>
                        <span class="history-meta">${formatDate(item.created_at)}</span>
                    </div>
                    <h4 class="history-title" title="${item.info?.filename || item.info?.title || "未命名记录"}">
                        ${item.info?.filename || item.info?.title || "未命名记录"}
                    </h4>
                    <div class="mt-4 flex items-center gap-2">
                        <div class="history-tag">${metaInfo}</div>
                    </div>
                </div>
            </div>
        `;
    }).join("");

    // 分页按钮逻辑
    if (filtered.length > 6) {
        if (filtered.length > profileState.visibleCount) {
            html += `
                <button class="load-more-btn" onclick="handleLoadMore()">
                    查看更多 (${filtered.length - profileState.visibleCount} 条)
                </button>
            `;
        } else {
            html += `
                <button class="load-more-btn bg-gray-50/50" onclick="handleShowLess()">
                    收起记录
                </button>
            `;
        }
    }

    list.innerHTML = html;
}

function handleLoadMore() {
    profileState.visibleCount += 6;
    renderHistory(profileState.historyItems, profileState.currentFilter);
}

function handleShowLess() {
    profileState.visibleCount = 6;
    renderHistory(profileState.historyItems, profileState.currentFilter);
    // 顺便滚回看板顶部，体验更连贯
    document.getElementById("history-list").scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function setupHistoryFilters() {
    const tabs = document.querySelectorAll(".history-tab");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            profileState.visibleCount = 6; // 切换分类时重置加载数
            renderHistory(profileState.historyItems, tab.dataset.filter);
        });
    });
}

function buildMetadataSummary(metadata) {
    const entries = Object.entries(metadata || {}).slice(0, 3);
    if (!entries.length) {
        return "该记录没有额外元数据。";
    }
    return entries.map(([key, value]) => `${key}: ${String(value)}`).join(" · ");
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

async function loadProfile() {
    const localUser = getCurrentUser();
    renderUser(localUser);

    if (!localUser) {
        profileState.historyItems = [];
        document.getElementById("profile-last-update").textContent = "--";
        updateSecurity(null, []);
        renderStats([]);
        renderHistory([]);
        setStatus("未检测到登录态，请先登录后再读取数据库中的个人信息。", true);
        document.getElementById("session-action-text").textContent = "前往登录";
        return;
    }

    try {
        const [user, history] = await Promise.all([
            requestJson("/users/me"),
            requestJson("/users/me/history"),
        ]);
        const items = (history.items || []).slice().sort((a, b) => {
            const left = new Date(a.created_at || 0).getTime();
            const right = new Date(b.created_at || 0).getTime();
            return right - left;
        });

        // ================= Mock 数据强制注入 (展示用) =================
        items.push(
            { history_id: "mock_1", history_type: "audio", created_at: "2026-04-17T12:00:00Z", info: { filename: "Chopin_Nocturne_Op9_No2.mp3" } },
            { history_id: "mock_2", history_type: "transcription", created_at: "2026-04-16T15:30:00Z", info: { filename: "昨日青空_声乐练习.wav", grade: "A", score: 92 } },
            { history_id: "mock_3", history_type: "community", created_at: "2026-04-15T10:20:00Z", info: { title: "Golden Hour - 钢琴独奏谱", download_count: 128 } },
            { history_id: "mock_4", history_type: "audio", created_at: "2026-04-14T09:15:00Z", info: { filename: "天空之城_主题曲.flac" } },
            { history_id: "mock_5", history_type: "transcription", created_at: "2026-04-13T20:45:00Z", info: { filename: "我的歌声里_翻唱评估.mp3", grade: "S", score: 98 } },
            { history_id: "mock_6", history_type: "community", created_at: "2026-04-12T14:10:00Z", info: { title: "SeeMusic 自制练习曲 No.1", like_count: 45 } },
            { history_id: "mock_7", history_type: "audio", created_at: "2026-04-11T11:00:00Z", info: { filename: "大鱼_海棠_伴奏提取.wav" } },
            { history_id: "mock_8", history_type: "transcription", created_at: "2026-04-10T18:22:00Z", info: { filename: "告白气球_音准测试.m4a", grade: "B+", score: 85 } },
            { history_id: "mock_9", history_type: "community", created_at: "2026-04-09T16:50:00Z", info: { title: "小星星变奏曲 - 爵士改编", version: "v1.2" } }
        );
        // ========================================================

        profileState.historyItems = items;

        renderUser(user);
        renderStats(items);
        renderHistory(items);
        updateSecurity(user, items);
        document.getElementById("profile-last-update").textContent = items[0] ? formatDate(items[0].created_at) : formatDate(new Date());
        document.getElementById("session-action-text").textContent = "退出本地登录";
        setStatus(`已从后端同步个人中心数据，共 ${items.length} 条历史记录。`);
    } catch (error) {
        profileState.historyItems = [];
        setStatus(error.message || "加载个人中心失败，请检查登录状态或后端服务。", true);
    }
}

async function handleDeleteHistory(historyId) {
    if (!historyId) {
        return;
    }
    if (!window.confirm("确认删除这条历史记录吗？")) {
        return;
    }
    try {
        await requestJson(`/users/me/history/${encodeURIComponent(historyId)}`, {
            method: "DELETE",
        });
        profileState.historyItems = profileState.historyItems.filter((item) => item.history_id !== historyId);
        renderStats(profileState.historyItems);
        renderHistory(profileState.historyItems);
        updateSecurity(getCurrentUser(), profileState.historyItems);
        document.getElementById("profile-last-update").textContent = profileState.historyItems[0]
            ? formatDate(profileState.historyItems[0].created_at)
            : formatDate(new Date());
        setStatus("历史记录已删除，并已同步到数据库。");
    } catch (error) {
        setStatus(error.message || "删除历史记录失败。", true);
    }
}

function clearCache(btn) {
    const textSpan = btn.querySelector(".cache-text");
    textSpan.textContent = "正在清理前端缓存...";
    btn.classList.replace("text-red-400", "text-yellow-500");

    window.setTimeout(() => {
        localStorage.removeItem("seemusic.transcription.apiBase");
        textSpan.textContent = "清理前端缓存配置";
        btn.classList.replace("text-yellow-500", "text-gray-400");
        setStatus("已清理本地 API 配置缓存，登录态与数据库记录未受影响。");
    }, 600);
}

function calculateAge(birthdayStr) {
    if (!birthdayStr) return "";
    const birthDate = new Date(birthdayStr);
    const today = new Date();
    let age = today.getFullYear() - birthDate.getFullYear();
    const monthDiff = today.getMonth() - birthDate.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
        age--;
    }
    return age >= 0 ? age : "";
}

function setupEditProfileModal() {
    const modal = document.getElementById("edit-profile-modal");
    // 使用类名选择开启按钮
    const openBtn = document.querySelector(".edit-profile-btn");
    const closeBtn = document.getElementById("close-edit-modal-btn");
    const overlay = document.getElementById("edit-modal-overlay");
    const birthdayInput = document.getElementById("edit-birthday");
    const ageInput = document.getElementById("edit-age");
    const tasteChips = document.querySelectorAll(".taste-chip");
    const form = document.getElementById("edit-profile-form");
    
    // 头像预览逻辑
    const avatarTrigger = document.getElementById("avatar-upload-trigger");
    const avatarInput = document.getElementById("avatar-file-input");
    const avatarPreview = document.getElementById("edit-avatar-preview");

    if (avatarTrigger && avatarInput) {
        avatarTrigger.addEventListener("click", () => avatarInput.click());
        avatarInput.addEventListener("change", (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (event) => {
                    avatarPreview.src = event.target.result;
                };
                reader.readAsDataURL(file);
            }
        });
    }

    if (!modal || !openBtn) return;

    openBtn.addEventListener("click", () => {
        // 初始化表单数据
        const currentName = document.getElementById("profile-name").textContent;
        document.getElementById("edit-nickname").value = currentName === "未登录用户" ? "" : currentName;
        
        // 同步当前头像到预览图
        if (avatarPreview) {
            avatarPreview.src = document.getElementById("profile-avatar").src;
        }
        
        modal.classList.add("active");
    });

    const closeModal = () => modal.classList.remove("active");
    closeBtn.addEventListener("click", closeModal);
    overlay.addEventListener("click", closeModal);

    // Age calculation logic
    birthdayInput.addEventListener("change", (e) => {
        ageInput.value = calculateAge(e.target.value);
    });

    // Taste chips multi-selection
    tasteChips.forEach(chip => {
        chip.addEventListener("click", () => {
            chip.classList.toggle("active");
        });
    });

    form.addEventListener("submit", (e) => {
        e.preventDefault();
        
        // 更新昵称
        const nickname = document.getElementById("edit-nickname").value;
        if (nickname) {
            document.getElementById("profile-name").textContent = nickname;
        }

        // 更新主页面头像
        if (avatarPreview && avatarPreview.src) {
            document.getElementById("profile-avatar").src = avatarPreview.src;
        }

        setStatus("个人详情已在本地同步更新。");
        closeModal();
    });
}

function bindEvents() {
    setupEditProfileModal();
    setupHistoryFilters();
    document.getElementById("refresh-profile-btn").addEventListener("click", () => {
        loadProfile();
    });

    document.getElementById("session-action-btn").addEventListener("click", async () => {
        if (getCurrentUser()) {
            try {
                await requestJson("/auth/logout", { method: "POST" });
            } catch (error) {
                setStatus(error.message || "退出登录请求失败，将仅清理本地登录态。", true);
            } finally {
                clearAuthSession();
                window.location.href = "login.html";
            }
            return;
        }
        window.location.href = "login.html";
    });

    document.getElementById("clear-cache-btn").addEventListener("click", function handleCacheClear() {
        clearCache(this);
    });

    document.getElementById("save-prefs-btn").addEventListener("click", () => {
        savePreferences();
    });

    document.getElementById("history-list").addEventListener("click", (event) => {
        const button = event.target.closest("[data-history-id]");
        if (!button) {
            return;
        }
        handleDeleteHistory(button.dataset.historyId);
    });
}

bindEvents();
window.addEventListener("load", () => {
    loadProfile();
    loadPreferences();
});

async function uploadAvatar() {
    const fileInput = document.getElementById("avatar-input");
    const file = fileInput.files[0];
    
    if (!file) {
        alert("请先选择图片！");
        return;
    }

    const formData = new FormData();
    formData.append("file", file); // 这里的 "file" 必须和后端 UploadFile 变量名一致

    try {
        // 直接用原生 fetch，避免 requestJson 的 JSON 处理逻辑污染 FormData
        const response = await fetch("http://127.0.0.1:8000/api/v1/users/avatar", {
            method: "POST",
            headers: {
                // 注意：这里不要设置 Content-Type，浏览器会自动处理成 multipart/form-data
                "Authorization": `Bearer ${localStorage.getItem("my_token")}`
            },
            body: formData 
        });

        const result = await response.json(); // 等待后端返回 JSON

        if (result.code === 0) {
            alert("头像上传成功！");
            
            // 【处理响应】：更新页面头像
            const newAvatarUrl = "http://127.0.0.1:8000" + result.data.avatar_url;
            document.getElementById("profile-avatar").src = newAvatarUrl;
            
            // 更新本地存储
            const user = JSON.parse(localStorage.getItem("user_info") || "{}");
            user.avatar = result.data.avatar_url;
            localStorage.setItem("user_info", JSON.stringify(user));
        } else {
            alert("上传失败：" + result.message);
        }
    } catch (error) {
        console.error("上传错误:", error);
        alert("后端服务未启动或连接中断");
    }
}