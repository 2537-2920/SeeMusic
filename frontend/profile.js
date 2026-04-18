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
    const isGuest = !currentUser || !currentUser.username;
    
    // 头像渲染逻辑：如果有自定义头像则用自定义的，否则用生成的
    const avatarImg = document.getElementById("profile-avatar");
    if (currentUser && currentUser.avatar && currentUser.avatar.length > 5) {
        // 使用公用工具补全服务器地址，并添加时间戳防止缓存
        const timestamp = new Date().getTime();
        const fullUrl = buildServerUrl(currentUser.avatar);
        avatarImg.src = `${fullUrl}${fullUrl.includes("?") ? "&" : "?"}t=${timestamp}`;
    } else {
        avatarImg.src = avatarUrl(currentUser && currentUser.username ? currentUser.username : "SeeMusic");
    }

    document.getElementById("profile-name").textContent = currentUser && currentUser.username ? (currentUser.nickname || currentUser.username) : "未登录用户";
    document.getElementById("profile-email").textContent = currentUser && currentUser.email ? currentUser.email : "登录后可查看记录";
    
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
        
        // 渲染从服务器获取的最新数据
        const items = (history.data || history.items || []).slice().sort((a, b) => {
            const left = new Date(a.created_at || 0).getTime();
            const right = new Date(b.created_at || 0).getTime();
            return right - left;
        });

        profileState.historyItems = items;
        document.getElementById("profile-last-update").textContent = formatDate(new Date());

        renderUser(user);
        renderStats(items);
        renderHistory(items, profileState.currentFilter);
        updateSecurity(user, items);
        
        document.getElementById("profile-last-update").textContent = items[0] && items[0].created_at ? formatDate(items[0].created_at) : formatDate(new Date());
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
        avatarInput.addEventListener("change", async (e) => {
            const file = e.target.files[0];
            if (file) {
                // 1. 本地预览
                const reader = new FileReader();
                reader.onload = (event) => {
                    avatarPreview.src = event.target.result;
                };
                reader.readAsDataURL(file);

                // 2. 立即上传后端
                try {
                    setStatus("正在上传头像...");
                    if (avatarTrigger) avatarTrigger.classList.add("opacity-50", "pointer-events-none");
                    
                    const formData = new FormData();
                    formData.append("file", file);

                    // 获取 Token
                    const user = getCurrentUser();
                    const token = localStorage.getItem(STORAGE_KEYS.authToken);

                    const response = await fetch(buildApiUrl("/users/me/avatar"), {
                        method: "POST",
                        headers: { "Authorization": `Bearer ${token}` },
                        body: formData
                    });
                    
                    const result = await response.json();
                    if (result.code === 0) {
                        const newAvatarUrl = result.data.avatar_url;
                        setStatus("头像上传并保存成功！");
                        profileState.tempAvatarUrl = newAvatarUrl;
                        
                        // 预先刷新侧边栏和弹窗预览，给用户最直接的反馈
                        const timestamp = new Date().getTime();
                        const fullUrl = buildServerUrl(newAvatarUrl);
                        const finalUrl = `${fullUrl}${fullUrl.includes("?") ? "&" : "?"}t=${timestamp}`;
                        
                        if (avatarPreview) avatarPreview.src = finalUrl;
                        const sidebarAvatar = document.getElementById("profile-avatar");
                        if (sidebarAvatar) sidebarAvatar.src = finalUrl;
                    } else {
                        throw new Error(result.message);
                    }
                } catch (error) {
                    setStatus("头像上传失败: " + error.message, true);
                } finally {
                    if (avatarTrigger) avatarTrigger.classList.remove("opacity-50", "pointer-events-none");
                }
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
            profileState.tempAvatarUrl = null; // 清空暂存
            setStatus("个人资料已成功持久化至数据库。");
            closeModal();
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
