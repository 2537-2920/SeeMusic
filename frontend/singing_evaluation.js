const {
    requestJson,
    getCurrentUser,
    getAuthToken,
    buildServerUrl,
    avatarUrl,
} = window.SeeMusicApp;

const evaluationState = {
    referenceFile: null,
    selectedReferenceTrack: null,
    userFile: null,
    analysis: null,
    pitchComparison: null,
    report: null,
    referenceSearchTimer: null,
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

function referenceDisplayName(track = evaluationState.selectedReferenceTrack, fallbackFile = evaluationState.referenceFile) {
    if (track) {
        return `${track.song_name || "未知歌曲"}${track.artist_name ? ` - ${track.artist_name}` : ""}`;
    }
    return fallbackFile ? fallbackFile.name : "--";
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
    document.getElementById("analysis-ref-display").textContent = referenceDisplayName();
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

    renderErrorList(analysis.error_classification, analysis);
    renderPitchComparison();
}

function renderErrorList(errorClassification, analysis = null) {
    const container = document.getElementById("rhythm-error-list");
    if (!errorClassification || typeof errorClassification !== "object" || !Object.keys(errorClassification).length) {
        container.innerHTML = `
            <div class="p-4 rounded-xl border border-gray-100 bg-white flex-1 min-w-[200px] text-sm text-gray-500">
                本次分析未返回结构化误差分类，可重点参考上方综合建议。
            </div>
        `;
        return;
    }

    const earlyBeats = Array.isArray(errorClassification.early_beats) ? errorClassification.early_beats : [];
    const lateBeats = Array.isArray(errorClassification.late_beats) ? errorClassification.late_beats : [];
    const onTime = Number(errorClassification.on_time || 0);
    const early = Number(errorClassification.early || 0);
    const late = Number(errorClassification.late || 0);

    const maxBeatIndex = Math.max(
        -1,
        ...earlyBeats.map((item) => Number(item && item.beat_index)),
        ...lateBeats.map((item) => Number(item && item.beat_index)),
    );
    const inferredTotal = Math.max(8, Math.round(onTime + early + late), maxBeatIndex + 1);
    const totalBeats = Number.isFinite(Number(analysis && analysis.total_ref_beats))
        ? Math.max(inferredTotal, Math.round(Number(analysis.total_ref_beats)))
        : inferredTotal;
    const referenceBpm = Number(analysis && analysis.reference_bpm);

    container.innerHTML = `
        <div class="p-4 rounded-xl border border-gray-100 bg-white w-full">
            <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
                <div class="text-sm font-bold text-gray-700">节奏时间轴对比</div>
                <div class="text-xs text-gray-500">准点 ${Math.round(onTime)} / 提前 ${Math.round(early)} / 延后 ${Math.round(late)}</div>
            </div>
            <div class="rounded-xl border border-gray-100 bg-gray-50 p-3">
                <canvas id="rhythm-waveform-canvas" width="960" height="220" style="width:100%;height:220px;display:block;"></canvas>
            </div>
            <div class="flex flex-wrap gap-4 mt-3 text-xs text-gray-500">
                <span class="flex items-center gap-2"><span style="display:inline-block;width:18px;height:2px;background:#dc2626;"></span>理想节奏（红）</span>
                <span class="flex items-center gap-2"><span style="display:inline-block;width:18px;height:2px;background:#2563eb;"></span>实际节奏（蓝）</span>
                <span>${Number.isFinite(referenceBpm) && referenceBpm > 0 ? `参考 BPM: ${Math.round(referenceBpm)}` : "时间轴: 按节拍序号"}</span>
            </div>
        </div>
    `;

    drawRhythmWaveformChart({
        earlyBeats,
        lateBeats,
        totalBeats,
        referenceBpm,
    });
}

function drawRhythmWaveformChart({ earlyBeats, lateBeats, totalBeats, referenceBpm }) {
    const canvas = document.getElementById("rhythm-waveform-canvas");
    if (!canvas) {
        return;
    }
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = Math.max(1, rect.width * dpr);
    canvas.height = Math.max(1, rect.height * dpr);
    ctx.scale(dpr, dpr);

    const W = rect.width;
    const H = rect.height;
    ctx.clearRect(0, 0, W, H);

    const PAD_L = 40;
    const PAD_R = 14;
    const PAD_T = 16;
    const PAD_B = 24;
    const plotW = W - PAD_L - PAD_R;
    const plotH = H - PAD_T - PAD_B;
    const midY = PAD_T + plotH * 0.5;
    const beatCount = Math.max(2, Number(totalBeats) || 2);

    const deviations = new Array(beatCount).fill(0);
    for (const item of earlyBeats || []) {
        const idx = Number(item && item.beat_index);
        const dev = Number(item && item.deviation_ms);
        if (Number.isFinite(idx) && idx >= 0 && idx < beatCount && Number.isFinite(dev)) {
            deviations[Math.round(idx)] = dev;
        }
    }
    for (const item of lateBeats || []) {
        const idx = Number(item && item.beat_index);
        const dev = Number(item && item.deviation_ms);
        if (Number.isFinite(idx) && idx >= 0 && idx < beatCount && Number.isFinite(dev)) {
            deviations[Math.round(idx)] = dev;
        }
    }

    const maxAbs = Math.max(60, ...deviations.map((v) => Math.abs(v)));
    const amp = plotH * 0.34;

    function tx(i) {
        if (beatCount <= 1) return PAD_L;
        return PAD_L + (i / (beatCount - 1)) * plotW;
    }
    function ty(devMs) {
        return midY - (devMs / maxAbs) * amp;
    }

    ctx.strokeStyle = "#e5e7eb";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = PAD_T + (plotH / 4) * i;
        ctx.beginPath();
        ctx.moveTo(PAD_L, y);
        ctx.lineTo(PAD_L + plotW, y);
        ctx.stroke();
    }

    ctx.strokeStyle = "#dc2626";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(PAD_L, midY);
    ctx.lineTo(PAD_L + plotW, midY);
    ctx.stroke();

    ctx.strokeStyle = "#2563eb";
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < beatCount; i++) {
        const x = tx(i);
        const y = ty(deviations[i] || 0);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.stroke();

    ctx.fillStyle = "#2563eb";
    for (let i = 0; i < beatCount; i++) {
        const x = tx(i);
        const y = ty(deviations[i] || 0);
        ctx.beginPath();
        ctx.arc(x, y, 2.2, 0, Math.PI * 2);
        ctx.fill();
    }

    ctx.fillStyle = "#9ca3af";
    ctx.font = "10px sans-serif";
    ctx.textAlign = "center";
    const ticks = Math.min(6, beatCount - 1);
    for (let i = 0; i <= ticks; i++) {
        const idx = Math.round((i / Math.max(1, ticks)) * (beatCount - 1));
        const x = tx(idx);
        let label = `Beat ${idx + 1}`;
        if (Number.isFinite(referenceBpm) && referenceBpm > 0) {
            const sec = (idx * 60) / referenceBpm;
            label = `${sec.toFixed(1)}s`;
        }
        ctx.fillText(label, x, H - 6);
    }
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

function audioFileNameFromUrl(audioUrl) {
    const raw = String(audioUrl || "").split("?")[0].split("#")[0];
    const name = raw.split("/").filter(Boolean).pop() || "";
    try {
        return decodeURIComponent(name);
    } catch {
        return name;
    }
}

function triggerFileDownload(url, fileName = "") {
    if (!url) {
        return;
    }
    const link = document.createElement("a");
    link.href = buildServerUrl(url);
    if (fileName) {
        link.download = fileName;
    }
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
}

function renderReferenceSearchResults(items, message = "") {
    const container = document.getElementById("reference-search-results");
    if (!container) {
        return;
    }
    if (message) {
        container.innerHTML = `
            <div class="text-xs text-gray-400 p-3 border border-dashed border-gray-200 rounded-xl bg-white">
                ${escapeHtml(message)}
            </div>
        `;
        return;
    }
    if (!items || !items.length) {
        container.innerHTML = `
            <div class="text-xs text-gray-400 p-3 border border-dashed border-gray-200 rounded-xl bg-white">
                未找到参考歌曲，可换关键词或手动上传标准音频。
            </div>
        `;
        return;
    }
    container.innerHTML = items.map((track) => `
        <button class="w-full text-left p-3 rounded-xl border border-gray-100 bg-white hover:border-blue-200 hover:bg-blue-50 transition-colors reference-result-btn" type="button" data-ref-id="${escapeHtml(track.ref_id)}">
            <div class="flex items-start justify-between gap-3">
                <div>
                    <div class="text-sm font-bold text-gray-700">${escapeHtml(track.song_name || "未知歌曲")}</div>
                    <div class="text-xs text-gray-500 mt-1">${escapeHtml(track.artist_name || "未知歌手")}</div>
                </div>
                <div class="text-[10px] text-gray-400 max-w-[160px] truncate">${escapeHtml(audioFileNameFromUrl(track.audio_url))}</div>
            </div>
        </button>
    `).join("");
    container.querySelectorAll(".reference-result-btn").forEach((button) => {
        button.addEventListener("click", () => {
            const refId = button.getAttribute("data-ref-id");
            const selected = items.find((track) => track.ref_id === refId);
            if (selected) {
                selectReferenceTrack(selected);
            }
        });
    });
}

function selectReferenceTrack(track) {
    evaluationState.selectedReferenceTrack = track || null;
    evaluationState.referenceFile = null;
    const input = document.getElementById("reference-file-input");
    if (input) {
        input.value = "";
    }
    const card = document.getElementById("selected-reference-card");
    const title = document.getElementById("selected-reference-title");
    const meta = document.getElementById("selected-reference-meta");
    if (track) {
        card.classList.remove("hidden");
        title.textContent = referenceDisplayName(track, null);
        meta.textContent = `${track.ref_id} · ${audioFileNameFromUrl(track.audio_url)}`;
        document.getElementById("reference-file-name").textContent = referenceDisplayName(track, null);
        setBanner("evaluation-status", "");
    } else {
        card.classList.add("hidden");
        title.textContent = "--";
        meta.textContent = "--";
        document.getElementById("reference-file-name").textContent = "尚未选择标准歌曲或上传音频";
    }
}

async function searchReferenceTracks() {
    const input = document.getElementById("reference-search-input");
    const keyword = (input && input.value ? input.value : "").trim();
    if (!keyword) {
        renderReferenceSearchResults([], "请输入歌曲名、歌手或关键词。");
        return;
    }
    renderReferenceSearchResults([], "正在搜索参考曲库...");
    try {
        const payload = await requestJson(`/reference-tracks/search?keyword=${encodeURIComponent(keyword)}&limit=10`);
        renderReferenceSearchResults(payload.items || []);
    } catch (error) {
        renderReferenceSearchResults([], error.message || "参考歌曲搜索失败。");
    }
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
    if (kind === "reference" && file) {
        selectReferenceTrack(null);
        evaluationState.referenceFile = file;
    }
    document.getElementById(labelId).textContent = file
        ? `${file.name} (${Math.round(file.size / 1024)} KB)`
        : (kind === "reference" ? "尚未选择标准歌曲或上传音频" : "尚未选择用户音频");
}

function isSupportedAudioFile(fileName) {
    return /\.(wav|mp3|m4a|ogg|flac|aac|opus|webm)$/i.test(fileName || "");
}

async function runEvaluation() {
    const referenceFile = evaluationState.referenceFile;
    const selectedReferenceTrack = evaluationState.selectedReferenceTrack;
    const userFile = evaluationState.userFile;
    const userAudioMode = document.getElementById("user-audio-mode").value;
    const language = document.getElementById("evaluation-language").value;
    const scoringModel = document.getElementById("evaluation-model").value;
    const threshold = document.getElementById("evaluation-threshold").value;
    const submitBtn = document.getElementById("evaluation-submit-btn");

    if (!selectedReferenceTrack && !referenceFile) {
        setBanner("evaluation-status", "请先搜索并选择标准歌曲，或手动上传标准音频。", true);
        return;
    }
    if (!userFile) {
        setBanner("evaluation-status", "请先选择用户 WAV 音频。", true);
        return;
    }
    if (referenceFile && !isSupportedAudioFile(referenceFile.name)) {
        setBanner("evaluation-status", "标准音频格式需为 WAV、MP3、M4A、OGG 或 FLAC。", true);
        return;
    }
    if (!isSupportedAudioFile(userFile.name)) {
        setBanner("evaluation-status", "用户音频格式需为 WAV、MP3、M4A、OGG 或 FLAC。", true);
        return;
    }

    const formData = new FormData();
    if (selectedReferenceTrack) {
        formData.append("reference_ref_id", selectedReferenceTrack.ref_id);
    } else {
        formData.append("reference_audio", referenceFile);
    }
    formData.append("user_audio", userFile);
    formData.append("user_audio_mode", userAudioMode);
    formData.append("language", language);
    formData.append("scoring_model", scoringModel);
    formData.append("threshold_ms", threshold || "50");
    formData.append("separation_model", "demucs");

    submitBtn.disabled = true;
    submitBtn.style.opacity = "0.7";
    setBanner("evaluation-status", "正在准备标准歌曲人声并进行歌唱评估，请稍候...");

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
            reference_track: payload.reference_track || selectedReferenceTrack || null,
            resolved_ref_id: payload.resolved_ref_id || selectedReferenceTrack?.ref_id || null,
            reference_separation: payload.reference_separation,
            user_separation: payload.user_separation,
        };
        if (payload.reference_track) {
            evaluationState.selectedReferenceTrack = payload.reference_track;
        }
        evaluationState.pitchComparison = payload.pitch_comparison || null;
        evaluationState.report = null;

        renderAnalysis();
        const analysisId = payload.analysis_id;
        const userModeText = userAudioMode === "with_accompaniment" ? "用户音频已分离人声" : "用户清唱直接评估";
        setBanner("evaluation-status", `分析完成，analysis_id=${analysisId}。标准歌曲已准备人声，${userModeText}，音高与节奏评估已完成。`);
        const referenceTrackForHistory = payload.reference_track || selectedReferenceTrack || null;
        await saveHistory({
            type: "audio",
            resource_id: payload.analysis_id,
            title: `歌唱评估：${userFile.name}`,
            metadata: {
                reference_file: referenceFile ? referenceFile.name : null,
                reference_ref_id: payload.resolved_ref_id || referenceTrackForHistory?.ref_id || null,
                reference_track: referenceTrackForHistory ? {
                    song_name: referenceTrackForHistory.song_name,
                    artist_name: referenceTrackForHistory.artist_name,
                    audio_url: referenceTrackForHistory.audio_url,
                } : null,
                user_audio_mode: userAudioMode,
                score: Math.round(Number(payload.overall_score || payload.score || 0)),
                language,
                scoring_model: scoringModel,
            },
        });
    } catch (error) {
        setBanner("evaluation-status", error.message || "歌唱评估失败，请检查音频文件或后端分离配置。", true);
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
        const pdfFile = (payload.files || []).find((file) => file.format === "pdf") || (payload.files || [])[0];
        if (pdfFile) {
            triggerFileDownload(pdfFile.download_api_url || pdfFile.download_url, pdfFile.file_name || "");
        }
        setBanner("report-export-status", `报告已生成，report_id=${payload.report_id}，浏览器已开始下载。`);
        await saveHistory({
            type: "report",
            resource_id: payload.report_id,
            title: `导出评估报告：${analysis.analysis_id}`,
            metadata: {
                analysis_id: analysis.analysis_id,
                formats: "pdf",
                include_charts: true,
                download_url: pdfFile ? (pdfFile.download_api_url || pdfFile.download_url || "") : "",
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
    const referenceUploadBtn = document.getElementById("reference-upload-btn");
    const referenceInput = document.getElementById("reference-file-input");
    if (referenceUploadBtn && referenceInput) {
        referenceUploadBtn.addEventListener("click", () => referenceInput.click());
    }
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
    const searchInput = document.getElementById("reference-search-input");
    const searchBtn = document.getElementById("reference-search-btn");
    const clearBtn = document.getElementById("reference-clear-btn");
    if (searchBtn) {
        searchBtn.addEventListener("click", searchReferenceTracks);
    }
    if (searchInput) {
        searchInput.addEventListener("input", () => {
            window.clearTimeout(evaluationState.referenceSearchTimer);
            evaluationState.referenceSearchTimer = window.setTimeout(searchReferenceTracks, 350);
        });
        searchInput.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                window.clearTimeout(evaluationState.referenceSearchTimer);
                searchReferenceTracks();
            }
        });
    }
    if (clearBtn) {
        clearBtn.addEventListener("click", () => selectReferenceTrack(null));
    }
    document.getElementById("evaluation-submit-btn").addEventListener("click", runEvaluation);
    document.getElementById("report-export-btn").addEventListener("click", exportReport);
    document.getElementById("variation-submit-btn").addEventListener("click", loadVariations);
}

renderHeader();
renderAnalysis();
clearPitchCanvas();
bindEvents();
