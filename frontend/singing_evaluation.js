const {
    requestJson,
    getCurrentUser,
    getAuthToken,
    avatarUrl,
} = window.SeeMusicApp;

const evaluationState = {
    referenceFile: null,
    userFile: null,
    analysis: null,
    pitchComparison: null,
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
        renderPitchComparison();
        return;
    }

    const totalScore = Math.round(Number(analysis.score || 0));
    const label = scoreLabel(totalScore);
    const consistencyValue = analysis.consistency_ratio ?? analysis.user_consistency ?? 0;
    const coverageValue = analysis.coverage_ratio ?? 0;
    const errorSummary = `${analysis.missing_beats || 0} / ${analysis.extra_beats || 0}`;

    // Compute combined score if pitch comparison is available
    const pitchSummary = evaluationState.pitchComparison?.summary;
    let displayScore = Math.round(Number(analysis.overall_score ?? totalScore));
    if (pitchSummary && typeof pitchSummary.accuracy === "number") {
        const rhythmScore = totalScore;
        const pitchScore = Math.round(pitchSummary.accuracy);
        displayScore = Math.round(rhythmScore * 0.5 + pitchScore * 0.5);
    }
    const displayLabel = scoreLabel(displayScore);

    document.getElementById("analysis-id-display").textContent = analysis.analysis_id || "--";
    document.getElementById("analysis-ref-display").textContent = evaluationState.referenceFile?.name || "--";
    document.getElementById("analysis-user-bpm").textContent = analysis.user_bpm ? String(Math.round(Number(analysis.user_bpm))) : "--";
    document.getElementById("analysis-reference-bpm").textContent = analysis.reference_bpm ? String(Math.round(Number(analysis.reference_bpm))) : "--";
    document.getElementById("analysis-beat-summary").textContent = errorSummary;
    document.getElementById("evaluation-feedback").textContent = summarizeFeedback(analysis);

    document.getElementById("report-score").textContent = String(displayScore);
    document.getElementById("report-grade").textContent = displayLabel.text;
    document.getElementById("report-grade").className = `ml-auto px-3 py-1 rounded-full text-xs font-bold ${displayLabel.className}`;
    document.getElementById("metric-accuracy").textContent = percentText(analysis.timing_accuracy);
    document.getElementById("metric-coverage").textContent = percentText(coverageValue);
    document.getElementById("metric-consistency").textContent = percentText(consistencyValue);
    document.getElementById("metric-deviation").textContent = `${Math.round(Number(analysis.mean_deviation_ms || 0))} ms`;
    document.getElementById("bar-accuracy").style.width = `${Math.min(toPercent(analysis.timing_accuracy), 100)}%`;
    document.getElementById("bar-coverage").style.width = `${Math.min(toPercent(coverageValue), 100)}%`;
    document.getElementById("bar-consistency").style.width = `${Math.min(toPercent(consistencyValue), 100)}%`;
    document.getElementById("last-analysis-time").textContent = new Date().toLocaleString("zh-CN");

    renderErrorList(analysis.error_classification);
    renderPitchComparison();
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

function renderPitchComparison() {
    const comparison = evaluationState.pitchComparison;
    if (!comparison) {
        document.getElementById("pitch-accuracy").textContent = "--";
        document.getElementById("pitch-avg-cents").textContent = "--";
        document.getElementById("pitch-within-25").textContent = "--";
        document.getElementById("pitch-within-50").textContent = "--";
        document.getElementById("metric-pitch-accuracy").textContent = "--";
        document.getElementById("bar-pitch-accuracy").style.width = "0%";
        clearPitchCanvas();
        return;
    }

    const summary = comparison.summary || {};
    const accuracy = Math.round(Number(summary.accuracy || 0));
    document.getElementById("pitch-accuracy").textContent = `${accuracy}%`;
    document.getElementById("pitch-avg-cents").textContent = String(Math.round(Number(summary.average_deviation_cents || 0)));
    document.getElementById("pitch-within-25").textContent = percentText(summary.within_25_cents_ratio || 0);
    document.getElementById("pitch-within-50").textContent = percentText(summary.within_50_cents_ratio || 0);
    document.getElementById("metric-pitch-accuracy").textContent = `${accuracy}%`;
    document.getElementById("bar-pitch-accuracy").style.width = `${Math.min(accuracy, 100)}%`;

    drawPitchCurve(comparison);
}

function clearPitchCanvas() {
    const canvas = document.getElementById("pitch-curve-canvas");
    if (!canvas) {
        return;
    }
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#9ca3af";
    ctx.font = "13px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("完成一次评估后，这里将展示音高对比曲线。", canvas.width / 2, canvas.height / 2);
}

function drawPitchCurve(comparison) {
    const canvas = document.getElementById("pitch-curve-canvas");
    if (!canvas) {
        return;
    }
    const ctx = canvas.getContext("2d");
    const xAxis = comparison.x_axis || [];
    const refCurve = comparison.reference_curve || [];
    const userCurve = comparison.user_curve || [];
    const devCurve = comparison.deviation_cents_curve || [];

    if (!xAxis.length) {
        clearPitchCanvas();
        return;
    }

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const W = rect.width;
    const H = rect.height;

    ctx.clearRect(0, 0, W, H);

    const PAD_LEFT = 50;
    const PAD_RIGHT = 16;
    const PAD_TOP = 12;
    const PAD_BOTTOM = 24;
    const plotW = W - PAD_LEFT - PAD_RIGHT;
    const plotH = H - PAD_TOP - PAD_BOTTOM;

    const allFreqs = [...refCurve, ...userCurve].filter((v) => v > 0);
    if (!allFreqs.length) {
        clearPitchCanvas();
        return;
    }
    const freqMin = Math.max(Math.min(...allFreqs) - 20, 0);
    const freqMax = Math.max(...allFreqs) + 20;
    const tMin = xAxis[0];
    const tMax = xAxis[xAxis.length - 1];
    const tRange = tMax - tMin || 1;
    const fRange = freqMax - freqMin || 1;

    function tx(t) {
        return PAD_LEFT + ((t - tMin) / tRange) * plotW;
    }
    function ty(f) {
        return PAD_TOP + plotH - ((f - freqMin) / fRange) * plotH;
    }

    // grid lines
    ctx.strokeStyle = "#e5e7eb";
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
        const y = PAD_TOP + (plotH / 4) * i;
        ctx.beginPath();
        ctx.moveTo(PAD_LEFT, y);
        ctx.lineTo(PAD_LEFT + plotW, y);
        ctx.stroke();
        ctx.fillStyle = "#9ca3af";
        ctx.font = "10px sans-serif";
        ctx.textAlign = "right";
        const freqLabel = Math.round(freqMax - (fRange / 4) * i);
        ctx.fillText(`${freqLabel}`, PAD_LEFT - 4, y + 3);
    }

    // time labels
    ctx.textAlign = "center";
    ctx.fillStyle = "#9ca3af";
    const timeSteps = Math.min(6, xAxis.length);
    for (let i = 0; i <= timeSteps; i++) {
        const t = tMin + (tRange / timeSteps) * i;
        ctx.fillText(`${t.toFixed(1)}s`, tx(t), H - 4);
    }

    function drawCurve(curve, color, lineWidth) {
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        ctx.beginPath();
        let started = false;
        for (let i = 0; i < xAxis.length; i++) {
            const freq = curve[i];
            if (!freq || freq <= 0) {
                started = false;
                continue;
            }
            const x = tx(xAxis[i]);
            const y = ty(freq);
            if (!started) {
                ctx.moveTo(x, y);
                started = true;
            } else {
                ctx.lineTo(x, y);
            }
        }
        ctx.stroke();
    }

    drawCurve(refCurve, "#457b9d", 2);
    drawCurve(userCurve, "#e76f51", 1.5);

    // deviation area
    if (devCurve.length) {
        const maxDev = Math.max(...devCurve.map((v) => Math.abs(v || 0)), 1);
        ctx.fillStyle = "rgba(42, 157, 143, 0.12)";
        ctx.beginPath();
        const midY = PAD_TOP + plotH / 2;
        ctx.moveTo(tx(xAxis[0]), midY);
        for (let i = 0; i < xAxis.length; i++) {
            const devH = ((devCurve[i] || 0) / maxDev) * (plotH / 4);
            ctx.lineTo(tx(xAxis[i]), midY - devH);
        }
        ctx.lineTo(tx(xAxis[xAxis.length - 1]), midY);
        ctx.closePath();
        ctx.fill();
    }
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

function setSelectedFile(kind, file) {
    const stateKey = kind === "reference" ? "referenceFile" : "userFile";
    const labelId = kind === "reference" ? "reference-file-name" : "user-file-name";
    evaluationState[stateKey] = file || null;
    document.getElementById(labelId).textContent = file
        ? `${file.name} (${Math.round(file.size / 1024)} KB)`
        : (kind === "reference" ? "尚未选择标准音频" : "尚未选择用户音频");
}

async function runEvaluation() {
    const referenceFile = evaluationState.referenceFile;
    const userFile = evaluationState.userFile;
    const userAudioMode = document.getElementById("user-audio-mode").value;
    const language = document.getElementById("evaluation-language").value;
    const scoringModel = document.getElementById("evaluation-model").value;
    const threshold = document.getElementById("evaluation-threshold").value;
    const submitBtn = document.getElementById("evaluation-submit-btn");

    if (!referenceFile) {
        setBanner("evaluation-status", "请先选择标准 WAV 音频。", true);
        return;
    }
    if (!userFile) {
        setBanner("evaluation-status", "请先选择用户 WAV 音频。", true);
        return;
    }
    if (!referenceFile.name.toLowerCase().endsWith(".wav") || !userFile.name.toLowerCase().endsWith(".wav")) {
        setBanner("evaluation-status", "当前歌唱评估流程只接受 WAV 文件。", true);
        return;
    }

    const formData = new FormData();
    formData.append("reference_audio", referenceFile);
    formData.append("user_audio", userFile);
    formData.append("user_audio_mode", userAudioMode);
    formData.append("language", language);
    formData.append("scoring_model", scoringModel);
    formData.append("threshold_ms", threshold || "50");
    formData.append("separation_model", "demucs");

    submitBtn.disabled = true;
    submitBtn.style.opacity = "0.7";
    setBanner("evaluation-status", "正在分离标准音频人声并准备歌唱评估，请稍候...");

    try {
        const payload = await requestJson("/singing/evaluate", {
            method: "POST",
            body: formData,
        });
        evaluationState.analysis = {
            ...(payload.rhythm || {}),
            analysis_id: payload.analysis_id,
            overall_score: payload.overall_score,
            score: payload.score,
            user_audio_mode: payload.user_audio_mode,
            reference_separation: payload.reference_separation,
            user_separation: payload.user_separation,
        };
        evaluationState.pitchComparison = payload.pitch_comparison || null;
        evaluationState.report = null;

        renderAnalysis();
        const analysisId = payload.analysis_id;
        const userModeText = userAudioMode === "with_accompaniment" ? "用户音频已分离人声" : "用户清唱直接评估";
        setBanner("evaluation-status", `分析完成，analysis_id=${analysisId}。标准音频已分离人声，${userModeText}，音高与节奏评估已完成。`);
        await saveHistory({
            type: "audio",
            resource_id: payload.analysis_id,
            title: `歌唱评估：${userFile.name}`,
            metadata: {
                reference_file: referenceFile.name,
                user_audio_mode: userAudioMode,
                score: Math.round(Number(payload.overall_score || payload.score || 0)),
                language,
                scoring_model: scoringModel,
            },
        });
    } catch (error) {
        setBanner("evaluation-status", error.message || "歌唱评估失败，请检查 WAV 文件或后端分离配置。", true);
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
        const exportBody = {
            analysis_id: analysis.analysis_id,
            formats: ["pdf"],
            include_charts: true,
        };
        const rhythmScore = typeof analysis.score === "number" ? analysis.score : null;
        const pitchSummary = evaluationState.pitchComparison?.summary;
        const pitchScore = pitchSummary ? Math.round(Number(pitchSummary.accuracy || 0)) : null;
        if (rhythmScore != null) exportBody.rhythm_score = rhythmScore;
        if (pitchScore != null) exportBody.pitch_score = pitchScore;
        if (rhythmScore != null && pitchScore != null) {
            exportBody.total_score = Math.round(rhythmScore * 0.5 + pitchScore * 0.5);
        }
        const payload = await requestJson("/reports/export", {
            method: "POST",
            body: exportBody,
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
    bindSingleFileUpload("reference", "reference-file-input", "reference-dropzone");
    bindSingleFileUpload("user", "user-file-input", "user-dropzone");
}

function bindSingleFileUpload(kind, inputId, dropzoneId) {
    const input = document.getElementById(inputId);
    const dropzone = document.getElementById(dropzoneId);
    dropzone.addEventListener("click", () => input.click());
    input.addEventListener("change", () => {
        const file = input.files && input.files[0];
        setSelectedFile(kind, file || null);
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
        setSelectedFile(kind, file);
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
clearPitchCanvas();
bindEvents();
