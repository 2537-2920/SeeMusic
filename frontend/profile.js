const {
    requestJson,
    getCurrentUser,
    clearAuthSession,
    avatarUrl,
    buildServerUrl,
    buildApiUrl,
    STORAGE_KEYS,
} = window.SeeMusicApp;

const profileState = {
    historyItems: [],
    visibleCount: 6, 
    currentFilter: "all",
    searchQuery: "",
    tempAvatarUrl: null // 暂存新上传但未点击“保存修改”的头像 URL
};

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
    const avatarElement = document.getElementById("profile-avatar");
    avatarElement.src = avatarUrl(currentUser);
    document.getElementById("profile-name").textContent = (currentUser && (currentUser.nickname || currentUser.username)) 
  ? (currentUser.nickname || currentUser.username) 
  : "未登录用户";
    document.getElementById("profile-email").textContent = (currentUser && currentUser.email)
        ? currentUser.email
        : "登录后可查看数据库中的个人记录";
    // 渲染简介
    const bioEl = document.getElementById("profile-bio");
    if (bioEl) {
        bioEl.textContent = currentUser && currentUser.bio ? currentUser.bio : "还没有填写个人简介...";
    }

    // 渲染音乐标签
    const tasteContainer = document.getElementById("profile-taste-tags");
    if (tasteContainer) {
        tasteContainer.innerHTML = "";
        if (currentUser && Array.isArray(currentUser.music_taste)) {
            currentUser.music_taste.forEach(tag => {
                const span = document.createElement("span");
                span.className = "px-2 py-0.5 rounded-full bg-blue-50 text-[10px] text-[#457b9d] border border-blue-100/50";
                span.textContent = tag;
                tasteContainer.appendChild(span);
            });
        }
    }
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
    const filtered = items.filter(i => {
        const type = (i.history_type || "").toLowerCase();
        
        // 1. 类型过滤 (更宽松的匹配)
        let typeMatch = true;
        if (filter === "transcription") {
            // 兼容多种可能出现的识谱类型名称
            typeMatch = (type === "transcription" || type === "audio" || type === "report");
        } else if (filter === "evaluation") {
            typeMatch = (type === "evaluation" || type === "score");
        } else if (filter === "community") {
            typeMatch = (type === "community");
        }
        
        if (!typeMatch) return false;

        // 2. 关键词筛选 (Search)
        if (profileState.searchQuery) {
            const q = profileState.searchQuery.toLowerCase();
            const title = (i.info?.title || "").toLowerCase();
            const filename = (i.info?.filename || "").toLowerCase();
            const label = (i.info?.label || "").toLowerCase();
            // 只要其中任何一个字段包含搜素词就保留
            return title.includes(q) || filename.includes(q) || label.includes(q);
        }

        return true;
    });

    // --- 搜索状态条交互控制 ---
    const searchStatus = document.getElementById("search-status-bar");
    const searchCountText = document.getElementById("search-count-text");
    
    if (searchStatus && searchCountText) {
        if (profileState.searchQuery) {
            searchStatus.classList.remove("hidden");
            searchCountText.textContent = `为您找到了 ${filtered.length} 条关于 "${profileState.searchQuery}" 的记录`;
        } else {
            searchStatus.classList.add("hidden");
        }
    }

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
        let metaInfo = item.info?.duration || "AI 识别结果";

        const type = (item.history_type || "").toLowerCase();

        if (type === "transcription" || type === "audio") {
            icon = "solar:notes-bold-duotone";
            moduleName = "识谱分析";
            typeClass = "type-transcription";
            metaInfo = item.info?.label || "乐谱提取";
        } else if (type === "evaluation") {
            icon = "solar:microphone-large-bold-duotone";
            moduleName = "唱歌测评";
            typeClass = "type-evaluation"; 
            metaInfo = `评分: ${item.info?.score || item.info?.overall_score || "进行中"}`;
        } else if (type === "community") {
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
        
        // 渲染从服务器获取的最新资料
        renderUser(user);
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
        // 移除原有的同步成功提示
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
    // 使用 ID 选择开启按钮
    const openBtn = document.getElementById("open-edit-modal-btn");
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
        const user = getCurrentUser();
        if (!user) {
            setStatus("请先登录后再修改个人资料。", true);
            return;
        }
        document.getElementById("edit-nickname").value = user.nickname || user.username || "";
        document.getElementById("edit-bio").value = user.bio || "";
        document.getElementById("edit-birthday").value = user.birthday || "";
        document.getElementById("edit-age").value = calculateAge(user.birthday);
        
        // 初始化音乐倾向标签
        tasteChips.forEach(chip => {
            const val = chip.dataset.value;
            if (user.music_taste && user.music_taste.includes(val)) {
                chip.classList.add("active");
            } else {
                chip.classList.remove("active");
            }
        });
        
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

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const avatarInput = document.getElementById("avatar-file-input");
        const selectedTastes = Array.from(document.querySelectorAll(".taste-chip.active")).map(c => c.dataset.value);
        
        const payload = {
            nickname: document.getElementById("edit-nickname").value,
            bio: document.getElementById("edit-bio").value,
            birthday: document.getElementById("edit-birthday").value,
            music_taste: selectedTastes
        };

        // 如果在弹窗期间上传了新头像，一并同步给后端
        if (profileState.tempAvatarUrl) {
            payload.avatar = profileState.tempAvatarUrl;
        }

        try {
            setStatus("正在同步至数据库...");
            if (avatarInput.files && avatarInput.files[0]) {
            setStatus("正在上传头像...");
            const avatarFile = avatarInput.files[0];
            const formData = new FormData();
            formData.append("file", avatarFile);

            // 调用你写好的头像上传接口
            const avatarResp = await fetch("http://127.0.0.1:8000/api/v1/users/avatar", {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${localStorage.getItem("seemusic.auth.token")}`//这里的原因，传错了token
                },
                body: formData
            });
            const avatarResult = await avatarResp.json();
            
            if (avatarResult.code === 0) {
                // 上传成功后，把新的头像路径也加到资料更新的 payload 里
                const newRelativePath = avatarResult.data.avatar_url; 
                payload.avatar = newRelativePath; 
                // --- 核心修复：定义 fullUrl 并加上时间戳 ---
                const API_BASE = "http://127.0.0.1:8000"; // 确保定义了后端地址
                const timestamp = new Date().getTime();   // 生成当前时间戳
            
                // 拼接完整的、带“防缓存”标记的 URL
                const fullUrl = `${API_BASE}${newRelativePath}?t=${timestamp}`;
            
                console.log("正在实时更新界面头像:", fullUrl);

                // 实时更新页面上的所有头像框
                const profileAvatar = document.getElementById("profile-avatar");
                const headerAvatar = document.getElementById("header-avatar");
                const editPreview = document.getElementById("edit-avatar-preview");

                if (profileAvatar) profileAvatar.src = fullUrl;
                if (headerAvatar) headerAvatar.src = fullUrl;
                if (editPreview) editPreview.src = fullUrl;
            } else {
                throw new Error("头像上传失败：" + avatarResult.message);
            }
            }
            const updatedUser = await requestJson("/users/me", {
                method: "PATCH",
                body: payload
            });
            
            // 更新成功后，同步本地登录态缓存（使用公共定义的键名）
            const currentUser = getCurrentUser();
            if (currentUser) {
                const newUserData = { ...currentUser, ...updatedUser };
                localStorage.setItem(STORAGE_KEYS.currentUser, JSON.stringify(newUserData));
            }

            renderUser(updatedUser);
            const localStoreKey = "seeMusic_currentUser"; 
            localStorage.setItem(localStoreKey, JSON.stringify(updatedUser));
            setStatus("个人资料已成功持久化至数据库。");
            modal.classList.remove("active");
        } catch (error) {
            setStatus(error.message || "同步失败，请检查网络。", true);
        }
    });
}

function bindEvents() {
    setupEditProfileModal();
    setupHistoryFilters();
    setupSearch();
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
});
function setupSearch() {
    const searchInput = document.getElementById("history-search-input");
    const clearBtn = document.getElementById("clear-search-btn");
    const exitBtn = document.getElementById("exit-search-btn");
    
    if (!searchInput || !clearBtn) return;

    const searchContainer = searchInput.closest(".group");

    const resetSearch = () => {
        searchInput.value = "";
        profileState.searchQuery = "";
        clearBtn.classList.add("opacity-0", "pointer-events-none");
        if (searchContainer) searchContainer.classList.remove("search-active");
        profileState.visibleCount = 6;
        renderHistory(profileState.historyItems, profileState.currentFilter);
    };

    searchInput.addEventListener("input", (e) => {
        const value = e.target.value.trim();
        profileState.searchQuery = value;
        
        // 视觉反馈：变换清空按钮和图标状态
        if (value) {
            clearBtn.classList.remove("opacity-0", "pointer-events-none");
            if (searchContainer) searchContainer.classList.add("search-active");
        } else {
            clearBtn.classList.add("opacity-0", "pointer-events-none");
            if (searchContainer) searchContainer.classList.remove("search-active");
        }

        // 实时筛选
        profileState.visibleCount = 6;
        renderHistory(profileState.historyItems, profileState.currentFilter);
    });

    clearBtn.addEventListener("click", () => {
        resetSearch();
        searchInput.focus();
    });

    if (exitBtn) {
        exitBtn.addEventListener("click", resetSearch);
    }
}

async function uploadAvatar() {
const fileInput = document.getElementById("avatar-input");
const file = fileInput.files[0];
if (!file) {
    alert("请先选择图片！");
    return;
}
const formData = new FormData();
formData.append("file", file);
try {
    const response = await fetch("http://127.0.0.1:8000/api/v1/users/avatar", {
        method: "POST",
        headers: {
            "Authorization": `Bearer ${localStorage.getItem("seemusic.auth.token")}`
        },
        body: formData 
    });
    const result = await response.json();
    if (result.code === 0) {
        alert("头像上传成功！");
        const newAvatarUrl = "http://127.0.0.1:8000" + result.data.avatar_url;
        document.getElementById("profile-avatar").src = newAvatarUrl;
        // 1. 调用现成的全局函数获取当前用户（这能确保你拿到的是正确的抽屉内容）
        const currentUser = getCurrentUser();

        if (currentUser) {
            // 2. 给这个人加上最新的头像路径
            currentUser.avatar = result.data.avatar_url;
    
            // 3. 按照原项目规定的 Key，把更新后的人塞回抽屉里
            localStorage.setItem(STORAGE_KEYS.currentUser, JSON.stringify(currentUser));
            }
    } else {
        alert("上传失败：" + result.message);
    }
} catch (error) {
    console.error("上传错误:", error);
    alert("后端服务未启动或连接中断");
}
}
