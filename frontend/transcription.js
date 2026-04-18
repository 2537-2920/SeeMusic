const STORAGE_KEYS = {
    apiBase: "seemusic.transcription.apiBase",
    userId: "seemusic.transcription.userId",
    title: "seemusic.transcription.title",
    analysisId: "seemusic.transcription.analysisId",
    scoreId: "seemusic.transcription.scoreId",
    tempo: "seemusic.transcription.tempo",
    timeSignature: "seemusic.transcription.timeSignature",
    keySignature: "seemusic.transcription.keySignature",
    pitchSequence: "seemusic.transcription.pitchSequence",
};

const TRANSCRIPTION_UI_BUILD = "2026-04-17-paper-score-viewer";
const DEFAULT_BACKEND_ORIGIN = "http://127.0.0.1:8000";
const DEFAULT_API_BASE = `${DEFAULT_BACKEND_ORIGIN}/api/v1`;
const VIEWER_LAYOUT = window.SeeMusicScoreViewerLayout || {};
const VIEWER_LAYOUT_DEFAULTS = VIEWER_LAYOUT.DEFAULT_VIEWER_LAYOUT_OPTIONS || {
    minMeasuresPerSystem: 4,
    maxMeasuresPerSystem: 6,
    systemsPerPage: 5,
};
const VIEWER_A4_RATIO = 210 / 297;
const VIEWER_PAGE_TURN_MS = 440;
const VIEWER_DRAG_THRESHOLD = 0.18;
const VIEWER_WHEEL_THRESHOLD = 120;

const NOTE_INDEX = {
    C: 0,
    "C#": 1,
    D: 2,
    "D#": 3,
    E: 4,
    F: 5,
    "F#": 6,
    G: 7,
    "G#": 8,
    A: 9,
    "A#": 10,
    B: 11,
};

const SEMITONE_SEQUENCE = Object.keys(NOTE_INDEX);
const FLAT_TO_SHARP = { Db: "C#", Eb: "D#", Gb: "F#", Ab: "G#", Bb: "A#" };
const DEFAULT_SEQUENCE = [
    { time: 0.0, frequency: 440.0, duration: 0.5 },
    { time: 0.5, frequency: 493.88, duration: 0.5 },
    { time: 1.0, frequency: 523.25, duration: 0.5 },
    { time: 1.5, frequency: 587.33, duration: 0.5 },
    { time: 2.0, frequency: 659.25, duration: 1.0 },
];

const state = {
    apiBase: "",
    backendHealthy: false,
    currentScore: null,
    selectedScoreId: localStorage.getItem(STORAGE_KEYS.scoreId) || "",
    selectedNotationElementId: null,
    exportList: [],
    selectedExportRecordId: null,
    selectedExportDetail: null,
    beatDetectResult: null,
    separateTracksResult: null,
    chordGenerationResult: null,
    rhythmScoreResult: null,
    audioLogs: [],
    analysisToolsOpen: false,
    busyKeys: new Set(),
    scorePageIndex: 0,
    scoreViewerOpen: false,
    verovioReady: false,
    verovioLoading: false,
    verovioError: "",
    notationRenderTicket: 0,
    previewPageCount: 0,
    viewerPageCount: 0,
    viewerPageRanges: [],
    viewerPreparedKey: "",
    viewerPreparedMusicxml: "",
    viewerPreparedLayout: null,
    viewerPageCache: new Map(),
    viewerTransition: {
        phase: "idle",
        direction: 0,
        fromIndex: 0,
        toIndex: 0,
        progress: 0,
    },
    viewerGesture: null,
    viewerWheelAccumX: 0,
    viewerSuppressClickUntil: 0,
};

const els = {};

document.addEventListener("DOMContentLoaded", init);

function init() {
    cacheElements();
    hydrateInputs();
    bindEvents();
    state.analysisToolsOpen = Boolean(els.analysisToolsPanel?.open);
    setApiBase(els.apiBaseInput.value || resolveDefaultApiBase(), false);
    console.info(`[SeeMusic] transcription UI build: ${TRANSCRIPTION_UI_BUILD}`);
    renderAll();
    void ensureVerovioRuntime();
    void syncAuthenticatedUserId();
    void checkBackendConnection();
    if (state.selectedScoreId) {
        void loadCurrentScore(state.selectedScoreId, { silent: true });
    }
}

function cacheElements() {
    [
        "api-base-input",
        "save-api-base-btn",
        "ping-backend-btn",
        "backend-status-dot",
        "backend-status-text",
        "score-linkage-status",
        "user-id-input",
        "project-title-input",
        "analysis-id-input",
        "tempo-input",
        "time-signature-input",
        "key-signature-input",
        "pitch-sequence-input",
        "load-sample-btn",
        "clear-sequence-btn",
        "create-score-btn",
        "analysis-file-input",
        "beat-bpm-hint-input",
        "beat-sensitivity-input",
        "separation-model-input",
        "separation-stems-input",
        "chord-style-input",
        "rhythm-language-input",
        "rhythm-model-input",
        "rhythm-threshold-input",
        "reference-beats-input",
        "user-beats-input",
        "pitch-detect-file-input",
        "pitch-detect-algorithm-input",
        "pitch-detect-frame-ms-input",
        "pitch-detect-hop-ms-input",
        "pitch-detect-btn",
        "pitch-detect-and-score-btn",
        "pitch-detect-status",
        "analysis-tools-panel",
        "beat-detect-btn",
        "separate-tracks-btn",
        "generate-chords-btn",
        "rhythm-score-btn",
        "refresh-audio-logs-btn",
        "beat-detect-output",
        "separate-tracks-output",
        "generate-chords-output",
        "rhythm-score-output",
        "score-title-display",
        "score-id-badge",
        "project-id-badge",
        "score-version-badge",
        "apply-score-settings-btn",
        "undo-btn",
        "redo-btn",
        "download-musicxml-btn",
        "refresh-score-btn",
        "selected-note-summary",
        "score-musicxml-file-input",
        "replace-score-from-file-btn",
        "load-score-file-into-editor-btn",
        "score-musicxml-input",
        "tempo-display",
        "time-display",
        "key-display",
        "measure-count-display",
        "score-empty",
        "score-viewer-entry",
        "open-score-viewer-btn",
        "score-viewer-overlay",
        "close-score-viewer-btn",
        "score-viewer-stage",
        "score-viewer-page-prev-btn",
        "score-viewer-page-next-btn",
        "score-viewer-page-status",
        "score-viewer-page-range",
        "score-viewer-score-title",
        "score-viewer-score-subtitle",
        "score-viewer-empty",
        "score-viewer-canvas",
        "export-format-select",
        "export-page-size-select",
        "export-annotations-input",
        "create-export-btn",
        "regenerate-selected-export-btn",
        "download-selected-export-btn",
        "delete-selected-export-btn",
        "refresh-exports-btn",
        "export-count-badge",
        "export-empty",
        "export-list",
        "audio-log-count-badge",
        "audio-log-empty",
        "audio-log-list",
        "preview-title",
        "detail-format",
        "detail-size",
        "detail-updated",
        "detail-status",
        "preview-stage",
        "preview-empty",
        "app-status",
    ].forEach((id) => {
        const key = id.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
        els[key] = document.getElementById(id);
    });
}

function hydrateInputs() {
    els.apiBaseInput.value = loadPreferredApiBase();
    els.userIdInput.value = String(resolveCachedScoreOwnerUserId() || localStorage.getItem(STORAGE_KEYS.userId) || "");
    els.projectTitleInput.value = localStorage.getItem(STORAGE_KEYS.title) || "我的智能识谱项目";
    els.analysisIdInput.value = localStorage.getItem(STORAGE_KEYS.analysisId) || "";
    els.tempoInput.value = localStorage.getItem(STORAGE_KEYS.tempo) || "120";
    els.timeSignatureInput.value = localStorage.getItem(STORAGE_KEYS.timeSignature) || "4/4";
    els.keySignatureInput.value = localStorage.getItem(STORAGE_KEYS.keySignature) || "C";
    els.pitchSequenceInput.value =
        localStorage.getItem(STORAGE_KEYS.pitchSequence) || JSON.stringify(DEFAULT_SEQUENCE, null, 2);
    els.pitchDetectAlgorithmInput.value = "yin";
    els.pitchDetectFrameMsInput.value = "20";
    els.pitchDetectHopMsInput.value = "10";
    if (els.scoreMusicxmlInput) {
        els.scoreMusicxmlInput.value = "";
    }
}

function loadPreferredApiBase() {
    const storedValue = localStorage.getItem(STORAGE_KEYS.apiBase);
    if (!storedValue) {
        return resolveDefaultApiBase();
    }

    const normalizedStoredValue = normalizeApiBase(storedValue);
    try {
        const storedUrl = new URL(normalizedStoredValue);
        const isLocalHost = ["localhost", "127.0.0.1", "0.0.0.0", "::1"].includes(storedUrl.hostname);
        if (isLocalHost && storedUrl.port !== "8000") {
            return resolveDefaultApiBase();
        }
    } catch {
        return resolveDefaultApiBase();
    }
    return normalizedStoredValue;
}

function resolveNumericUserId(value) {
    const text = String(value || "").trim();
    if (!/^\d+$/.test(text)) {
        return null;
    }
    const parsed = Number.parseInt(text, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function resolveCachedScoreOwnerUserId() {
    const appCommon = window.SeeMusicApp;
    const cachedUser = appCommon && typeof appCommon.getCurrentUser === "function" ? appCommon.getCurrentUser() : null;
    return resolveNumericUserId(cachedUser?.user_id);
}

function persistScoreOwnerUserId(userId) {
    const normalizedUserId = resolveNumericUserId(userId);
    if (!normalizedUserId) {
        return null;
    }
    els.userIdInput.value = String(normalizedUserId);
    localStorage.setItem(STORAGE_KEYS.userId, String(normalizedUserId));
    return normalizedUserId;
}

async function syncAuthenticatedUserId() {
    const cachedUserId = resolveCachedScoreOwnerUserId();
    if (cachedUserId) {
        persistScoreOwnerUserId(cachedUserId);
        return cachedUserId;
    }

    const appCommon = window.SeeMusicApp;
    if (!appCommon || typeof appCommon.getAuthToken !== "function" || !appCommon.getAuthToken()) {
        return resolveNumericUserId(els.userIdInput.value);
    }
    if (typeof appCommon.requestJson !== "function") {
        return resolveNumericUserId(els.userIdInput.value);
    }

    try {
        const currentUser = await appCommon.requestJson("/users/me");
        return persistScoreOwnerUserId(currentUser?.user_id);
    } catch {
        return resolveNumericUserId(els.userIdInput.value);
    }
}

async function ensureScoreOwnerUserId() {
    const syncedUserId = await syncAuthenticatedUserId();
    if (syncedUserId) {
        return syncedUserId;
    }

    const fallbackUserId = resolveNumericUserId(els.userIdInput.value || localStorage.getItem(STORAGE_KEYS.userId));
    if (fallbackUserId) {
        return persistScoreOwnerUserId(fallbackUserId);
    }

    throw new Error("当前未找到可用的登录用户，请先登录后再生成乐谱");
}

function bindEvents() {
    els.saveApiBaseBtn.addEventListener("click", handleSaveApiBase);
    els.pingBackendBtn.addEventListener("click", checkBackendConnection);
    els.loadSampleBtn.addEventListener("click", loadSampleSequence);
    els.clearSequenceBtn.addEventListener("click", handleClearSequence);
    els.createScoreBtn.addEventListener("click", handleCreateScore);
    els.pitchDetectBtn.addEventListener("click", handlePitchDetect);
    els.pitchDetectAndScoreBtn.addEventListener("click", handlePitchDetectAndScore);
    els.beatDetectBtn.addEventListener("click", handleBeatDetect);
    els.separateTracksBtn.addEventListener("click", handleSeparateTracks);
    els.generateChordsBtn.addEventListener("click", handleGenerateChords);
    els.rhythmScoreBtn.addEventListener("click", handleRhythmScore);
    els.refreshAudioLogsBtn.addEventListener("click", () => loadAudioLogs());
    els.applyScoreSettingsBtn.addEventListener("click", handleApplyScoreSettings);
    els.undoBtn.addEventListener("click", handleUndo);
    els.redoBtn.addEventListener("click", handleRedo);
    els.downloadMusicxmlBtn.addEventListener("click", handleDownloadMusicxml);
    els.refreshScoreBtn.addEventListener("click", handleRefreshScore);
    els.replaceScoreFromFileBtn.addEventListener("click", handleReplaceScoreFromFile);
    els.loadScoreFileIntoEditorBtn.addEventListener("click", handleLoadScoreFileIntoEditor);
    els.openScoreViewerBtn.addEventListener("click", openScoreViewer);
    els.closeScoreViewerBtn.addEventListener("click", closeScoreViewer);
    els.scoreViewerPagePrevBtn.addEventListener("click", () => changeScorePage(-1));
    els.scoreViewerPageNextBtn.addEventListener("click", () => changeScorePage(1));
    els.scoreViewerCanvas.addEventListener("click", handleScoreCanvasInteraction);
    els.scoreViewerEntry.addEventListener("click", handleScoreCanvasInteraction);
    els.scoreViewerStage.addEventListener("pointerdown", handleViewerPointerDown);
    els.scoreViewerStage.addEventListener("wheel", handleViewerWheel, { passive: false });
    els.createExportBtn.addEventListener("click", handleCreateExport);
    els.refreshExportsBtn.addEventListener("click", () => loadExportList(state.selectedExportRecordId));
    els.regenerateSelectedExportBtn.addEventListener("click", handleRegenerateSelectedExport);
    els.downloadSelectedExportBtn.addEventListener("click", handleDownloadSelectedExport);
    els.deleteSelectedExportBtn.addEventListener("click", handleDeleteSelectedExport);
    els.exportList.addEventListener("click", handleExportListClick);
    els.analysisToolsPanel?.addEventListener("toggle", () => {
        state.analysisToolsOpen = els.analysisToolsPanel.open;
    });
    window.addEventListener("resize", () => {
        if (state.currentScore) {
            scheduleNotationRender();
            if (state.scoreViewerOpen) {
                scheduleNotationRender({ viewerOnly: true });
            }
        }
    });
    window.addEventListener("pointermove", handleViewerPointerMove);
    window.addEventListener("pointerup", handleViewerPointerUp);
    window.addEventListener("pointercancel", handleViewerPointerUp);
    document.addEventListener("keydown", handleViewerKeydown);

    [
        [els.apiBaseInput, STORAGE_KEYS.apiBase],
        [els.userIdInput, STORAGE_KEYS.userId],
        [els.projectTitleInput, STORAGE_KEYS.title],
        [els.analysisIdInput, STORAGE_KEYS.analysisId],
        [els.tempoInput, STORAGE_KEYS.tempo],
        [els.timeSignatureInput, STORAGE_KEYS.timeSignature],
        [els.keySignatureInput, STORAGE_KEYS.keySignature],
        [els.pitchSequenceInput, STORAGE_KEYS.pitchSequence],
    ].forEach(([element, key]) => {
        element.addEventListener("input", () => localStorage.setItem(key, element.value));
    });
}

function handleViewerKeydown(event) {
    if (!state.scoreViewerOpen) {
        return;
    }
    if (event.key === "Escape") {
        closeScoreViewer();
        return;
    }
    if (event.key === "ArrowLeft") {
        event.preventDefault();
        changeScorePage(-1);
        return;
    }
    if (event.key === "ArrowRight") {
        event.preventDefault();
        changeScorePage(1);
    }
}

function resolveDefaultApiBase() {
    return DEFAULT_API_BASE;
}

function normalizeApiBase(rawValue) {
    let value = (rawValue || "").trim() || resolveDefaultApiBase();
    if (!/^https?:\/\//i.test(value)) {
        if (value.startsWith("/")) {
            value = `${DEFAULT_BACKEND_ORIGIN}${value}`;
        } else {
            value = `http://${value}`;
        }
    }
    value = value.replace(/\/+$/, "");
    if (!/\/api\/v\d+$/i.test(value)) {
        value = `${value}/api/v1`;
    }
    return value;
}

function apiOrigin() {
    try {
        return new URL(state.apiBase).origin;
    } catch {
        return "http://127.0.0.1:8000";
    }
}

function buildApiUrl(path = "") {
    if (/^https?:\/\//i.test(path)) {
        return path;
    }
    if (path.startsWith("/api/")) {
        return `${apiOrigin()}${path}`;
    }
    if (path.startsWith("/")) {
        return `${state.apiBase}${path}`;
    }
    return `${state.apiBase}/${path}`;
}

function buildServerUrl(path = "") {
    if (/^https?:\/\//i.test(path)) {
        return path;
    }
    return `${apiOrigin()}${path.startsWith("/") ? path : `/${path}`}`;
}

function setApiBase(value, persist = true) {
    state.apiBase = normalizeApiBase(value);
    els.apiBaseInput.value = state.apiBase;
    if (persist) {
        localStorage.setItem(STORAGE_KEYS.apiBase, state.apiBase);
    }
}

async function requestJson(path, options = {}) {
    const requestOptions = { method: "GET", headers: {}, ...options };

    // Inject auth header from app_common if available
    const appCommon = window.SeeMusicApp;
    if (appCommon && typeof appCommon.getAuthToken === "function") {
        const token = appCommon.getAuthToken();
        if (token) {
            requestOptions.headers.Authorization = `Bearer ${token}`;
        }
    }

    if (requestOptions.body !== undefined && !(requestOptions.body instanceof FormData)) {
        requestOptions.headers = { "Content-Type": "application/json", ...requestOptions.headers };
        requestOptions.body = JSON.stringify(requestOptions.body);
    }

    const response = await fetch(buildApiUrl(path), requestOptions);
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : await response.text();

    if (!response.ok) {
        const detail =
            (payload && typeof payload === "object" && (payload.detail || payload.message)) || response.statusText;
        throw new Error(detail || "请求失败");
    }
    if (payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "code")) {
        if (payload.code !== 0) {
            throw new Error(payload.message || "请求失败");
        }
        return payload.data;
    }
    return payload;
}

async function checkBackendConnection() {
    if (isBusy("ping")) {
        return;
    }
    setBusy("ping", true);
    try {
        const response = await fetch(buildServerUrl("/health"));
        const payload = await response.json();
        if (!response.ok || payload.status !== "ok") {
            throw new Error("健康检查失败");
        }
        state.backendHealthy = true;
        setAppStatus("服务连接正常，现在可以开始识谱和编辑。");
    } catch (error) {
        state.backendHealthy = false;
        setAppStatus(`服务暂不可用：${error.message}`, true);
    } finally {
        renderBackendState();
        setBusy("ping", false);
    }
}

function renderBackendState() {
    els.backendStatusDot.classList.remove("online", "offline");
    els.backendStatusText.textContent = state.backendHealthy ? "服务可用" : "服务未连接";
    els.backendStatusDot.classList.add(state.backendHealthy ? "online" : "offline");
}

function setAppStatus(message, isError = false) {
    els.appStatus.textContent = message;
    els.appStatus.style.color = isError ? "var(--danger)" : "var(--accent-strong)";
}

function setBusy(key, value) {
    if (value) {
        state.busyKeys.add(key);
    } else {
        state.busyKeys.delete(key);
    }
    renderControlState();
}

function isBusy(key) {
    return state.busyKeys.has(key);
}

function parsePitchSequence() {
    const parsed = JSON.parse(els.pitchSequenceInput.value);
    if (!Array.isArray(parsed) || parsed.length === 0) {
        throw new Error("音高序列 JSON 必须是非空数组");
    }
    return parsed;
}

function parseJsonArray(value, label) {
    let parsed;
    try {
        parsed = JSON.parse(value);
    } catch {
        throw new Error(`${label} 必须是有效的 JSON`);
    }
    if (!Array.isArray(parsed)) {
        throw new Error(`${label} 必须是 JSON 数组`);
    }
    return parsed.map((item) => Number(item));
}

function parsePositiveInteger(value, label) {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed) || parsed <= 0) {
        throw new Error(`${label} 必须是正整数`);
    }
    return parsed;
}

function parsePositiveNumber(value, label) {
    const parsed = Number.parseFloat(value);
    if (!Number.isFinite(parsed) || parsed <= 0) {
        throw new Error(`${label} 必须是正数`);
    }
    return parsed;
}

function normalizePitchInput(rawValue) {
    const value = (rawValue || "").trim();
    if (!value) {
        throw new Error("音高不能为空");
    }
    if (/^rest$/i.test(value)) {
        return "Rest";
    }
    const match = value.match(/^([A-Ga-g])([#b]?)(-?\d+)$/);
    if (!match) {
        throw new Error("音高格式应类似 C4、F#4、Bb3 或 Rest");
    }
    const letter = match[1].toUpperCase();
    const accidental = match[2] || "";
    const octave = match[3];
    const noteName = accidental === "b" ? FLAT_TO_SHARP[`${letter}b`] : `${letter}${accidental}`;
    if (!Object.prototype.hasOwnProperty.call(NOTE_INDEX, noteName)) {
        throw new Error("不支持的音高名称");
    }
    return `${noteName}${octave}`;
}

function buildNotePayloadFromInputs() {
    const measureNo = parsePositiveInteger(els.noteMeasureInput.value, "小节");
    const startBeat = quantizeBeat(parsePositiveNumber(els.noteBeatInput.value, "拍点"));
    const beats = quantizeBeat(parsePositiveNumber(els.noteBeatsInput.value, "时值"));
    const pitch = normalizePitchInput(els.notePitchInput.value);
    return {
        measureNo,
        note: {
            pitch,
            start_beat: startBeat,
            beats,
            is_rest: pitch === "Rest",
        },
    };
}

async function handleSaveApiBase() {
    try {
        setApiBase(els.apiBaseInput.value, true);
        setAppStatus(`服务地址已保存：${state.apiBase}`);
        await checkBackendConnection();
    } catch (error) {
        setAppStatus(error.message, true);
    }
}

function loadSampleSequence() {
    els.pitchSequenceInput.value = JSON.stringify(DEFAULT_SEQUENCE, null, 2);
    localStorage.setItem(STORAGE_KEYS.pitchSequence, els.pitchSequenceInput.value);
    setAppStatus("示例音高序列已载入，可以直接生成乐谱。");
}

function handleClearSequence() {
    els.pitchSequenceInput.value = "";
    localStorage.setItem(STORAGE_KEYS.pitchSequence, "");
    setAppStatus("音高序列输入已清空。");
}

function ensureAnalysisFile() {
    const file = els.analysisFileInput.files?.[0];
    if (!file) {
        throw new Error("请先选择音频文件");
    }
    return file;
}

function setPitchDetectStatus(message, isError = false) {
    if (els.pitchDetectStatus) {
        els.pitchDetectStatus.textContent = message;
        els.pitchDetectStatus.classList.toggle("error", Boolean(message) && isError);
        els.pitchDetectStatus.classList.toggle("success", Boolean(message) && !isError);
        els.pitchDetectStatus.style.color = isError ? "var(--danger, #e74c3c)" : "var(--accent-strong, #2563eb)";
    }
}

function ensurePitchDetectFile() {
    const file = els.pitchDetectFileInput.files?.[0];
    if (!file) {
        throw new Error("请先在上方选择音频文件");
    }
    return file;
}

function setAnalysisToolsOpen(isOpen) {
    state.analysisToolsOpen = Boolean(isOpen);
    if (els.analysisToolsPanel) {
        els.analysisToolsPanel.open = state.analysisToolsOpen;
    }
}

function getPitchDetectConfig() {
    return {
        algorithm: (els.pitchDetectAlgorithmInput.value || "yin").trim() || "yin",
        frameMs: parsePositiveInteger(els.pitchDetectFrameMsInput.value || "20", "分析窗长"),
        hopMs: parsePositiveInteger(els.pitchDetectHopMsInput.value || "10", "步进间隔"),
    };
}

function buildPitchDetectFormData(file) {
    const config = getPitchDetectConfig();
    const formData = new FormData();
    formData.append("file", file);
    formData.append("algorithm", config.algorithm);
    formData.append("frame_ms", String(config.frameMs));
    formData.append("hop_ms", String(config.hopMs));
    return { formData, config };
}

async function handlePitchDetect() {
    if (isBusy("pitch-detect")) {
        return;
    }
    setBusy("pitch-detect", true);
    setPitchDetectStatus("");
    try {
        const file = ensurePitchDetectFile();
        const { formData } = buildPitchDetectFormData(file);
        setPitchDetectStatus("正在检测音高序列，请稍候…");
        setAppStatus("正在处理音高识别，请稍候。");
        const result = await requestJson("/pitch/detect", { method: "POST", body: formData });
        const sequence = result.pitch_sequence || [];
        els.pitchSequenceInput.value = JSON.stringify(sequence, null, 2);
        localStorage.setItem(STORAGE_KEYS.pitchSequence, els.pitchSequenceInput.value);
        els.analysisIdInput.value = result.analysis_id || "";
        localStorage.setItem(STORAGE_KEYS.analysisId, els.analysisIdInput.value);
        const msg = `音高识别完成：识别到 ${sequence.length} 个音高点`;
        setPitchDetectStatus(msg);
        setAppStatus("音高识别已完成，可以继续生成乐谱。");
    } catch (error) {
        setPitchDetectStatus(`音高识别失败：${error.message}`, true);
        setAppStatus("音高识别未完成，请查看识别区域提示。", true);
    } finally {
        setBusy("pitch-detect", false);
    }
}

async function handlePitchDetectAndScore() {
    if (isBusy("pitch-detect-score")) {
        return;
    }
    setBusy("pitch-detect-score", true);
    setPitchDetectStatus("");
    try {
        const file = ensurePitchDetectFile();
        const { formData } = buildPitchDetectFormData(file);
        setPitchDetectStatus("正在检测音高序列…");
        setAppStatus("正在处理音频识谱请求。");
        let detectResult;
        try {
            detectResult = await requestJson("/pitch/detect", { method: "POST", body: formData });
        } catch (error) {
            setPitchDetectStatus(`音高识别失败：${error.message}`, true);
            setAppStatus("音高识别未完成，请查看识别区域提示。", true);
            return;
        }
        const sequence = detectResult.pitch_sequence || [];
        if (!sequence.length) {
            throw new Error("未能从音频中检测到有效的音高序列");
        }
        els.pitchSequenceInput.value = JSON.stringify(sequence, null, 2);
        localStorage.setItem(STORAGE_KEYS.pitchSequence, els.pitchSequenceInput.value);
        els.analysisIdInput.value = detectResult.analysis_id || "";
        localStorage.setItem(STORAGE_KEYS.analysisId, els.analysisIdInput.value);
        setPitchDetectStatus(`音高识别完成：检测到 ${sequence.length} 个音高点，正在生成乐谱…`);
        setAppStatus("音高识别完成，正在生成乐谱。");

        const payload = {
            user_id: await ensureScoreOwnerUserId(),
            title: (els.projectTitleInput.value || "").trim() || null,
            analysis_id: detectResult.analysis_id || null,
            tempo: parsePositiveInteger(els.tempoInput.value, "速度"),
            time_signature: (els.timeSignatureInput.value || "").trim() || "4/4",
            key_signature: (els.keySignatureInput.value || "").trim() || "C",
            pitch_sequence: sequence,
        };
        let created;
        try {
            created = await requestJson("/score/from-pitch-sequence", { method: "POST", body: payload });
        } catch (error) {
            setPitchDetectStatus(`音高已识别 ${sequence.length} 个音高点，但生成乐谱失败：${error.message}`, true);
            setAppStatus("乐谱生成未完成，请查看识别区域提示。", true);
            return;
        }
        state.exportList = [];
        state.selectedExportRecordId = null;
        state.selectedExportDetail = null;
        applyScoreResult(created);
        const msg = `音高识别与乐谱生成完成：乐谱 ${created.score_id} 已生成`;
        setPitchDetectStatus(msg);
        setAppStatus(`音频识谱完成，已关联乐谱 ${created.score_id}。`);
        queueExportRefresh();
    } catch (error) {
        setPitchDetectStatus(`识谱失败：${error.message}`, true);
        setAppStatus("音频识谱未完成，请查看识别区域提示。", true);
    } finally {
        setBusy("pitch-detect-score", false);
    }
}

async function handleCreateScore() {
    if (isBusy("create-score")) {
        return;
    }
    setBusy("create-score", true);
    try {
        const payload = {
            user_id: await ensureScoreOwnerUserId(),
            title: (els.projectTitleInput.value || "").trim() || null,
            analysis_id: (els.analysisIdInput.value || "").trim() || null,
            tempo: parsePositiveInteger(els.tempoInput.value, "速度"),
            time_signature: (els.timeSignatureInput.value || "").trim() || "4/4",
            key_signature: (els.keySignatureInput.value || "").trim() || "C",
            pitch_sequence: parsePitchSequence(),
        };
        const created = await requestJson("/score/from-pitch-sequence", { method: "POST", body: payload });
        state.exportList = [];
        state.selectedExportRecordId = null;
        state.selectedExportDetail = null;
        applyScoreResult(created);
        setAppStatus(`乐谱已生成并关联：${created.score_id}`);
        queueExportRefresh();
    } catch (error) {
        setAppStatus(`生成乐谱失败：${error.message}`, true);
    } finally {
        setBusy("create-score", false);
    }
}

async function handleBeatDetect() {
    if (isBusy("beat-detect")) {
        return;
    }
    setAnalysisToolsOpen(true);
    setBusy("beat-detect", true);
    try {
        const file = ensureAnalysisFile();
        const formData = new FormData();
        formData.append("file", file);
        if (els.beatBpmHintInput.value) {
            formData.append("bpm_hint", els.beatBpmHintInput.value);
        }
        formData.append("sensitivity", els.beatSensitivityInput.value || "0.5");
        const result = await requestJson("/rhythm/beat-detect", { method: "POST", body: formData });
        state.beatDetectResult = result;
        els.analysisIdInput.value = result.analysis_id || "";
        localStorage.setItem(STORAGE_KEYS.analysisId, els.analysisIdInput.value);
        els.userBeatsInput.value = JSON.stringify(result.beats || [], null, 2);
        renderAll();
        await loadAudioLogs();
        setAppStatus("节拍检测完成。");
    } catch (error) {
        setAppStatus(`节拍检测失败：${error.message}`, true);
    } finally {
        setBusy("beat-detect", false);
    }
}

async function handleSeparateTracks() {
    if (isBusy("separate-tracks")) {
        return;
    }
    setAnalysisToolsOpen(true);
    setBusy("separate-tracks", true);
    try {
        const file = ensureAnalysisFile();
        const formData = new FormData();
        formData.append("file", file);
        formData.append("model", (els.separationModelInput.value || "").trim() || "demucs");
        formData.append("stems", els.separationStemsInput.value || "2");
        const result = await requestJson("/audio/separate-tracks", { method: "POST", body: formData });
        state.separateTracksResult = result;
        els.analysisIdInput.value = result.analysis_id || els.analysisIdInput.value;
        localStorage.setItem(STORAGE_KEYS.analysisId, els.analysisIdInput.value);
        renderAll();
        await loadAudioLogs();
        setAppStatus("音轨分离完成。");
    } catch (error) {
        setAppStatus(`音轨分离失败：${error.message}`, true);
    } finally {
        setBusy("separate-tracks", false);
    }
}

async function handleGenerateChords() {
    if (isBusy("generate-chords")) {
        return;
    }
    setAnalysisToolsOpen(true);
    setBusy("generate-chords", true);
    try {
        const key = (state.currentScore?.key_signature || els.keySignatureInput.value || "C").trim() || "C";
        const tempo = parsePositiveInteger(state.currentScore?.tempo || els.tempoInput.value, "速度");
        const style = (els.chordStyleInput.value || "").trim() || "pop";
        const melody = buildMelodyFromScore();
        const result = await requestJson("/generation/chords", {
            method: "POST",
            body: { key, tempo, style, melody },
        });
        state.chordGenerationResult = result;
        renderAll();
        setAppStatus(`和弦生成完成，共返回 ${result.chords?.length || 0} 个和弦。`);
    } catch (error) {
        setAppStatus(`和弦生成失败：${error.message}`, true);
    } finally {
        setBusy("generate-chords", false);
    }
}

async function handleRhythmScore() {
    if (isBusy("rhythm-score")) {
        return;
    }
    setAnalysisToolsOpen(true);
    setBusy("rhythm-score", true);
    try {
        const result = await requestJson("/rhythm/score", {
            method: "POST",
            body: {
                reference_beats: parseJsonArray(els.referenceBeatsInput.value, "参考拍点"),
                user_beats: parseJsonArray(els.userBeatsInput.value, "用户拍点"),
                language: els.rhythmLanguageInput.value,
                scoring_model: els.rhythmModelInput.value,
                threshold_ms: Number(els.rhythmThresholdInput.value || 50),
            },
        });
        state.rhythmScoreResult = result;
        renderAll();
        setAppStatus(`节奏评分完成：${Math.round(Number(result.score || 0))}/100`);
    } catch (error) {
        setAppStatus(`节奏评分失败：${error.message}`, true);
    } finally {
        setBusy("rhythm-score", false);
    }
}

async function loadAudioLogs() {
    if (isBusy("audio-logs")) {
        return;
    }
    setBusy("audio-logs", true);
    try {
        const analysisId = (els.analysisIdInput.value || "").trim();
        const query = new URLSearchParams({ limit: "20" });
        if (analysisId) {
            query.set("analysis_id", analysisId);
        }
        const result = await requestJson(`/logs/audio?${query.toString()}`);
        state.audioLogs = result.logs || [];
        renderAll();
    } catch (error) {
        state.audioLogs = [];
        renderAll();
        setAppStatus(`音频日志加载失败：${error.message}`, true);
    } finally {
        setBusy("audio-logs", false);
    }
}

async function handleApplyScoreSettings() {
    if (!state.currentScore) {
        setAppStatus("请先生成或载入一份乐谱。", true);
        return;
    }
    const musicxml = (els.scoreMusicxmlInput.value || "").trim();
    if (!musicxml) {
        setAppStatus("MusicXML 不能为空。", true);
        return;
    }
    await patchScoreMusicxml(musicxml, "score-settings", "MusicXML 已保存并重新渲染。");
}

async function handleLoadScoreFileIntoEditor() {
    try {
        const file = els.scoreMusicxmlFileInput.files?.[0];
        if (!file) {
            throw new Error("请先选择一个 MusicXML 文件。");
        }
        const text = await file.text();
        els.scoreMusicxmlInput.value = text;
        setAppStatus(`已将 ${file.name} 载入编辑区。`);
    } catch (error) {
        setAppStatus(error.message, true);
    }
}

async function handleReplaceScoreFromFile() {
    if (!state.currentScore) {
        setAppStatus("请先生成或载入一份乐谱，再执行替换。", true);
        return;
    }
    try {
        const file = els.scoreMusicxmlFileInput.files?.[0];
        if (!file) {
            throw new Error("请先选择一个 MusicXML 文件。");
        }
        const text = await file.text();
        els.scoreMusicxmlInput.value = text;
        await patchScoreMusicxml(text, "score-file-replace", `已使用 ${file.name} 替换当前乐谱。`);
    } catch (error) {
        setAppStatus(error.message, true);
    }
}

function handleDownloadMusicxml() {
    if (!state.currentScore?.musicxml) {
        setAppStatus("当前没有可下载的 MusicXML。", true);
        return;
    }
    const blob = new Blob([state.currentScore.musicxml], { type: "application/xml;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${state.currentScore.score_id || "score"}.musicxml`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
}

async function handleRefreshScore() {
    if (!state.currentScore?.score_id && !state.selectedScoreId) {
        setAppStatus("当前没有可刷新的乐谱。", true);
        return;
    }
    await loadCurrentScore(state.currentScore?.score_id || state.selectedScoreId);
}

async function handleUndo() {
    await runScoreAction("undo", "undo-action", "已撤销到上一个 MusicXML 快照。");
}

async function handleRedo() {
    await runScoreAction("redo", "redo-action", "已重做到下一个 MusicXML 快照。");
}

async function runScoreAction(path, busyKey, message) {
    if (!state.currentScore || isBusy(busyKey)) {
        return;
    }
    setBusy(busyKey, true);
    try {
        const updated = await requestJson(`/scores/${state.currentScore.score_id}/${path}`, { method: "POST" });
        applyScoreResult(updated);
        setAppStatus(message);
    } catch (error) {
        setAppStatus(`${message} 失败：${error.message}`, true);
    } finally {
        setBusy(busyKey, false);
    }
}

async function patchScoreMusicxml(musicxml, busyKey, successMessage) {
    if (!state.currentScore || isBusy(busyKey)) {
        return;
    }
    setBusy(busyKey, true);
    try {
        const updated = await requestJson(`/scores/${state.currentScore.score_id}`, {
            method: "PATCH",
            body: { musicxml },
        });
        applyScoreResult(updated);
        setAppStatus(successMessage);
    } catch (error) {
        setAppStatus(`乐谱更新失败：${error.message}`, true);
    } finally {
        setBusy(busyKey, false);
    }
}

async function loadCurrentScore(scoreId, { silent = false } = {}) {
    if (!scoreId) {
        return null;
    }
    const busyKey = `score-load-${scoreId}`;
    if (isBusy(busyKey)) {
        return null;
    }
    setBusy(busyKey, true);
    try {
        const score = await requestJson(`/scores/${scoreId}`);
        applyScoreResult(score);
        if (!silent) {
            setAppStatus(`已刷新乐谱 ${score.score_id}。`);
        }
        return score;
    } catch (error) {
        if (!silent) {
            setAppStatus(`乐谱加载失败：${error.message}`, true);
        }
        return null;
    } finally {
        setBusy(busyKey, false);
    }
}

function applyScoreResult(score) {
    const previousScoreId = state.currentScore?.score_id || null;
    const previousScoreVersion = state.currentScore?.version || null;
    const preservePageIndex =
        Boolean(previousScoreId) &&
        previousScoreId === score?.score_id &&
        previousScoreVersion === score?.version;

    state.currentScore = score;
    state.selectedScoreId = score?.score_id || "";
    state.selectedNotationElementId = null;
    localStorage.setItem(STORAGE_KEYS.scoreId, state.selectedScoreId);

    els.tempoInput.value = String(score.tempo || els.tempoInput.value || "120");
    els.timeSignatureInput.value = score.time_signature || els.timeSignatureInput.value || "4/4";
    els.keySignatureInput.value = score.key_signature || els.keySignatureInput.value || "C";
    els.scoreMusicxmlInput.value = score.musicxml || "";

    invalidateViewerRenderState({ preservePageIndex });
    state.scorePageIndex = preservePageIndex ? Math.max(state.scorePageIndex || 0, 0) : 0;

    renderAll();
    queueExportRefresh();
}

function invalidateViewerRenderState({ preservePageIndex = false } = {}) {
    state.viewerPreparedKey = "";
    state.viewerPreparedMusicxml = "";
    state.viewerPreparedLayout = null;
    state.viewerPageCache = new Map();
    state.viewerPageRanges = [];
    state.viewerPageCount = 0;
    state.viewerWheelAccumX = 0;
    state.viewerSuppressClickUntil = 0;
    state.viewerGesture = null;
    state.viewerTransition = {
        phase: "idle",
        direction: 0,
        fromIndex: preservePageIndex ? state.scorePageIndex || 0 : 0,
        toIndex: preservePageIndex ? state.scorePageIndex || 0 : 0,
        progress: 0,
    };
}

function resolveMeasureCount(score) {
    return Number(score?.summary?.measure_count || 0) || 0;
}

function defaultSelectionHint() {
    return "当前谱面以 MusicXML 为唯一真源。点击谱面中的音符可高亮查看；如需修改，请直接编辑下方 MusicXML 或上传新的 `.musicxml/.xml` 文件整体替换。";
}

function renderAll() {
    renderBackendState();
    renderScoreSummary();
    renderAnalysisOutputs();
    renderExportList();
    renderAudioLogs();
    renderExportDetail();
    renderControlState();
    scheduleNotationRender();
}

async function ensureVerovioRuntime() {
    if (state.verovioReady) {
        return true;
    }
    if (state.verovioLoading) {
        return false;
    }
    const verovioApi = window.verovio;
    if (!verovioApi || typeof verovioApi.toolkit !== "function") {
        state.verovioError = "Verovio 资源未正确加载。";
        scheduleNotationRender();
        return false;
    }

    const tryConstruct = () => {
        const moduleRef = verovioApi.module;
        return new verovioApi.toolkit(moduleRef);
    };

    try {
        tryConstruct();
        state.verovioReady = true;
        state.verovioError = "";
        scheduleNotationRender();
        return true;
    } catch {
        state.verovioLoading = true;
        return await new Promise((resolve) => {
            const previousInit = verovioApi.module?.onRuntimeInitialized;
            if (verovioApi.module) {
                verovioApi.module.onRuntimeInitialized = () => {
                    if (typeof previousInit === "function") {
                        previousInit();
                    }
                    state.verovioLoading = false;
                    try {
                        tryConstruct();
                        state.verovioReady = true;
                        state.verovioError = "";
                        scheduleNotationRender();
                        resolve(true);
                    } catch (error) {
                        state.verovioError = `Verovio 初始化失败：${error.message}`;
                        scheduleNotationRender();
                        resolve(false);
                    }
                };
            } else {
                state.verovioLoading = false;
                state.verovioError = "Verovio 模块未准备就绪。";
                scheduleNotationRender();
                resolve(false);
            }
        });
    }
}

function createVerovioToolkit() {
    if (!state.verovioReady || !window.verovio || typeof window.verovio.toolkit !== "function") {
        return null;
    }
    return new window.verovio.toolkit(window.verovio.module);
}

function buildVerovioOptions(mode = "preview") {
    const measureCount = Math.max(resolveMeasureCount(state.currentScore), 1);
    if (mode === "viewer") {
        return {
            breaks: "encoded",
            pageWidth: 2100,
            pageHeight: Math.round(2100 / VIEWER_A4_RATIO),
            pageMarginLeft: 118,
            pageMarginRight: 118,
            pageMarginTop: 102,
            pageMarginBottom: 128,
            scale: 43,
            svgViewBox: true,
            adjustPageWidth: false,
            adjustPageHeight: false,
            scaleToPageSize: true,
            justifyVertically: true,
            systemMaxPerPage: VIEWER_LAYOUT_DEFAULTS.systemsPerPage || 5,
            spacingSystem: 24,
            spacingStaff: 14,
            header: "none",
            footer: "none",
        };
    }
    return {
        breaks: "auto",
        pageWidth: Math.max(2800, measureCount * 380),
        pageHeight: 1600,
        scale: 92,
        svgViewBox: true,
        adjustPageWidth: false,
        adjustPageHeight: true,
    };
}

function scheduleNotationRender({ viewerOnly = false } = {}) {
    const ticket = ++state.notationRenderTicket;
    queueMicrotask(async () => {
        if (ticket !== state.notationRenderTicket) {
            return;
        }
        if (!viewerOnly) {
            await renderScoreEntry();
        }
        await renderScoreViewer();
    });
}

async function renderScoreEntry() {
    const score = state.currentScore;
    els.scoreEmpty.hidden = Boolean(score);
    els.scoreViewerEntry.hidden = !score;
    if (!score) {
        els.scoreViewerEntry.innerHTML = "";
        state.previewPageCount = 0;
        return;
    }

    const rendered = await renderNotationTarget(els.scoreViewerEntry, { mode: "preview", pageIndex: 0 });
    state.previewPageCount = rendered.pageCount;
    const measureCount = resolveMeasureCount(score);
    const renderStateText = rendered.error
        ? escapeHtmlText(rendered.error)
        : `Verovio 预览已更新。全屏查看器会以 A4 纸张分页显示，当前预计 ${rendered.pageCount} 页。`;
    els.scoreViewerEntry.innerHTML = `
        <div class="score-entry-copy">
            <span class="score-entry-kicker">Verovio + MusicXML</span>
            <h3 class="score-entry-title">${escapeHtmlText(score.title || "未命名乐谱")}</h3>
            <p class="score-entry-text">谱面已经切换为 Verovio 渲染，五线谱、连音线、延音线与休止符都由 MusicXML 真源统一驱动。点击右上角查看器后，会以更接近真实纸质乐谱的 A4 分页方式浏览整份谱面。</p>
        </div>
        <div class="score-entry-stats">
            <span class="score-entry-chip">共 ${escapeHtmlText(String(measureCount))} 小节</span>
            <span class="score-entry-chip">预计 ${escapeHtmlText(String(rendered.pageCount))} 页</span>
            <span class="score-entry-chip">${rendered.error ? "渲染失败" : "全屏查看器支持纸张翻页"}</span>
        </div>
        ${rendered.markup}
        <p class="helper-text">${renderStateText}</p>
    `;
}

async function renderNotationTarget(targetElement, { mode = "preview", pageIndex = 0 } = {}) {
    if (!targetElement || !state.currentScore) {
        return { pageCount: 0, markup: "", error: "" };
    }
    const runtimeReady = await ensureVerovioRuntime();
    if (!runtimeReady) {
        const message = state.verovioError || "Verovio 仍在初始化，请稍候重试。";
        const markup = `<div class="verovio-stage"><div class="score-empty"><h3>暂时无法渲染谱面</h3><p>${escapeHtmlText(message)}</p></div></div>`;
        targetElement.innerHTML = markup;
        return { pageCount: 0, markup, error: message };
    }

    try {
        const toolkit = createVerovioToolkit();
        toolkit.setOptions(buildVerovioOptions(mode));
        const loaded = toolkit.loadData(state.currentScore.musicxml || "");
        if (!loaded) {
            throw new Error("Verovio 未能载入当前 MusicXML。");
        }
        const pageCount = Math.max(Number(toolkit.getPageCount() || 0), 1);
        const clampedPage = Math.min(Math.max(Number(pageIndex || 0), 0), pageCount - 1);
        if (mode === "viewer") {
            state.scorePageIndex = clampedPage;
        }
        const svgMarkup = toolkit.renderToSVG(clampedPage + 1);
        const markup = `<div class="verovio-stage ${mode === "viewer" ? "viewer" : "preview"}"><div class="verovio-pane">${svgMarkup}</div></div>`;
        targetElement.innerHTML = markup;
        targetElement.querySelectorAll(".note, .rest").forEach((element) => {
            element.classList.remove("is-selected");
        });
        return { pageCount, markup, error: "" };
    } catch (error) {
        const message = error?.message || "未知渲染错误";
        const markup = `<div class="verovio-stage"><div class="score-empty"><h3>谱面渲染失败</h3><p>${escapeHtmlText(message)}</p></div></div>`;
        targetElement.innerHTML = markup;
        return { pageCount: 0, markup, error: message };
    }
}

function isReducedMotionPreferred() {
    return Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
}

function buildViewerPreparedKey(score) {
    return `${score?.score_id || "score"}:${score?.version || 0}:${score?.musicxml?.length || 0}`;
}

function xmlLocalName(node) {
    return node?.localName || String(node?.nodeName || "").split(":").pop();
}

function getNamedChildren(parent, tagName) {
    return Array.from(parent?.children || []).filter((child) => xmlLocalName(child) === tagName);
}

function getFirstNamedChild(parent, tagName) {
    return getNamedChildren(parent, tagName)[0] || null;
}

function getNamedDescendants(parent, tagName) {
    return Array.from(parent?.getElementsByTagName("*") || []).filter((child) => xmlLocalName(child) === tagName);
}

function getFirstNamedDescendant(parent, tagName) {
    return getNamedDescendants(parent, tagName)[0] || null;
}

function childText(parent, tagName, fallback = "") {
    return getFirstNamedChild(parent, tagName)?.textContent || fallback;
}

function descendantText(parent, tagName, fallback = "") {
    return getFirstNamedDescendant(parent, tagName)?.textContent || fallback;
}

function createXmlChild(doc, tagName, text = null) {
    const element = doc.createElement(tagName);
    if (text !== null && text !== undefined) {
        element.textContent = String(text);
    }
    return element;
}

function setNamedChildText(parent, tagName, text, { prepend = false } = {}) {
    let child = getFirstNamedChild(parent, tagName);
    if (!child) {
        child = createXmlChild(parent.ownerDocument, tagName, text);
        if (prepend && parent.firstChild) {
            parent.insertBefore(child, parent.firstChild);
        } else {
            parent.appendChild(child);
        }
    } else {
        child.textContent = String(text);
    }
    return child;
}

function parsePitchFromNote(noteEl) {
    if (getFirstNamedChild(noteEl, "rest")) {
        return "Rest";
    }
    const pitchEl = getFirstNamedChild(noteEl, "pitch");
    if (!pitchEl) {
        return "Rest";
    }
    const step = childText(pitchEl, "step", "C");
    const alter = Number.parseInt(childText(pitchEl, "alter", "0"), 10) || 0;
    const octave = childText(pitchEl, "octave", "4");
    const accidental = alter === 1 ? "#" : alter === -1 ? "b" : "";
    return `${step}${accidental}${octave}`;
}

function extractViewerMeasureModels(partEl) {
    const measureElements = getNamedChildren(partEl, "measure");
    let divisions = 8;

    return measureElements.map((measureEl, measureIndex) => {
        const attributesEl = getFirstNamedChild(measureEl, "attributes");
        if (attributesEl) {
            divisions = Number.parseInt(descendantText(attributesEl, "divisions", String(divisions)), 10) || divisions;
        }
        const notes = getNamedChildren(measureEl, "note").map((noteEl) => {
            const pitch = parsePitchFromNote(noteEl);
            const isRest = pitch === "Rest";
            const duration = Number.parseFloat(childText(noteEl, "duration", "0")) || 0;
            const beats = divisions > 0 ? duration / divisions : 0;
            const pitchEl = getFirstNamedChild(noteEl, "pitch");
            const alter = pitchEl ? Number.parseInt(childText(pitchEl, "alter", "0"), 10) || 0 : 0;
            return {
                pitch,
                isRest,
                beats,
                alter,
                hasAccidental: Boolean(getFirstNamedChild(noteEl, "accidental")),
                tieCount: getNamedChildren(noteEl, "tie").length,
                slurCount: getNamedDescendants(noteEl, "slur").length,
                dotCount: getNamedChildren(noteEl, "dot").length,
            };
        });
        return {
            measureNo: Number(measureEl.getAttribute("number") || measureIndex + 1),
            notes,
        };
    });
}

function canUseGrandStaffDisplayTransform(parts) {
    if ((parts || []).length !== 1) {
        return false;
    }
    const partEl = parts[0];
    const measures = getNamedChildren(partEl, "measure");
    if (!measures.length) {
        return false;
    }
    const firstAttributes = getFirstNamedChild(measures[0], "attributes");
    if (Number.parseInt(descendantText(firstAttributes, "staves", "1"), 10) > 1) {
        return false;
    }
    const hasMultipleClefs = getNamedChildren(firstAttributes, "clef").length > 1;
    if (hasMultipleClefs) {
        return false;
    }

    return !measures.some((measureEl) =>
        getNamedChildren(measureEl, "note").some(
            (noteEl) =>
                Boolean(getFirstNamedChild(noteEl, "staff")) ||
                Boolean(getFirstNamedChild(noteEl, "chord"))
        ) ||
        Boolean(getFirstNamedChild(measureEl, "backup")) ||
        Boolean(getFirstNamedChild(measureEl, "forward"))
    );
}

function ensurePrintElement(measureEl) {
    let printEl = getFirstNamedChild(measureEl, "print");
    if (printEl) {
        return printEl;
    }

    printEl = measureEl.ownerDocument.createElement("print");
    const insertBeforeEl = Array.from(measureEl.children).find((child) => xmlLocalName(child) !== "attributes");
    if (insertBeforeEl) {
        measureEl.insertBefore(printEl, insertBeforeEl);
    } else {
        measureEl.appendChild(printEl);
    }
    return printEl;
}

function applyViewerBreaksToPart(partEl, pagination) {
    const measures = getNamedChildren(partEl, "measure");
    const systemStarts = new Set((pagination?.systems || []).map((system) => system.measureIndices[0]).filter((value) => value > 0));
    const pageStarts = new Set((pagination?.pages || []).map((page) => page.measureIndices[0]).filter((value) => value > 0));

    measures.forEach((measureEl, measureIndex) => {
        const printEl = getFirstNamedChild(measureEl, "print");
        const isPageStart = pageStarts.has(measureIndex);
        const isSystemStart = isPageStart || systemStarts.has(measureIndex);

        if (!isPageStart && !isSystemStart) {
            if (printEl) {
                printEl.removeAttribute("new-page");
                printEl.removeAttribute("new-system");
                if (!printEl.attributes.length && !printEl.children.length) {
                    printEl.remove();
                }
            }
            return;
        }

        const ensuredPrintEl = printEl || ensurePrintElement(measureEl);
        if (isPageStart) {
            ensuredPrintEl.setAttribute("new-page", "yes");
        } else {
            ensuredPrintEl.removeAttribute("new-page");
        }
        if (isSystemStart) {
            ensuredPrintEl.setAttribute("new-system", "yes");
        } else {
            ensuredPrintEl.removeAttribute("new-system");
        }
    });
}

function upsertGrandStaffAttributes(measureEl, { includeBrace = false } = {}) {
    let attributesEl = getFirstNamedChild(measureEl, "attributes");
    if (!attributesEl) {
        attributesEl = measureEl.ownerDocument.createElement("attributes");
        measureEl.insertBefore(attributesEl, measureEl.firstChild);
    }

    setNamedChildText(attributesEl, "staves", "2");
    getNamedChildren(attributesEl, "clef").forEach((clefEl) => clefEl.remove());

    if (includeBrace) {
        let partSymbolEl = getFirstNamedChild(attributesEl, "part-symbol");
        if (!partSymbolEl) {
            partSymbolEl = attributesEl.ownerDocument.createElement("part-symbol");
            attributesEl.appendChild(partSymbolEl);
        }
        partSymbolEl.setAttribute("type", "brace");
    }

    const trebleClef = attributesEl.ownerDocument.createElement("clef");
    trebleClef.setAttribute("number", "1");
    trebleClef.appendChild(createXmlChild(attributesEl.ownerDocument, "sign", "G"));
    trebleClef.appendChild(createXmlChild(attributesEl.ownerDocument, "line", "2"));

    const bassClef = attributesEl.ownerDocument.createElement("clef");
    bassClef.setAttribute("number", "2");
    bassClef.appendChild(createXmlChild(attributesEl.ownerDocument, "sign", "F"));
    bassClef.appendChild(createXmlChild(attributesEl.ownerDocument, "line", "4"));

    attributesEl.appendChild(trebleClef);
    attributesEl.appendChild(bassClef);
}

function upsertNoteStaff(noteEl, staffNumber) {
    let staffEl = getFirstNamedChild(noteEl, "staff");
    if (!staffEl) {
        staffEl = noteEl.ownerDocument.createElement("staff");
        const anchor =
            getFirstNamedChild(noteEl, "voice") ||
            getFirstNamedChild(noteEl, "duration") ||
            getFirstNamedChild(noteEl, "type");
        if (anchor?.nextSibling) {
            noteEl.insertBefore(staffEl, anchor.nextSibling);
        } else {
            noteEl.appendChild(staffEl);
        }
    }
    staffEl.textContent = String(staffNumber);
}

function applyGrandStaffDisplayTransform(partEl) {
    const measureElements = getNamedChildren(partEl, "measure");
    const noteEntries = [];

    measureElements.forEach((measureEl) => {
        upsertGrandStaffAttributes(measureEl, { includeBrace: measureEl === measureElements[0] });
        getNamedChildren(measureEl, "note").forEach((noteEl) => {
            noteEntries.push({
                noteEl,
                pitch: parsePitchFromNote(noteEl),
                isRest: Boolean(getFirstNamedChild(noteEl, "rest")),
            });
        });
    });

    const assignedStaffs = VIEWER_LAYOUT.assignStaffSequence
        ? VIEWER_LAYOUT.assignStaffSequence(noteEntries)
        : noteEntries.map((entry) => (entry.isRest ? "treble" : "treble"));

    noteEntries.forEach((entry, index) => {
        upsertNoteStaff(entry.noteEl, assignedStaffs[index] === "bass" ? 2 : 1);
    });

    const partNameEl = getFirstNamedDescendant(partEl.ownerDocument, "part-name");
    if (partNameEl) {
        partNameEl.textContent = "Piano";
    }
}

function serializeXmlDocument(xmlDoc) {
    return `<?xml version="1.0" encoding="UTF-8"?>\n${new XMLSerializer().serializeToString(xmlDoc)}`;
}

function prepareViewerDocument() {
    if (!state.currentScore?.musicxml) {
        return null;
    }

    const cacheKey = buildViewerPreparedKey(state.currentScore);
    if (state.viewerPreparedKey === cacheKey && state.viewerPreparedLayout && state.viewerPreparedMusicxml) {
        return {
            cacheKey,
            musicxml: state.viewerPreparedMusicxml,
            layout: state.viewerPreparedLayout,
            pageCount: state.viewerPreparedLayout.pages.length,
            pageRanges: state.viewerPreparedLayout.pageRanges,
        };
    }

    try {
        const xmlDoc = new DOMParser().parseFromString(state.currentScore.musicxml, "application/xml");
        if (xmlDoc.querySelector("parsererror")) {
            throw new Error("MusicXML 解析失败");
        }

        const parts = Array.from(xmlDoc.getElementsByTagName("*")).filter((element) => xmlLocalName(element) === "part");
        const primaryPart = parts[0] || null;
        const measureModels = primaryPart ? extractViewerMeasureModels(primaryPart) : [];
        const layout = VIEWER_LAYOUT.buildViewerPagination
            ? VIEWER_LAYOUT.buildViewerPagination(measureModels, VIEWER_LAYOUT_DEFAULTS)
            : { systems: [], pages: [], pageRanges: [] };

        parts.forEach((partEl) => applyViewerBreaksToPart(partEl, layout));
        if (primaryPart && canUseGrandStaffDisplayTransform(parts)) {
            applyGrandStaffDisplayTransform(primaryPart);
        }

        state.viewerPreparedKey = cacheKey;
        state.viewerPreparedMusicxml = serializeXmlDocument(xmlDoc);
        state.viewerPreparedLayout = layout;
        state.viewerPageRanges = layout.pageRanges || [];
        state.viewerPageCache = new Map();

        return {
            cacheKey,
            musicxml: state.viewerPreparedMusicxml,
            layout,
            pageCount: layout.pages.length,
            pageRanges: layout.pageRanges,
        };
    } catch (error) {
        const measureCount = resolveMeasureCount(state.currentScore);
        const fallbackLayout = {
            systems: [],
            pages: [{ index: 0, systems: [], measureIndices: [], startMeasureNo: 1, endMeasureNo: measureCount || 1 }],
            pageRanges: [{ pageIndex: 0, startMeasureNo: 1, endMeasureNo: measureCount || 1 }],
        };
        state.viewerPreparedKey = cacheKey;
        state.viewerPreparedMusicxml = state.currentScore.musicxml;
        state.viewerPreparedLayout = fallbackLayout;
        state.viewerPageRanges = fallbackLayout.pageRanges;
        state.viewerPageCache = new Map();
        return {
            cacheKey,
            musicxml: state.viewerPreparedMusicxml,
            layout: fallbackLayout,
            pageCount: 1,
            pageRanges: fallbackLayout.pageRanges,
            fallbackError: error.message,
        };
    }
}

async function resolveViewerPageMarkup(pageIndex) {
    const prepared = prepareViewerDocument();
    if (!prepared) {
        return null;
    }
    const cacheKey = `${prepared.cacheKey}:${pageIndex}`;
    const cached = state.viewerPageCache.get(cacheKey);
    if (cached) {
        return cached;
    }

    const toolkit = createVerovioToolkit();
    if (!toolkit) {
        throw new Error(state.verovioError || "Verovio 查看器尚未初始化完成。");
    }
    toolkit.setOptions(buildVerovioOptions("viewer"));
    const loaded = toolkit.loadData(prepared.musicxml || "");
    if (!loaded) {
        throw new Error("Verovio 未能载入查看器分页数据。");
    }

    const actualPageCount = Math.max(Number(toolkit.getPageCount() || 0), prepared.pageCount || 1, 1);
    state.viewerPageCount = actualPageCount;
    const resolvedIndex = VIEWER_LAYOUT.clamp
        ? VIEWER_LAYOUT.clamp(pageIndex, 0, actualPageCount - 1)
        : Math.min(Math.max(pageIndex, 0), actualPageCount - 1);
    const payload = {
        pageIndex: resolvedIndex,
        svgMarkup: toolkit.renderToSVG(resolvedIndex + 1),
    };
    state.viewerPageCache.set(cacheKey, payload);
    return payload;
}

function primeViewerPageCache(pageIndex) {
    const prepared = prepareViewerDocument();
    if (!prepared || pageIndex < 0 || pageIndex >= Math.max(prepared.pageCount || 0, state.viewerPageCount || 0, 1)) {
        return;
    }
    void resolveViewerPageMarkup(pageIndex).catch(() => {});
}

function buildViewerSheetMarkup(pagePayload, role, { interactive = false } = {}) {
    if (!pagePayload) {
        return "";
    }
    return `
        <section class="score-paper-sheet ${role}${interactive ? " is-live" : ""}" data-page-index="${pagePayload.pageIndex}">
            <div class="score-paper-surface">
                <div class="score-paper-canvas">
                    <div class="score-paper-svg">
                        <div class="verovio-pane">${pagePayload.svgMarkup}</div>
                    </div>
                </div>
                <span class="score-paper-sheet-number">${pagePayload.pageIndex + 1}</span>
            </div>
        </section>
    `;
}

function buildViewerStackMarkup(currentPage, incomingPage) {
    const transition = state.viewerTransition;
    const classes = ["score-paper-stack"];

    if (transition.phase === "animating") {
        classes.push("is-animated");
        classes.push(transition.direction >= 0 ? "is-turning-forward" : "is-turning-backward");
    } else if (transition.phase === "dragging") {
        classes.push(transition.direction >= 0 ? "is-dragging-forward" : "is-dragging-backward");
    }

    const progress = Math.min(Math.max(Number(transition.progress || 0), 0), 1);
    return `
        <div class="score-paper-viewport">
            <div class="${classes.join(" ")}" style="--turn-progress:${progress}">
                ${buildViewerSheetMarkup(currentPage, "current", { interactive: !incomingPage })}
                ${buildViewerSheetMarkup(incomingPage, "incoming")}
            </div>
        </div>
    `;
}

function reapplySelectedNotationState() {
    if (!state.selectedNotationElementId) {
        return;
    }
    const safeId = window.CSS?.escape
        ? window.CSS.escape(state.selectedNotationElementId)
        : String(state.selectedNotationElementId).replace(/"/g, '\\"');
    els.scoreViewerCanvas
        .querySelectorAll(`.note.is-selected, .rest.is-selected, [id="${safeId}"].is-selected`)
        .forEach((element) => element.classList.remove("is-selected"));

    const target = els.scoreViewerCanvas.querySelector(`#${safeId}, [id="${safeId}"]`);
    if (target?.classList) {
        target.classList.add("is-selected");
    }
}

async function renderScoreViewer() {
    const score = state.currentScore;
    const isOpen = Boolean(state.scoreViewerOpen);
    els.scoreViewerOverlay.hidden = !isOpen;
    document.body.classList.toggle("score-viewer-open", isOpen);
    if (!isOpen) {
        return;
    }

    els.scoreViewerEmpty.hidden = Boolean(score);
    els.scoreViewerCanvas.hidden = !score;
    if (!score) {
        els.scoreViewerStage.classList.remove("is-dragging");
        els.scoreViewerScoreTitle.textContent = "未加载乐谱";
        els.scoreViewerScoreSubtitle.textContent = "请先在工作台生成乐谱，然后再打开这里查看 A4 纸质乐谱风格的分页谱面。";
        els.scoreViewerCanvas.innerHTML = "";
        state.viewerPageCount = 0;
        state.viewerPageRanges = [];
        renderScoreViewerPagination(0);
        renderControlState();
        return;
    }

    els.scoreViewerScoreTitle.textContent = score.title || `乐谱 ${score.score_id}`;
    els.scoreViewerScoreSubtitle.textContent = `共 ${resolveMeasureCount(score)} 小节。纸张按 A4 五行钢琴大谱表查看，支持左右滑动翻页，点击音符可高亮当前符号。`;

    const runtimeReady = await ensureVerovioRuntime();
    if (!runtimeReady) {
        els.scoreViewerStage.classList.remove("is-dragging");
        els.scoreViewerCanvas.innerHTML = `<div class="score-empty"><h3>暂时无法渲染谱面</h3><p>${escapeHtmlText(
            state.verovioError || "Verovio 仍在初始化，请稍候重试。"
        )}</p></div>`;
        renderScoreViewerPagination(0);
        renderControlState();
        return;
    }

    try {
        const prepared = prepareViewerDocument();
        const pageCount = Math.max(Number(prepared?.pageCount || 0), 1);
        state.viewerPageRanges = prepared?.pageRanges || [];
        state.viewerPageCount = pageCount;
        state.scorePageIndex = Math.min(Math.max(state.scorePageIndex || 0, 0), pageCount - 1);

        const transition = state.viewerTransition;
        const currentIndex =
            transition.phase === "idle"
                ? state.scorePageIndex
                : Math.min(Math.max(transition.fromIndex || 0, 0), pageCount - 1);
        const incomingIndex =
            transition.phase === "idle"
                ? null
                : Math.min(Math.max(transition.toIndex || 0, 0), pageCount - 1);

        const currentPage = await resolveViewerPageMarkup(currentIndex);
        const incomingPage = incomingIndex !== null ? await resolveViewerPageMarkup(incomingIndex) : null;

        els.scoreViewerStage.classList.toggle("is-dragging", transition.phase === "dragging");
        els.scoreViewerCanvas.innerHTML = buildViewerStackMarkup(currentPage, incomingPage);
        reapplySelectedNotationState();
        renderScoreViewerPagination(pageCount);
        renderControlState();
        primeViewerPageCache(state.scorePageIndex + 1);
        primeViewerPageCache(state.scorePageIndex - 1);
    } catch (error) {
        els.scoreViewerStage.classList.remove("is-dragging");
        els.scoreViewerCanvas.innerHTML = `<div class="score-empty"><h3>谱面渲染失败</h3><p>${escapeHtmlText(
            error?.message || "未知渲染错误"
        )}</p></div>`;
        renderScoreViewerPagination(0);
        renderControlState();
    }
}

function renderScoreSummary() {
    const score = state.currentScore;
    els.scoreLinkageStatus.textContent = score ? "已连接" : "未连接";
    els.scoreTitleDisplay.textContent = score ? score.title || "未命名乐谱" : "尚未载入乐谱";
    els.scoreIdBadge.textContent = score ? score.score_id : "--";
    els.projectIdBadge.textContent = score ? score.project_id : "--";
    els.scoreVersionBadge.textContent = score ? score.version : "--";
    els.tempoDisplay.textContent = score ? score.tempo : "--";
    els.timeDisplay.textContent = score ? score.time_signature : "--";
    els.keyDisplay.textContent = score ? score.key_signature : "--";
    els.measureCountDisplay.textContent = score ? resolveMeasureCount(score) : "--";
    els.selectedNoteSummary.textContent = state.selectedNotationElementId
        ? "当前已在谱面中高亮一个音符或休止符。若需修改，请在下方 MusicXML 中编辑后保存。"
        : defaultSelectionHint();
}

function renderScoreViewerPagination(pageCount) {
    const resolvedCount = Math.max(Number(pageCount || 0), 0);
    if (!resolvedCount) {
        els.scoreViewerPageStatus.textContent = "第 0 / 0 页";
        els.scoreViewerPageRange.textContent = "共 0 小节";
        return;
    }
    const visibleIndex =
        state.viewerTransition.phase === "idle"
            ? state.scorePageIndex
            : Math.min(Math.max(state.viewerTransition.toIndex || 0, 0), resolvedCount - 1);
    els.scoreViewerPageStatus.textContent = `第 ${visibleIndex + 1} / ${resolvedCount} 页`;
    const range =
        state.viewerPageRanges[visibleIndex] ||
        state.viewerPageRanges[resolvedCount - 1] ||
        { startMeasureNo: 1, endMeasureNo: resolveMeasureCount(state.currentScore) };
    els.scoreViewerPageRange.textContent = `第 ${range.startMeasureNo}-${range.endMeasureNo} 小节`;
}

function openScoreViewer() {
    if (!state.currentScore) {
        setAppStatus("请先生成乐谱，再打开查看器。", true);
        return;
    }
    state.scoreViewerOpen = true;
    state.viewerTransition = {
        phase: "idle",
        direction: 0,
        fromIndex: state.scorePageIndex || 0,
        toIndex: state.scorePageIndex || 0,
        progress: 0,
    };
    scheduleNotationRender({ viewerOnly: true });
    els.scoreViewerStage.focus({ preventScroll: true });
    renderControlState();
}

function closeScoreViewer() {
    state.viewerGesture = null;
    state.viewerSuppressClickUntil = 0;
    state.viewerTransition = {
        phase: "idle",
        direction: 0,
        fromIndex: state.scorePageIndex || 0,
        toIndex: state.scorePageIndex || 0,
        progress: 0,
    };
    state.scoreViewerOpen = false;
    renderScoreViewer();
    renderControlState();
}

function finishViewerPageTurn(nextIndex) {
    state.scorePageIndex = nextIndex;
    state.viewerTransition = {
        phase: "idle",
        direction: 0,
        fromIndex: nextIndex,
        toIndex: nextIndex,
        progress: 0,
    };
    scheduleNotationRender({ viewerOnly: true });
}

function beginViewerPageTurn(nextIndex, direction, { immediate = false } = {}) {
    if (immediate || isReducedMotionPreferred()) {
        finishViewerPageTurn(nextIndex);
        return;
    }
    state.viewerTransition = {
        phase: "animating",
        direction,
        fromIndex: state.scorePageIndex,
        toIndex: nextIndex,
        progress: 1,
    };
    scheduleNotationRender({ viewerOnly: true });
    window.setTimeout(() => finishViewerPageTurn(nextIndex), VIEWER_PAGE_TURN_MS);
}

function changeScorePage(delta, options = {}) {
    if (state.viewerTransition.phase !== "idle") {
        return;
    }
    const pageCount = Math.max(state.viewerPageCount || 1, 1);
    const nextIndex = Math.min(Math.max((state.scorePageIndex || 0) + Number(delta || 0), 0), pageCount - 1);
    if (nextIndex === state.scorePageIndex) {
        return;
    }
    beginViewerPageTurn(nextIndex, Math.sign(delta || nextIndex - state.scorePageIndex || 1), options);
}

function handleViewerPointerDown(event) {
    if (!state.scoreViewerOpen || !state.currentScore || state.viewerTransition.phase !== "idle") {
        return;
    }
    if (event.pointerType === "mouse" && event.button !== 0) {
        return;
    }
    state.viewerGesture = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        currentX: event.clientX,
        dragging: false,
    };
}

function handleViewerPointerMove(event) {
    const gesture = state.viewerGesture;
    if (!gesture || gesture.pointerId !== event.pointerId || !state.scoreViewerOpen) {
        return;
    }

    const deltaX = event.clientX - gesture.startX;
    const deltaY = event.clientY - gesture.startY;
    if (!gesture.dragging) {
        if (Math.abs(deltaX) < 10 || Math.abs(deltaX) <= Math.abs(deltaY) * 1.15) {
            return;
        }
        gesture.dragging = true;
    }

    event.preventDefault();
    gesture.currentX = event.clientX;
    const width = els.scoreViewerStage.getBoundingClientRect().width || window.innerWidth || 1;
    const direction = deltaX < 0 ? 1 : -1;
    const candidateIndex = Math.min(
        Math.max((state.scorePageIndex || 0) + direction, 0),
        Math.max((state.viewerPageCount || 1) - 1, 0)
    );
    if (candidateIndex === state.scorePageIndex) {
        state.viewerTransition = {
            phase: "dragging",
            direction,
            fromIndex: state.scorePageIndex,
            toIndex: state.scorePageIndex,
            progress: 0,
        };
        scheduleNotationRender({ viewerOnly: true });
        return;
    }

    state.viewerTransition = {
        phase: "dragging",
        direction,
        fromIndex: state.scorePageIndex,
        toIndex: candidateIndex,
        progress: Math.min(Math.abs(deltaX) / width, 1),
    };
    scheduleNotationRender({ viewerOnly: true });
}

function handleViewerPointerUp(event) {
    const gesture = state.viewerGesture;
    if (!gesture || gesture.pointerId !== event.pointerId) {
        return;
    }

    const deltaX = (gesture.currentX || event.clientX) - gesture.startX;
    const width = els.scoreViewerStage.getBoundingClientRect().width || window.innerWidth || 1;
    const direction = deltaX < 0 ? 1 : -1;
    const nextIndex = Math.min(
        Math.max((state.scorePageIndex || 0) + direction, 0),
        Math.max((state.viewerPageCount || 1) - 1, 0)
    );
    const progress = Math.abs(deltaX) / width;
    const shouldTurn = gesture.dragging && nextIndex !== state.scorePageIndex && progress >= VIEWER_DRAG_THRESHOLD;

    state.viewerGesture = null;
    if (gesture.dragging) {
        state.viewerSuppressClickUntil = Date.now() + 220;
    }
    if (shouldTurn) {
        beginViewerPageTurn(nextIndex, direction);
        return;
    }

    state.viewerTransition = {
        phase: "idle",
        direction: 0,
        fromIndex: state.scorePageIndex || 0,
        toIndex: state.scorePageIndex || 0,
        progress: 0,
    };
    scheduleNotationRender({ viewerOnly: true });
}

function handleViewerWheel(event) {
    if (!state.scoreViewerOpen || Math.abs(event.deltaX) <= Math.abs(event.deltaY) || state.viewerTransition.phase !== "idle") {
        return;
    }
    event.preventDefault();
    state.viewerWheelAccumX += event.deltaX;
    if (Math.abs(state.viewerWheelAccumX) < VIEWER_WHEEL_THRESHOLD) {
        return;
    }
    const direction = state.viewerWheelAccumX > 0 ? 1 : -1;
    state.viewerWheelAccumX = 0;
    changeScorePage(direction);
}

function handleScoreCanvasInteraction(event) {
    if (
        state.viewerGesture?.dragging ||
        state.viewerTransition.phase === "dragging" ||
        Date.now() < (state.viewerSuppressClickUntil || 0)
    ) {
        return;
    }
    const clickedSymbol = event.target.closest(".note, .rest");
    const host = event.currentTarget;
    host.querySelectorAll(".note.is-selected, .rest.is-selected").forEach((element) => {
        element.classList.remove("is-selected");
    });
    if (clickedSymbol) {
        clickedSymbol.classList.add("is-selected");
        state.selectedNotationElementId = clickedSymbol.id || "selected-symbol";
        els.selectedNoteSummary.textContent = "当前已在谱面中高亮一个音符或休止符。若需修改，请在下方 MusicXML 中编辑后保存。";
    } else {
        state.selectedNotationElementId = null;
        els.selectedNoteSummary.textContent = defaultSelectionHint();
    }
}

function buildMelodyFromScore() {
    if (!state.currentScore?.musicxml) {
        return [];
    }
    const xml = new DOMParser().parseFromString(state.currentScore.musicxml, "application/xml");
    if (xml.querySelector("parsererror")) {
        return [];
    }

    const measures = Array.from(xml.querySelectorAll("part > measure"));
    const melody = [];
    measures.forEach((measure, index) => {
        const divisions = Number(measure.querySelector("attributes > divisions")?.textContent || 8);
        let cursor = 0;
        Array.from(measure.children).forEach((child) => {
            if (child.tagName !== "note") {
                return;
            }
            const duration = Number(child.querySelector("duration")?.textContent || 0);
            const beats = duration > 0 ? duration / divisions : 0;
            const startBeat = cursor / divisions + 1;
            cursor += duration;
            if (child.querySelector("rest")) {
                return;
            }
            const pitch = child.querySelector("pitch");
            if (!pitch) {
                return;
            }
            const step = pitch.querySelector("step")?.textContent || "C";
            const alter = Number(pitch.querySelector("alter")?.textContent || 0);
            const octave = pitch.querySelector("octave")?.textContent || "4";
            const accidental = alter === 1 ? "#" : alter === -1 ? "b" : "";
            melody.push({
                measure_no: index + 1,
                start_beat: startBeat,
                beats,
                pitch: `${step}${accidental}${octave}`,
            });
        });
    });
    return melody;
}

function renderAnalysisOutputs() {
    renderBeatDetectPanel();
    renderSeparateTracksPanel();
    renderChordGenerationPanel();
    renderRhythmScorePanel();
}

function renderBeatDetectPanel() {
    if (!state.beatDetectResult) {
        els.beatDetectOutput.innerHTML = '<p class="analysis-placeholder">运行节拍检测后，这里会展示 BPM、拍点分布和节拍时间轴。</p>';
        return;
    }
    const result = state.beatDetectResult;
    const beats = Array.isArray(result.beats) ? result.beats : [];
    els.beatDetectOutput.innerHTML = `
        <div class="analysis-stack analysis-tone-blue">
            <div class="analysis-metrics">
                ${metricCard("BPM", result.bpm ? Math.round(Number(result.bpm)) : "--")}
                ${metricCard("拍点数", beats.length)}
                ${metricCard("时长", formatSeconds(result.duration || result.audio_log?.duration))}
            </div>
            <div class="analysis-note">${escapeHtmlText(buildBeatSummary(beats))}</div>
            <p class="analysis-subtitle">节拍尺</p>
            ${buildBeatRuler(beats, result.duration || result.audio_log?.duration)}
            <p class="analysis-subtitle">拍点间隔</p>
            ${buildBeatIntervalChart(beats)}
            <div class="analysis-chip-row">
                ${beats.slice(0, 8).map((beat, index) => `<span class="analysis-chip">第 ${index + 1} 拍 ${formatBeat(beat)} 秒</span>`).join("") || '<span class="analysis-chip">暂无拍点</span>'}
            </div>
        </div>
    `;
}

function renderSeparateTracksPanel() {
    if (!state.separateTracksResult) {
        els.separateTracksOutput.innerHTML = '<p class="analysis-placeholder">运行音轨分离后，这里会展示分离出的音轨、时长和处理信息。</p>';
        return;
    }
    const result = state.separateTracksResult;
    const tracks = Array.isArray(result.tracks) ? result.tracks : [];
    els.separateTracksOutput.innerHTML = `
        <div class="analysis-stack analysis-tone-orange">
            <div class="analysis-metrics">
                ${metricCard("状态", escapeHtmlText(localizeTaskStatus(result.status) || "--"))}
                ${metricCard("处理方式", escapeHtmlText(result.backend_used || "--"))}
                ${metricCard("分轨数", result.stems || 0)}
                ${metricCard("采样率", result.sample_rate ? `${result.sample_rate} Hz` : "--")}
            </div>
            <div class="analysis-track-grid">
                ${tracks.map((track) => buildTrackCard(track)).join("") || '<div class="analysis-note">暂未返回分离后的分轨结果。</div>'}
            </div>
            ${result.warnings && result.warnings.length ? `<div class="analysis-note">${escapeHtmlText(result.warnings.join("；"))}</div>` : ""}
        </div>
    `;
}

function renderChordGenerationPanel() {
    if (!state.chordGenerationResult) {
        els.generateChordsOutput.innerHTML = '<p class="analysis-placeholder">基于当前乐谱生成和弦后，这里会展示系统给出的和声建议和时间轴。</p>';
        return;
    }
    const result = state.chordGenerationResult;
    const chords = Array.isArray(result.chords) ? result.chords : [];
    els.generateChordsOutput.innerHTML = `
        <div class="analysis-stack analysis-tone-green">
            <div class="analysis-metrics">
                ${metricCard("调号", escapeHtmlText(result.key || "--"))}
                ${metricCard("速度", result.tempo ? `${result.tempo} BPM` : "--")}
                ${metricCard("风格", escapeHtmlText(result.style || "--"))}
                ${metricCard("旋律音符", result.melody_size || 0)}
            </div>
            <p class="analysis-subtitle">和弦时间轴</p>
            ${buildChordTimeline(chords)}
            <div class="analysis-list">
                ${chords.map((chord) => `
                    <div class="analysis-item">
                        <div>
                            <div class="analysis-item-title">${escapeHtmlText(chord.symbol || "--")}</div>
                            <div class="analysis-item-meta">和弦建议</div>
                        </div>
                        <div class="analysis-item-value">${formatBeat(chord.time || 0)}秒</div>
                    </div>
                `).join("") || '<div class="analysis-note">暂未返回和弦结果。</div>'}
            </div>
        </div>
    `;
}

function renderRhythmScorePanel() {
    if (!state.rhythmScoreResult) {
        els.rhythmScoreOutput.innerHTML = '<p class="analysis-placeholder">运行节奏评分后，这里会对比参考拍点与用户拍点，并展示得分与反馈。</p>';
        return;
    }
    const result = state.rhythmScoreResult;
    const feedback = flattenFeedback(result.feedback);
    els.rhythmScoreOutput.innerHTML = `
        <div class="analysis-stack analysis-tone-blue">
            <div class="analysis-metrics">
                ${metricCard("得分", result.score ? `${Math.round(Number(result.score))}/100` : "--")}
                ${metricCard("准确率", formatPercentValue(result.timing_accuracy))}
                ${metricCard("漏拍", result.missing_beats || 0)}
                ${metricCard("多拍", result.extra_beats || 0)}
            </div>
            <p class="analysis-subtitle">表现概览</p>
            <div class="analysis-progress-list">
                ${progressBar("准确率", normalizePercent(result.timing_accuracy), "blue")}
                ${progressBar("覆盖率", normalizePercent(result.coverage_ratio), "orange")}
                ${progressBar("稳定性", normalizePercent(result.consistency_ratio || result.user_consistency), "green")}
            </div>
            <div class="analysis-list">
                <div class="analysis-item">
                    <div>
                        <div class="analysis-item-title">偏差</div>
                        <div class="analysis-item-meta">平均值 / 最大值</div>
                    </div>
                    <div class="analysis-item-value">${Math.round(Number(result.mean_deviation_ms || 0))} / ${Math.round(Number(result.max_deviation_ms || 0))} ms</div>
                </div>
                <div class="analysis-item">
                    <div>
                        <div class="analysis-item-title">覆盖率</div>
                        <div class="analysis-item-meta">匹配拍点占比</div>
                    </div>
                    <div class="analysis-item-value">${formatPercentValue(result.coverage_ratio)}</div>
                </div>
                <div class="analysis-item">
                    <div>
                        <div class="analysis-item-title">稳定性</div>
                        <div class="analysis-item-meta">节奏稳定程度</div>
                    </div>
                    <div class="analysis-item-value">${formatPercentValue(result.consistency_ratio || result.user_consistency)}</div>
                </div>
            </div>
            <div class="analysis-note">${escapeHtmlText(result.detailed_assessment || feedback || "暂未返回文字评语。")}</div>
        </div>
    `;
}

function renderAudioLogs() {
    els.audioLogCountBadge.textContent = `${state.audioLogs.length} 条日志`;
    els.audioLogEmpty.hidden = state.audioLogs.length > 0;
    els.audioLogList.innerHTML = "";

    state.audioLogs.forEach((item) => {
        const entry = document.createElement("div");
        entry.className = "export-item";
        entry.innerHTML = `
            <div class="export-row">
                <span class="export-title">${item.file_name || "音频文件"}</span>
                <span class="format-badge">${escapeHtmlText(localizeAudioStage(item.stage || "manual"))}</span>
            </div>
            <div class="export-row">
                <span>${formatDate(item.created_at)}</span>
                <span>${Number(item.duration || 0).toFixed(2)}s / ${item.sample_rate || "--"}Hz</span>
            </div>
        `;
        els.audioLogList.appendChild(entry);
    });
}

function metricCard(label, value) {
    const safeValue = escapeHtmlText(String(value));
    return `
        <div class="analysis-metric">
            <span class="analysis-metric-label">${escapeHtmlText(label)}</span>
            <strong class="analysis-metric-value">${safeValue}</strong>
        </div>
    `;
}

function progressBar(label, value, tone) {
    return `
        <div class="analysis-progress">
            <div class="analysis-progress-head">
                <span>${escapeHtmlText(label)}</span>
                <strong>${escapeHtmlText(formatPercentValue(value))}</strong>
            </div>
            <div class="analysis-progress-track">
                <div class="analysis-progress-fill ${tone}" style="width: ${Math.max(0, Math.min(Number(value) || 0, 100))}%"></div>
            </div>
        </div>
    `;
}

function buildBeatIntervalChart(beats) {
    if (!Array.isArray(beats) || beats.length < 2) {
        return '<div class="analysis-note">至少需要两个拍点才能绘制间隔图。</div>';
    }
    const intervals = beats.slice(1).map((beat, index) => Math.max(Number(beat) - Number(beats[index]), 0));
    const maxInterval = Math.max(...intervals, 0.001);
    return `
        <div class="analysis-mini-chart">
            ${intervals.slice(0, 10).map((interval, index) => {
                const height = Math.max((interval / maxInterval) * 72, 12);
                return `
                    <div class="analysis-column">
                        <div class="analysis-column-bar" style="height: ${height}px"></div>
                        <span class="analysis-column-label">拍${index + 1}</span>
                        <span class="analysis-column-value">${interval.toFixed(2)}</span>
                    </div>
                `;
            }).join("")}
        </div>
    `;
}

function buildTrackCard(track) {
    const name = String(track.name || "other");
    const slug = slugifyTrackName(name);
    const downloadUrl = track.download_url ? buildServerUrl(track.download_url) : "";
    return `
        <div class="analysis-track-card">
            <div class="analysis-track-icon ${slug}">${escapeHtmlText(trackGlyph(name))}</div>
            <div>
                <div class="analysis-track-name">${escapeHtmlText(localizeTrackName(name))}</div>
                <div class="analysis-track-file">${escapeHtmlText(track.file_name || "")}</div>
            </div>
            <div class="analysis-track-meta">${formatSeconds(track.duration)}</div>
            <div class="analysis-track-actions">
                ${downloadUrl ? `<audio controls preload="none" src="${downloadUrl}"></audio>` : '<div class="analysis-note">当前没有可预览音频。</div>'}
                <div class="analysis-track-buttons">
                    ${downloadUrl ? `<a class="analysis-link-button" href="${downloadUrl}" target="_blank" rel="noopener">试听</a>` : ""}
                    ${downloadUrl ? `<a class="analysis-link-button" href="${downloadUrl}" download="${escapeHtmlAttribute(track.file_name || `${name}.wav`)}">下载</a>` : ""}
                </div>
            </div>
        </div>
    `;
}

function buildBeatRuler(beats, duration) {
    if (!Array.isArray(beats) || !beats.length) {
        return '<div class="analysis-note">当前没有拍点，无法绘制节拍尺。</div>';
    }
    const maxBeat = Math.max(...beats.map((item) => Number(item) || 0), 0);
    const totalDuration = Math.max(Number(duration) || maxBeat || 1, 1);
    const tickCount = Math.min(Math.max(Math.ceil(totalDuration), 2), 12);
    const ticks = Array.from({ length: tickCount + 1 }, (_, index) => {
        const value = (totalDuration / tickCount) * index;
        return { left: `${(index / tickCount) * 100}%`, label: `${value.toFixed(1)}秒` };
    });
    const segments = beats.slice(1).map((beat, index) => {
        const start = Number(beats[index]) || 0;
        const end = Number(beat) || start;
        return {
            left: `${(start / totalDuration) * 100}%`,
            width: `${Math.max(((end - start) / totalDuration) * 100, 1.6)}%`,
        };
    });
    return `
        <div class="analysis-ruler">
            <div class="analysis-ruler-line"></div>
            ${segments.map((segment) => `<div class="analysis-ruler-segment" style="left:${segment.left};width:${segment.width};"></div>`).join("")}
            ${ticks.map((tick) => `
                <div class="analysis-ruler-tick" style="left:${tick.left};">
                    <span class="analysis-ruler-tick-label">${tick.label}</span>
                </div>
            `).join("")}
            ${beats.map((beat, index) => `
                <div class="analysis-ruler-marker" style="left:${((Number(beat) || 0) / totalDuration) * 100}%;">
                    <span class="analysis-ruler-label">拍${index + 1}</span>
                </div>
            `).join("")}
        </div>
    `;
}

function buildChordTimeline(chords) {
    if (!Array.isArray(chords) || !chords.length) {
        return '<div class="analysis-note">当前没有和弦建议，无法绘制时间轴。</div>';
    }
    const times = chords.map((item) => Number(item.time) || 0);
    const total = Math.max(times[times.length - 1] || 0, 1) + 2;
    return `
        <div class="analysis-chord-timeline">
            <div class="analysis-chord-track">
                ${chords.map((chord, index) => {
                    const start = Number(chord.time) || 0;
                    const end = index < chords.length - 1 ? Number(chords[index + 1].time) || start + 1 : total;
                    const left = (start / total) * 100;
                    const width = Math.max(((end - start) / total) * 100, 14);
                    return `
                        <div class="analysis-chord-block" style="left:${left}%;width:${width}%;">
                            <span class="analysis-chord-name">${escapeHtmlText(chord.symbol || "--")}</span>
                            <span class="analysis-chord-time">${formatBeat(start)}秒</span>
                        </div>
                    `;
                }).join("")}
            </div>
        </div>
    `;
}

function localizeTrackName(name) {
    const normalized = String(name || "other").toLowerCase();
    const labels = {
        vocal: "人声",
        accompaniment: "伴奏",
        drums: "鼓组",
        bass: "低音",
        guitar: "吉他",
        piano: "钢琴",
        other: "其他",
    };
    return labels[normalized] || name;
}

function localizeAudioStage(stage) {
    const normalized = String(stage || "manual").toLowerCase();
    const labels = {
        manual: "手动",
        upload: "上传",
        "beat-detect": "节拍检测",
        "track-separation": "音轨分离",
        "separate-tracks": "音轨分离",
        "generate-chords": "和弦生成",
        "rhythm-score": "节奏评分",
        export: "导出",
    };
    return labels[normalized] || stage;
}

function localizeTaskStatus(status) {
    const normalized = String(status || "").toLowerCase();
    const labels = {
        ok: "正常",
        ready: "就绪",
        pending: "处理中",
        running: "执行中",
        success: "成功",
        completed: "已完成",
        failed: "失败",
        error: "异常",
    };
    return labels[normalized] || status;
}

function slugifyTrackName(name) {
    const normalized = String(name || "other").toLowerCase();
    if (["vocal", "accompaniment", "drums", "bass", "guitar", "piano", "other"].includes(normalized)) {
        return normalized;
    }
    return "other";
}

function trackGlyph(name) {
    const normalized = String(name || "").toLowerCase();
    const glyphs = {
        vocal: "VO",
        accompaniment: "AC",
        drums: "DR",
        bass: "BA",
        guitar: "GT",
        piano: "PI",
        other: "OT",
    };
    return glyphs[normalized] || normalized.slice(0, 2).toUpperCase() || "OT";
}

function escapeHtmlAttribute(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll('"', "&quot;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}

function buildBeatSummary(beats) {
    if (!beats.length) {
        return "系统没有返回拍点数据。";
    }
    if (beats.length === 1) {
        return `检测到 1 个拍点，出现在 ${formatBeat(beats[0])} 秒。`;
    }
    return `共检测到 ${beats.length} 个拍点，首拍 ${formatBeat(beats[0])} 秒，末拍 ${formatBeat(beats[beats.length - 1])} 秒。`;
}

function formatSeconds(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric <= 0) {
        return "--";
    }
    return `${numeric.toFixed(2)}秒`;
}

function formatPercentValue(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
        return "--";
    }
    return numeric <= 1 ? `${Math.round(numeric * 100)}%` : `${Math.round(numeric)}%`;
}

function normalizePercent(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
        return 0;
    }
    return numeric <= 1 ? numeric * 100 : numeric;
}

function flattenFeedback(feedback) {
    if (typeof feedback === "string") {
        return feedback;
    }
    if (Array.isArray(feedback)) {
        return feedback.join("；");
    }
    if (feedback && typeof feedback === "object") {
        return Object.values(feedback)
            .flatMap((item) => Array.isArray(item) ? item : [item])
            .map((item) => String(item))
            .join("；");
    }
    return "";
}

async function handleCreateExport() {
    if (!state.currentScore || isBusy("create-export")) {
        return;
    }
    setBusy("create-export", true);
    try {
        const created = await requestJson(`/scores/${state.currentScore.score_id}/export`, {
            method: "POST",
            body: {
                format: els.exportFormatSelect.value,
                page_size: els.exportPageSizeSelect.value,
                with_annotations: els.exportAnnotationsInput.checked,
            },
        });
        state.selectedExportRecordId = created.export_record_id;
        state.selectedExportDetail = created;
        await loadExportList(created.export_record_id);
        setAppStatus(`导出已创建：${created.file_name}`);
    } catch (error) {
        setAppStatus(`导出失败：${error.message}`, true);
    } finally {
        setBusy("create-export", false);
    }
}

function queueExportRefresh(preferredId = null) {
    void loadExportList(preferredId, { suppressStatusError: true, suppressDetailStatusError: true });
}

async function loadExportList(preferredId = null, options = {}) {
    if (!state.currentScore || isBusy("load-exports")) {
        return;
    }
    const suppressStatusError = Boolean(options.suppressStatusError);
    const suppressDetailStatusError = Boolean(options.suppressDetailStatusError);
    setBusy("load-exports", true);
    try {
        const listing = await requestJson(`/scores/${state.currentScore.score_id}/exports`);
        state.exportList = listing.items || [];
        const preferred = preferredId ?? state.selectedExportRecordId;
        const nextId =
            preferred && state.exportList.some((item) => item.export_record_id === preferred)
                ? preferred
                : state.exportList[0]?.export_record_id || null;
        state.selectedExportRecordId = nextId;
        state.selectedExportDetail = state.exportList.find((item) => item.export_record_id === nextId) || null;
        renderAll();
        if (nextId) {
            await loadExportDetail(nextId, { suppressStatusError: suppressDetailStatusError });
        }
    } catch (error) {
        state.exportList = [];
        state.selectedExportRecordId = null;
        state.selectedExportDetail = null;
        renderAll();
        if (!suppressStatusError) {
            setAppStatus(`导出历史加载失败：${error.message}`, true);
        } else {
            console.warn("[SeeMusic] export list refresh skipped status update:", error);
        }
    } finally {
        setBusy("load-exports", false);
    }
}

async function loadExportDetail(exportRecordId, options = {}) {
    if (!state.currentScore || !exportRecordId) {
        return;
    }
    const suppressStatusError = Boolean(options.suppressStatusError);
    try {
        state.selectedExportDetail = await requestJson(
            `/scores/${state.currentScore.score_id}/exports/${exportRecordId}`
        );
        state.selectedExportRecordId = exportRecordId;
        renderAll();
    } catch (error) {
        if (!suppressStatusError) {
            setAppStatus(`导出详情加载失败：${error.message}`, true);
        } else {
            console.warn("[SeeMusic] export detail refresh skipped status update:", error);
        }
    }
}

function renderExportList() {
    els.exportCountBadge.textContent = `${state.exportList.length} 条记录`;
    els.exportEmpty.hidden = state.exportList.length > 0;
    els.exportList.innerHTML = "";

    state.exportList.forEach((item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `export-item ${item.export_record_id === state.selectedExportRecordId ? "active" : ""}`;
        button.dataset.exportId = item.export_record_id;
        button.innerHTML = `
            <div class="export-row">
                <span class="export-title">${item.file_name || `导出项 ${item.export_record_id}`}</span>
                <span class="format-badge">${String(item.format || "").toUpperCase()}</span>
            </div>
            <div class="export-row">
                <span>${formatDate(item.updated_at || item.created_at)}</span>
                <span>${item.exists ? formatBytes(item.size_bytes) : "文件缺失"}</span>
            </div>
        `;
        els.exportList.appendChild(button);
    });
}

function renderExportDetail() {
    const detail = state.selectedExportDetail;
    els.previewEmpty.hidden = Boolean(detail);
    els.previewTitle.textContent = detail ? detail.file_name || `导出项 ${detail.export_record_id}` : "尚未选择导出项";
    els.detailFormat.textContent = detail ? String(detail.format || "").toUpperCase() : "--";
    els.detailSize.textContent = detail ? formatBytes(detail.size_bytes) : "--";
    els.detailUpdated.textContent = detail ? formatDate(detail.updated_at || detail.created_at) : "--";
    els.detailStatus.textContent = detail ? (detail.exists ? "可用" : "文件缺失") : "--";
    els.previewStage.innerHTML = "";

    if (!detail) {
        els.previewStage.appendChild(els.previewEmpty);
        return;
    }
    if (!detail.exists) {
        els.previewStage.appendChild(buildPreviewMessage("导出记录存在，但对应文件已经缺失。"));
        return;
    }
    if (detail.content_type === "application/pdf") {
        const frame = document.createElement("iframe");
        frame.className = "preview-frame";
        frame.src = buildServerUrl(detail.preview_url);
        els.previewStage.appendChild(frame);
        return;
    }
    if ((detail.content_type || "").startsWith("image/")) {
        const image = document.createElement("img");
        image.className = "preview-image";
        image.src = buildServerUrl(detail.preview_url);
        image.alt = detail.file_name || "乐谱导出预览";
        els.previewStage.appendChild(image);
        return;
    }
    els.previewStage.appendChild(
        buildPreviewMessage("当前格式暂不支持页内预览，请使用下载按钮在本地打开。")
    );
}

function buildPreviewMessage(message) {
    const wrapper = document.createElement("div");
    wrapper.className = "preview-message";
    wrapper.textContent = message;
    return wrapper;
}

async function handleExportListClick(event) {
    const item = event.target.closest(".export-item");
    if (!item) {
        return;
    }
    await loadExportDetail(Number(item.dataset.exportId));
}

async function handleRegenerateSelectedExport() {
    if (!state.currentScore || !state.selectedExportRecordId || isBusy("regenerate-export")) {
        return;
    }
    setBusy("regenerate-export", true);
    try {
        const regenerated = await requestJson(
            `/scores/${state.currentScore.score_id}/exports/${state.selectedExportRecordId}/regenerate`,
            {
                method: "POST",
                body: {
                    page_size: els.exportPageSizeSelect.value,
                    with_annotations: els.exportAnnotationsInput.checked,
                },
            }
        );
        state.selectedExportDetail = regenerated;
        await loadExportList(state.selectedExportRecordId);
        setAppStatus(`导出已重新生成：${regenerated.file_name}`);
    } catch (error) {
        setAppStatus(`重新生成导出失败：${error.message}`, true);
    } finally {
        setBusy("regenerate-export", false);
    }
}

function handleDownloadSelectedExport() {
    const detail = state.selectedExportDetail;
    if (!detail || !detail.exists) {
        setAppStatus("请先选择一个可下载的导出项。", true);
        return;
    }
    const link = document.createElement("a");
    link.href = buildServerUrl(detail.download_api_url || detail.download_url);
    link.target = "_blank";
    link.rel = "noopener";
    link.click();
}

async function handleDeleteSelectedExport() {
    if (!state.currentScore || !state.selectedExportRecordId || isBusy("delete-export")) {
        return;
    }
    if (!window.confirm("确定删除当前导出记录吗？如果该文件未被其他记录复用，也会一并删除文件。")) {
        return;
    }
    setBusy("delete-export", true);
    try {
        await requestJson(`/scores/${state.currentScore.score_id}/exports/${state.selectedExportRecordId}`, {
            method: "DELETE",
        });
        const deletedId = state.selectedExportRecordId;
        state.selectedExportRecordId = null;
        state.selectedExportDetail = null;
        await loadExportList();
        setAppStatus(`导出记录 ${deletedId} 已删除。`);
    } catch (error) {
        setAppStatus(`删除导出失败：${error.message}`, true);
    } finally {
        setBusy("delete-export", false);
    }
}

function renderControlState() {
    const hasScore = Boolean(state.currentScore);
    const hasExport = Boolean(state.selectedExportDetail);
    const hasAnalysisFile = Boolean(els.analysisFileInput.files?.length);
    const hasScoreFile = Boolean(els.scoreMusicxmlFileInput.files?.length);
    const scorePageCount = Math.max(state.viewerPageCount || 0, 0);
    const canTurnPage = state.viewerTransition.phase === "idle";
    const canGoPrevPage =
        canTurnPage && state.scoreViewerOpen && hasScore && scorePageCount > 1 && (state.scorePageIndex || 0) > 0;
    const canGoNextPage =
        canTurnPage &&
        state.scoreViewerOpen &&
        hasScore &&
        scorePageCount > 1 &&
        (state.scorePageIndex || 0) < scorePageCount - 1;

    els.pingBackendBtn.disabled = isBusy("ping");
    els.createScoreBtn.disabled = isBusy("create-score");
    els.beatDetectBtn.disabled = !hasAnalysisFile || isBusy("beat-detect");
    els.separateTracksBtn.disabled = !hasAnalysisFile || isBusy("separate-tracks");
    els.generateChordsBtn.disabled = !hasScore || isBusy("generate-chords");
    els.rhythmScoreBtn.disabled = isBusy("rhythm-score");
    els.refreshAudioLogsBtn.disabled = isBusy("audio-logs");
    els.applyScoreSettingsBtn.disabled = !hasScore || isBusy("score-settings");
    els.undoBtn.disabled = !hasScore || isBusy("undo-action");
    els.redoBtn.disabled = !hasScore || isBusy("redo-action");
    els.downloadMusicxmlBtn.disabled = !hasScore;
    els.refreshScoreBtn.disabled = !hasScore || isBusy(`score-load-${state.currentScore?.score_id || state.selectedScoreId}`);
    els.replaceScoreFromFileBtn.disabled = !hasScore || !hasScoreFile || isBusy("score-file-replace");
    els.loadScoreFileIntoEditorBtn.disabled = !hasScoreFile;
    els.openScoreViewerBtn.disabled = !hasScore;
    els.closeScoreViewerBtn.disabled = !state.scoreViewerOpen;
    els.scoreViewerPagePrevBtn.disabled = !canGoPrevPage;
    els.scoreViewerPageNextBtn.disabled = !canGoNextPage;
    els.createExportBtn.disabled = !hasScore || isBusy("create-export");
    els.refreshExportsBtn.disabled = !hasScore || isBusy("load-exports");
    els.regenerateSelectedExportBtn.disabled = !hasExport || isBusy("regenerate-export");
    els.downloadSelectedExportBtn.disabled = !hasExport || !state.selectedExportDetail?.exists;
    els.deleteSelectedExportBtn.disabled = !hasExport || isBusy("delete-export");
    els.pitchDetectBtn.disabled = isBusy("pitch-detect") || isBusy("pitch-detect-score");
    els.pitchDetectAndScoreBtn.disabled = isBusy("pitch-detect") || isBusy("pitch-detect-score");
}

function quantizeBeat(value) {
    return Math.max(0.25, Math.round(Number(value) * 4) / 4);
}

function transposePitch(pitch, delta) {
    if (pitch === "Rest") {
        return "Rest";
    }
    const parts = splitPitch(pitch);
    const midi = (parts.octave + 1) * 12 + NOTE_INDEX[parts.note] + delta;
    const octave = Math.floor(midi / 12) - 1;
    const note = SEMITONE_SEQUENCE[((midi % 12) + 12) % 12];
    return `${note}${octave}`;
}

function splitPitch(pitch) {
    const normalized = normalizePitchInput(pitch);
    const match = normalized.match(/^([A-G]#?)(-?\d+)$/);
    return { note: match[1], octave: Number(match[2]) };
}

function formatBeat(value) {
    const numeric = Number(value);
    return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function formatBytes(bytes) {
    const size = Number(bytes || 0);
    if (size === 0) {
        return "0 B";
    }
    if (size < 1024) {
        return `${size} B`;
    }
    if (size < 1024 * 1024) {
        return `${(size / 1024).toFixed(1)} KB`;
    }
    return `${(size / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDate(value) {
    if (!value) {
        return "--";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return new Intl.DateTimeFormat("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    }).format(date);
}

function escapeHtmlText(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}
