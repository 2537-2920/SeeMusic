const {
    requestJson,
    getCurrentUser,
    clearAuthSession,
    avatarUrl,
} = window.SeeMusicApp;

const profileState = {
    historyItems: [],
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
        // Preferences not critical — keep defaults
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
    if (!value) {
        return "--";
    }
    try {
        return new Date(value).toLocaleString("zh-CN");
    } catch {
        return value;
    }
}

function updateSecurity(user, historyItems) {
    document.getElementById("security-login-state").textContent = user ? "已登录" : "未登录";
    document.getElementById("security-user-id").textContent = user && user.user_id ? user.user_id : "--";
    document.getElementById("security-history-count").textContent = String(historyItems.length);
}

function renderUser(user) {
    const currentUser = user || getCurrentUser();
    document.getElementById("profile-avatar").src = avatarUrl(currentUser && currentUser.username ? currentUser.username : "SeeMusic");
    document.getElementById("profile-name").textContent = currentUser && currentUser.username ? currentUser.username : "未登录用户";
    document.getElementById("profile-email").textContent = currentUser && currentUser.email
        ? currentUser.email
        : "登录后可查看数据库中的个人记录";
}

function renderStats(items) {
    const counts = items.reduce((summary, item) => {
        const key = item.type || "unknown";
        summary[key] = (summary[key] || 0) + 1;
        return summary;
    }, {});
    document.getElementById("stat-audio").textContent = String(counts.audio || 0);
    document.getElementById("stat-report").textContent = String(counts.report || 0);
    document.getElementById("stat-score").textContent = String(counts.score || 0);
}

function buildDayBuckets(items) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const buckets = [];

    for (let offset = 6; offset >= 0; offset -= 1) {
        const day = new Date(today);
        day.setDate(today.getDate() - offset);
        buckets.push({
            date: day,
            label: day.toLocaleDateString("zh-CN", { weekday: "short" }),
            count: 0,
        });
    }

    items.forEach((item) => {
        if (!item.created_at) {
            return;
        }
        const createdAt = new Date(item.created_at);
        createdAt.setHours(0, 0, 0, 0);
        const bucket = buckets.find((entry) => entry.date.getTime() === createdAt.getTime());
        if (bucket) {
            bucket.count += 1;
        }
    });
    return buckets;
}

function renderChart(items) {
    const buckets = buildDayBuckets(items);
    const chart = document.getElementById("activity-chart");
    const peak = Math.max(...buckets.map((item) => item.count), 1);

    chart.innerHTML = buckets.map((item) => {
        const height = item.count === 0 ? 12 : Math.max((item.count / peak) * 100, 18);
        return `
            <div class="flex-1 flex flex-col items-center gap-2 h-full">
                <div class="chart-bar w-full ${item.count === peak && item.count > 0 ? "" : "opacity-50"}" style="height: ${height}%"></div>
                <span class="text-[10px] text-gray-400">${item.label}</span>
                <span class="text-[10px] text-[#457b9d] font-bold">${item.count}</span>
            </div>
        `;
    }).join("");

    const total = items.length;
    const latest = items[0] ? formatDate(items[0].created_at) : "暂无";
    document.getElementById("activity-summary").textContent = `最近 7 天共产生 ${total} 条历史记录，最新一条时间：${latest}。`;
}

function historyTypeLabel(type) {
    if (type === "audio") {
        return "音频分析";
    }
    if (type === "report") {
        return "报告导出";
    }
    if (type === "score") {
        return "乐谱操作";
    }
    return "其他记录";
}

function renderHistory(items) {
    const list = document.getElementById("history-list");
    if (!items.length) {
        list.innerHTML = `
            <div class="rounded-2xl border border-dashed border-gray-200 p-6 text-center text-sm text-gray-400">
                当前数据库里还没有你的个人历史记录。可以先去社区下载乐谱，或在评估页生成分析与报告。
            </div>
        `;
        return;
    }

    list.innerHTML = items.slice(0, 8).map((item) => `
        <div class="rounded-2xl border border-gray-100 bg-gray-50/70 px-5 py-4">
            <div class="flex items-start justify-between gap-4">
                <div>
                    <div class="flex items-center gap-2">
                        <span class="text-xs px-2.5 py-1 rounded-full bg-white text-[#457b9d] border border-[#457b9d]/10">${historyTypeLabel(item.type)}</span>
                        <span class="text-xs text-gray-400">${item.resource_id || "--"}</span>
                    </div>
                    <h4 class="text-sm font-bold text-gray-800 mt-3">${escapeHtml(item.title || "未命名记录")}</h4>
                    <p class="text-xs text-gray-500 mt-2 leading-relaxed">${escapeHtml(buildMetadataSummary(item.metadata || {}))}</p>
                </div>
                <div class="flex flex-col items-end gap-3">
                    <span class="text-[11px] text-gray-400 whitespace-nowrap">${formatDate(item.created_at)}</span>
                    <button class="text-xs text-red-400 hover:text-red-500 font-medium" data-history-id="${escapeHtml(item.history_id || "")}" type="button">删除</button>
                </div>
            </div>
        </div>
    `).join("");
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
        renderChart([]);
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
        profileState.historyItems = items;

        renderUser(user);
        renderStats(items);
        renderChart(items);
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
        renderChart(profileState.historyItems);
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

function bindEvents() {
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
