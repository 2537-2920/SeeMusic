const {
    requestJson,
    getCurrentUser,
    getAuthToken,
    avatarUrl,
} = window.SeeMusicApp;

const evaluationState = {
    file: null,
    analysis: null,
    report: null,
};

function setBanner(id, message, isError = false) {
    const el = document.getElementById(id);
    if (!message) {
        el.className = "hidden text-xs rounded-xl px-4 py-3";
        el.textContent = "";
        return;
    }
    el.className = `text-xs rounded-xl px-4 py-3 ${isError ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-700"}`;
    el.textContent = message;
}

function toPercent(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return 0;
    }
    const numeric = Number(value);
    return numeric <= 1 ? numeric * 100 : numeric;
}

function percentText(value) {
    return `${Math.round(toPercent(value))}%`;
}

function scoreLabel(score) {
    if (score >= 90) {
        return { text: "表现出色", className: "bg-green-100 text-green-600" };
    }
    if (score >= 75) {
        return { text: "表现稳定", className: "bg-blue-100 text-blue-600" };
    }
    if (score >= 60) {
        return { text: "仍可提升", className: "bg-yellow-100 text-yellow-600" };
    }
    return { text: "建议重点练习", className: "bg-red-100 text-red-600" };
}

function summarizeFeedback(analysis) {
    if (!analysis) {
        return "等待后端返回分析结果。";
    }
    const feedback = analysis.feedback;
    if (typeof analysis.detailed_assessment === "string" && analysis.detailed_assessment.trim()) {
        return analysis.detailed_assessment.trim();
    }
    if (typeof feedback === "string" && feedback.trim()) {
        return feedback.trim();
    }
    if (Array.isArray(feedback) && feedback.length) {
        return feedback.map((item) => String(item)).join("；");
    }
    if (feedback && typeof feedback === "object") {
        const values = Object.values(feedback).flatMap((item) => Array.isArray(item) ? item : [item]);
        if (values.length) {
            return values.map((item) => String(item)).join("；");
        }
    }
    return "后端未返回文字建议，可结合下方偏差明细继续排查。";
}

function renderHeader() {
    const currentUser = getCurrentUser();
    document.getElementById("current-date").textContent = new Date().toLocaleDateString("zh-CN");
    document.getElementById("current-user-name").textContent = currentUser && currentUser.username ? currentUser.username : "游客模式";
    document.getElementById("current-user-avatar").src = avatarUrl(currentUser && currentUser.username ? currentUser.username : "SeeMusic");
}

function renderAnalysis() {
    const analysis = evaluationState.analysis;
    if (!analysis) {
        document.getElementById("analysis-id-display").textContent = "--";
        document.getElementById("analysis-ref-display").textContent = "--";
        document.getElementById("analysis-user-bpm").textContent = "--";
        document.getElementById("analysis-reference-bpm").textContent = "--";
        document.getElementById("analysis-beat-summary").textContent = "--";
        document.getElementById("evaluation-feedback").textContent = "等待后端返回分析结果。";
        document.getElementById("report-score").textContent = "--";
        document.getElementById("report-grade").textContent = "等待分析";
        document.getElementById("report-grade").className = "ml-auto px-3 py-1 bg-gray-100 text-gray-500 rounded-full text-xs font-bold";
        document.getElementById("metric-accuracy").textContent = "--";
        document.getElementById("metric-coverage").textContent = "--";
        document.getElementById("metric-consistency").textContent = "--";
        document.getElementById("metric-deviation").textContent = "--";
        document.getElementById("bar-accuracy").style.width = "0%";
        document.getElementById("bar-coverage").style.width = "0%";
        document.getElementById("bar-consistency").style.width = "0%";
        document.getElementById("rhythm-error-list").innerHTML = `
            <div class="p-4 rounded-xl border border-dashed border-gray-200 bg-white flex-1 min-w-[200px] text-sm text-gray-400">
                完成一次评估后，这里会展示后端返回的节奏误差分类与说明。
            </div>
        `;
        return;
    }

    const totalScore = Math.round(Number(analysis.score || 0));
    const label = scoreLabel(totalScore);
    const consistencyValue = analysis.consistency_ratio ?? analysis.user_consistency ?? 0;
    const coverageValue = analysis.coverage_ratio ?? 0;
    const errorSummary = `${analysis.missing_beats || 0} / ${analysis.extra_beats || 0}`;

    document.getElementById("analysis-id-display").textContent = analysis.analysis_id || "--";
    document.getElementById("analysis-ref-display").textContent = document.getElementById("reference-id-input").value.trim() || "--";
    document.getElementById("analysis-user-bpm").textContent = analysis.user_bpm ? String(Math.round(Number(analysis.user_bpm))) : "--";
    document.getElementById("analysis-reference-bpm").textContent = analysis.reference_bpm ? String(Math.round(Number(analysis.reference_bpm))) : "--";
    document.getElementById("analysis-beat-summary").textContent = errorSummary;
    document.getElementById("evaluation-feedback").textContent = summarizeFeedback(analysis);

    document.getElementById("report-score").textContent = String(totalScore);
    document.getElementById("report-grade").textContent = label.text;
    document.getElementById("report-grade").className = `ml-auto px-3 py-1 rounded-full text-xs font-bold ${label.className}`;
    document.getElementById("metric-accuracy").textContent = percentText(analysis.timing_accuracy);
    document.getElementById("metric-coverage").textContent = percentText(coverageValue);
    document.getElementById("metric-consistency").textContent = percentText(consistencyValue);
    document.getElementById("metric-deviation").textContent = `${Math.round(Number(analysis.mean_deviation_ms || 0))} ms`;
    document.getElementById("bar-accuracy").style.width = `${Math.min(toPercent(analysis.timing_accuracy), 100)}%`;
    document.getElementById("bar-coverage").style.width = `${Math.min(toPercent(coverageValue), 100)}%`;
    document.getElementById("bar-consistency").style.width = `${Math.min(toPercent(consistencyValue), 100)}%`;
    document.getElementById("last-analysis-time").textContent = new Date().toLocaleString("zh-CN");

    renderErrorList(analysis.error_classification);
}

function renderErrorList(errorClassification) {
    const container = document.getElementById("rhythm-error-list");
    if (!errorClassification || typeof errorClassification !== "object" || !Object.keys(errorClassification).length) {
        container.innerHTML = `
            <div class="p-4 rounded-xl border border-gray-100 bg-white flex-1 min-w-[200px] text-sm text-gray-500">
                本次分析未返回结构化误差分类，可重点参考上方综合建议。
            </div>
        `;
        return;
    }

    container.innerHTML = Object.entries(errorClassification).map(([key, value]) => `
        <div class="p-4 rounded-xl border border-gray-100 bg-white flex-1 min-w-[200px]">
            <div class="text-xs text-gray-400 mb-2 uppercase tracking-wider font-bold">${escapeHtml(key)}</div>
            <div class="p-2 error-highlight rounded-lg">
                <span class="text-sm font-medium">${escapeHtml(stringifyValue(value))}</span>
            </div>
        </div>
    `).join("");
}

function stringifyValue(value) {
    if (Array.isArray(value)) {
        return value.map((item) => stringifyValue(item)).join("；");
    }
    if (value && typeof value === "object") {
        return Object.entries(value).map(([key, item]) => `${key}: ${stringifyValue(item)}`).join("；");
    }
    return String(value);
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

async function saveHistory(payload) {
    if (!getAuthToken()) {
        return;
    }
    try {
        await requestJson("/users/me/history", {
            method: "POST",
            body: payload,
        });
    } catch (error) {
        console.warn("save history failed", error);
    }
}

function setSelectedFile(file) {
    evaluationState.file = file || null;
    document.getElementById("evaluation-file-name").textContent = file
        ? `${file.name} (${Math.round(file.size / 1024)} KB)`
        : "尚未选择文件";
}

async function runEvaluation() {
    const file = evaluationState.file;
    const refId = document.getElementById("reference-id-input").value.trim();
    const language = document.getElementById("evaluation-language").value;
    const scoringModel = document.getElementById("evaluation-model").value;
    const threshold = document.getElementById("evaluation-threshold").value;
    const submitBtn = document.getElementById("evaluation-submit-btn");

    if (!file) {
        setBanner("evaluation-status", "请先选择要评估的音频文件。", true);
        return;
    }
    if (!refId) {
        setBanner("evaluation-status", "请填写后端可识别的参考音频 ID。", true);
        return;
    }

    const formData = new FormData();
    formData.append("user_audio", file);
    formData.append("ref_id", refId);
    formData.append("language", language);
    formData.append("scoring_model", scoringModel);
    formData.append("threshold_ms", threshold || "50");

    submitBtn.disabled = true;
    submitBtn.style.opacity = "0.7";
    setBanner("evaluation-status", "正在调用后端分析接口并写入数据库...");

    try {
        const payload = await requestJson("/analyze/rhythm", {
            method: "POST",
            body: formData,
        });
        evaluationState.analysis = payload;
        evaluationState.report = null;
        renderAnalysis();
        setBanner("evaluation-status", `分析完成，analysis_id=${payload.analysis_id}`);
        await saveHistory({
            type: "audio",
            resource_id: payload.analysis_id,
            title: `节奏评估：${file.name}`,
            metadata: {
                ref_id: refId,
                score: Math.round(Number(payload.score || 0)),
                language,
                scoring_model: scoringModel,
            },
        });
    } catch (error) {
        setBanner("evaluation-status", error.message || "分析失败，请检查参考音频配置。", true);
    } finally {
        submitBtn.disabled = false;
        submitBtn.style.opacity = "1";
    }
}

async function exportReport() {
    const analysis = evaluationState.analysis;
    const exportBtn = document.getElementById("report-export-btn");
    if (!analysis || !analysis.analysis_id) {
        setBanner("report-export-status", "请先完成一次分析，再导出报告。", true);
        return;
    }

    exportBtn.disabled = true;
    exportBtn.style.opacity = "0.7";
    setBanner("report-export-status", "正在生成报告并写入报告表...");

    try {
        const payload = await requestJson("/reports/export", {
            method: "POST",
            body: {
                analysis_id: analysis.analysis_id,
                formats: ["pdf"],
                include_charts: true,
            },
        });
        evaluationState.report = payload;
        setBanner("report-export-status", `报告已生成并持久化，report_id=${payload.report_id}`);
        await saveHistory({
            type: "report",
            resource_id: payload.report_id,
            title: `导出评估报告：${analysis.analysis_id}`,
            metadata: {
                analysis_id: analysis.analysis_id,
                formats: "pdf",
                include_charts: true,
            },
        });
    } catch (error) {
        setBanner("report-export-status", error.message || "报告导出失败。", true);
    } finally {
        exportBtn.disabled = false;
        exportBtn.style.opacity = "1";
    }
}

function variationCardClass(index) {
    const variants = [
        "bg-[#FDF7FF] border border-purple-100 text-[#8E44AD]",
        "bg-[#F0FFF4] border border-green-100 text-[#27AE60]",
        "bg-[#FFF9F0] border border-orange-100 text-[#D35400]",
    ];
    return variants[index % variants.length];
}

async function loadVariations() {
    const analysis = evaluationState.analysis;
    const style = document.getElementById("variation-style-select").value;
    const difficulty = document.getElementById("variation-difficulty-select").value;
    const submitBtn = document.getElementById("variation-submit-btn");

    if (!analysis || !analysis.analysis_id) {
        setBanner("variation-status", "请先完成一次分析，再生成变奏建议。", true);
        return;
    }

    submitBtn.disabled = true;
    submitBtn.style.opacity = "0.7";
    setBanner("variation-status", "正在请求后端变奏建议...");

    try {
        const payload = await requestJson("/generation/variation-suggestions", {
            method: "POST",
            body: {
                score_id: analysis.analysis_id,
                style,
                difficulty,
            },
        });
        renderVariations(payload.suggestions || []);
        setBanner("variation-status", `已生成 ${payload.suggestions ? payload.suggestions.length : 0} 条建议。`);
    } catch (error) {
        setBanner("variation-status", error.message || "变奏建议生成失败。", true);
    } finally {
        submitBtn.disabled = false;
        submitBtn.style.opacity = "1";
    }
}

function renderVariations(items) {
    const list = document.getElementById("variation-list");
    if (!items.length) {
        list.innerHTML = `
            <div class="p-4 rounded-2xl bg-gray-50 border border-gray-100 text-sm text-gray-400">
                后端当前没有返回可展示的变奏建议。
            </div>
        `;
        return;
    }

    list.innerHTML = items.map((item, index) => `
        <div class="p-4 rounded-2xl relative overflow-hidden ${variationCardClass(index)}">
            <div class="relative z-10">
                <div class="flex justify-between items-start mb-2">
                    <h5 class="font-bold">${escapeHtml(item.type || `建议 ${index + 1}`)}</h5>
                    <iconify-icon class="text-2xl" icon="solar:stars-bold"></iconify-icon>
                </div>
                <p class="text-xs leading-relaxed">${escapeHtml(item.description || "暂无说明")}</p>
            </div>
        </div>
    `).join("");
}

function bindFileUpload() {
    const input = document.getElementById("evaluation-file-input");
    const dropzone = document.getElementById("evaluation-dropzone");

    dropzone.addEventListener("click", () => input.click());
    input.addEventListener("change", () => {
        const file = input.files && input.files[0];
        setSelectedFile(file || null);
    });

    dropzone.addEventListener("dragover", (event) => {
        event.preventDefault();
        dropzone.classList.add("border-blue-300");
    });
    dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("border-blue-300");
    });
    dropzone.addEventListener("drop", (event) => {
        event.preventDefault();
        dropzone.classList.remove("border-blue-300");
        const file = event.dataTransfer.files && event.dataTransfer.files[0];
        if (!file) {
            return;
        }
        const transfer = new DataTransfer();
        transfer.items.add(file);
        input.files = transfer.files;
        setSelectedFile(file);
    });
}

function bindEvents() {
    bindFileUpload();
    document.getElementById("evaluation-submit-btn").addEventListener("click", runEvaluation);
    document.getElementById("report-export-btn").addEventListener("click", exportReport);
    document.getElementById("variation-submit-btn").addEventListener("click", loadVariations);
}

renderHeader();
renderAnalysis();
bindEvents();
