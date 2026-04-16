const STORAGE_KEYS = {
    apiBase: "seemusic.transcription.apiBase",
    userId: "seemusic.transcription.userId",
    title: "seemusic.transcription.title",
    analysisId: "seemusic.transcription.analysisId",
    tempo: "seemusic.transcription.tempo",
    timeSignature: "seemusic.transcription.timeSignature",
    keySignature: "seemusic.transcription.keySignature",
    pitchSequence: "seemusic.transcription.pitchSequence",
};

const DEFAULT_BACKEND_ORIGIN = "http://127.0.0.1:8000";
const DEFAULT_API_BASE = `${DEFAULT_BACKEND_ORIGIN}/api/v1`;

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
const STAFF_TOP = 42;
const STAFF_SPACING = 15;
const BOTTOM_LINE_Y = STAFF_TOP + STAFF_SPACING * 4;
const STEP_HEIGHT = STAFF_SPACING / 2;
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
    selectedNoteId: null,
    exportList: [],
    selectedExportRecordId: null,
    selectedExportDetail: null,
    beatDetectResult: null,
    separateTracksResult: null,
    chordGenerationResult: null,
    rhythmScoreResult: null,
    audioLogs: [],
    busyKeys: new Set(),
};

const els = {};

document.addEventListener("DOMContentLoaded", init);

function init() {
    cacheElements();
    hydrateInputs();
    bindEvents();
    setApiBase(els.apiBaseInput.value || resolveDefaultApiBase(), false);
    renderAll();
    checkBackendConnection();
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
        "pitch-detect-btn",
        "pitch-detect-and-score-btn",
        "pitch-detect-status",
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
        "pitch-up-btn",
        "pitch-down-btn",
        "delete-note-btn",
        "clear-note-selection-btn",
        "selected-note-summary",
        "note-measure-input",
        "note-beat-input",
        "note-pitch-input",
        "note-beats-input",
        "add-note-btn",
        "update-note-btn",
        "tempo-display",
        "time-display",
        "key-display",
        "measure-count-display",
        "score-empty",
        "score-canvas",
        "refresh-score-view-btn",
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
    els.userIdInput.value = localStorage.getItem(STORAGE_KEYS.userId) || "1";
    els.projectTitleInput.value = localStorage.getItem(STORAGE_KEYS.title) || "我的智能识谱项目";
    els.analysisIdInput.value = localStorage.getItem(STORAGE_KEYS.analysisId) || "";
    els.tempoInput.value = localStorage.getItem(STORAGE_KEYS.tempo) || "120";
    els.timeSignatureInput.value = localStorage.getItem(STORAGE_KEYS.timeSignature) || "4/4";
    els.keySignatureInput.value = localStorage.getItem(STORAGE_KEYS.keySignature) || "C";
    els.pitchSequenceInput.value =
        localStorage.getItem(STORAGE_KEYS.pitchSequence) || JSON.stringify(DEFAULT_SEQUENCE, null, 2);
    els.noteMeasureInput.value = "1";
    els.noteBeatInput.value = "1";
    els.notePitchInput.value = "C4";
    els.noteBeatsInput.value = "1";
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
    els.pitchUpBtn.addEventListener("click", () => handleTransposeSelected(1));
    els.pitchDownBtn.addEventListener("click", () => handleTransposeSelected(-1));
    els.deleteNoteBtn.addEventListener("click", handleDeleteSelectedNote);
    els.clearNoteSelectionBtn.addEventListener("click", clearNoteSelection);
    els.addNoteBtn.addEventListener("click", handleAddNote);
    els.updateNoteBtn.addEventListener("click", handleUpdateSelectedNote);
    els.refreshScoreViewBtn.addEventListener("click", renderAll);
    els.createExportBtn.addEventListener("click", handleCreateExport);
    els.refreshExportsBtn.addEventListener("click", () => loadExportList(state.selectedExportRecordId));
    els.regenerateSelectedExportBtn.addEventListener("click", handleRegenerateSelectedExport);
    els.downloadSelectedExportBtn.addEventListener("click", handleDownloadSelectedExport);
    els.deleteSelectedExportBtn.addEventListener("click", handleDeleteSelectedExport);
    els.exportList.addEventListener("click", handleExportListClick);

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

async function handlePitchDetect() {
    if (isBusy("pitch-detect")) {
        return;
    }
    setBusy("pitch-detect", true);
    setPitchDetectStatus("");
    try {
        const file = ensurePitchDetectFile();
        const formData = new FormData();
        formData.append("file", file);
        setPitchDetectStatus("正在检测音高序列，请稍候…");
        setAppStatus("正在检测音高序列，请稍候…");
        const result = await requestJson("/pitch/detect", { method: "POST", body: formData });
        const sequence = result.pitch_sequence || [];
        els.pitchSequenceInput.value = JSON.stringify(sequence, null, 2);
        localStorage.setItem(STORAGE_KEYS.pitchSequence, els.pitchSequenceInput.value);
        els.analysisIdInput.value = result.analysis_id || "";
        localStorage.setItem(STORAGE_KEYS.analysisId, els.analysisIdInput.value);
        const msg = `音高检测完成：识别到 ${sequence.length} 个音高点`;
        setPitchDetectStatus(msg);
        setAppStatus(`${msg}，analysis_id=${result.analysis_id}`);
    } catch (error) {
        setPitchDetectStatus(`检测失败：${error.message}`, true);
        setAppStatus(`音高检测失败：${error.message}`, true);
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
        const formData = new FormData();
        formData.append("file", file);
        setPitchDetectStatus("正在检测音高序列…");
        setAppStatus("正在检测音高序列…");
        const detectResult = await requestJson("/pitch/detect", { method: "POST", body: formData });
        const sequence = detectResult.pitch_sequence || [];
        if (!sequence.length) {
            throw new Error("未能从音频中检测到有效的音高序列");
        }
        els.pitchSequenceInput.value = JSON.stringify(sequence, null, 2);
        localStorage.setItem(STORAGE_KEYS.pitchSequence, els.pitchSequenceInput.value);
        els.analysisIdInput.value = detectResult.analysis_id || "";
        localStorage.setItem(STORAGE_KEYS.analysisId, els.analysisIdInput.value);
        setPitchDetectStatus(`检测到 ${sequence.length} 个音高点，正在生成乐谱…`);
        setAppStatus(`检测到 ${sequence.length} 个音高点，正在生成乐谱…`);

        const payload = {
            user_id: parsePositiveInteger(els.userIdInput.value, "用户 ID"),
            title: (els.projectTitleInput.value || "").trim() || null,
            analysis_id: detectResult.analysis_id || null,
            tempo: parsePositiveInteger(els.tempoInput.value, "速度"),
            time_signature: (els.timeSignatureInput.value || "").trim() || "4/4",
            key_signature: (els.keySignatureInput.value || "").trim() || "C",
            pitch_sequence: sequence,
        };
        const created = await requestJson("/score/from-pitch-sequence", { method: "POST", body: payload });
        state.exportList = [];
        state.selectedExportRecordId = null;
        state.selectedExportDetail = null;
        applyScoreResult(created, firstNoteId(created));
        await loadExportList();
        const msg = `音频识谱完成：乐谱 ${created.score_id} 已生成`;
        setPitchDetectStatus(msg);
        setAppStatus(`${msg}，analysis_id=${detectResult.analysis_id}`);
    } catch (error) {
        setPitchDetectStatus(`识谱失败：${error.message}`, true);
        setAppStatus(`音频识谱失败：${error.message}`, true);
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
            user_id: parsePositiveInteger(els.userIdInput.value, "用户 ID"),
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
        applyScoreResult(created, firstNoteId(created));
        await loadExportList();
        setAppStatus(`乐谱已生成并关联：${created.score_id}`);
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

function buildMelodyFromScore() {
    const melody = [];
    for (const measure of state.currentScore?.measures || []) {
        for (const note of measure.notes || []) {
            if (note.is_rest) {
                continue;
            }
            melody.push({
                measure_no: measure.measure_no,
                start_beat: note.start_beat,
                beats: note.beats,
                pitch: note.pitch,
                frequency: note.frequency,
            });
        }
    }
    return melody;
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
    try {
        await patchScore(
            [
                { type: "update_tempo", value: parsePositiveInteger(els.tempoInput.value, "速度") },
                { type: "update_time_signature", value: (els.timeSignatureInput.value || "").trim() || "4/4" },
                { type: "update_key_signature", value: (els.keySignatureInput.value || "").trim() || "C" },
            ],
            "score-settings",
            "乐谱设置已同步。"
        );
    } catch (error) {
        setAppStatus(error.message, true);
    }
}

async function handleAddNote() {
    try {
        const noteDraft = buildNotePayloadFromInputs();
        await patchScore(
            [{ type: "add_note", measure_no: noteDraft.measureNo, beat: noteDraft.note.start_beat, note: noteDraft.note }],
            "note-add",
            "音符已添加到乐谱。",
            { mode: "new", note: noteDraft.note, measureNo: noteDraft.measureNo }
        );
    } catch (error) {
        setAppStatus(error.message, true);
    }
}

async function handleUpdateSelectedNote() {
    if (!state.selectedNoteId) {
        setAppStatus("请先选择一个音符。", true);
        return;
    }
    try {
        const noteDraft = buildNotePayloadFromInputs();
        await patchScore(
            [{ type: "update_note", note_id: state.selectedNoteId, beat: noteDraft.note.start_beat, note: noteDraft.note }],
            "note-update",
            "已更新选中的音符。",
            state.selectedNoteId
        );
    } catch (error) {
        setAppStatus(error.message, true);
    }
}

async function handleDeleteSelectedNote() {
    if (!state.selectedNoteId) {
        setAppStatus("删除前请先选择一个音符。", true);
        return;
    }
    await patchScore([{ type: "delete_note", note_id: state.selectedNoteId }], "note-delete", "已删除选中的音符。");
}

async function handleTransposeSelected(delta) {
    const selected = getSelectedNoteContext();
    if (!selected || selected.note.is_rest) {
        setAppStatus("升降调前请先选择一个有音高的音符。", true);
        return;
    }
    await patchScore(
        [{ type: "update_note", note_id: selected.note.note_id, note: { pitch: transposePitch(selected.note.pitch, delta) } }],
        delta > 0 ? "transpose-up" : "transpose-down",
        `选中的音符已${delta > 0 ? "升高" : "降低"}半音。`,
        selected.note.note_id
    );
}

async function handleUndo() {
    await runScoreAction("undo", "undo-action", "已执行撤销。");
}

async function handleRedo() {
    await runScoreAction("redo", "redo-action", "已执行重做。");
}

async function runScoreAction(path, busyKey, message) {
    if (!state.currentScore || isBusy(busyKey)) {
        return;
    }
    setBusy(busyKey, true);
    try {
        const updated = await requestJson(`/scores/${state.currentScore.score_id}/${path}`, { method: "POST" });
        applyScoreResult(updated, state.selectedNoteId);
        setAppStatus(message);
    } catch (error) {
        setAppStatus(`${message} 操作失败：${error.message}`, true);
    } finally {
        setBusy(busyKey, false);
    }
}

async function patchScore(operations, busyKey, successMessage, preferredNote = null) {
    if (!state.currentScore || isBusy(busyKey)) {
        return;
    }
    setBusy(busyKey, true);
    try {
        const updated = await requestJson(`/scores/${state.currentScore.score_id}`, {
            method: "PATCH",
            body: { operations },
        });
        applyScoreResult(updated, preferredNote);
        setAppStatus(successMessage);
    } catch (error) {
        setAppStatus(`乐谱更新失败：${error.message}`, true);
    } finally {
        setBusy(busyKey, false);
    }
}

function applyScoreResult(score, preferredNote = null) {
    state.currentScore = score;
    els.tempoInput.value = score.tempo;
    els.timeSignatureInput.value = score.time_signature;
    els.keySignatureInput.value = score.key_signature;
    state.selectedNoteId = resolveSelectedNoteId(score, preferredNote);
    if (state.selectedNoteId) {
        populateNoteInputsFromSelection();
    }
    renderAll();
}

function resolveSelectedNoteId(score, preferredNote) {
    if (typeof preferredNote === "string" && findNoteById(score, preferredNote)) {
        return preferredNote;
    }
    if (preferredNote && preferredNote.mode === "new") {
        const match = findMatchingNote(score, preferredNote.measureNo, preferredNote.note);
        if (match) {
            return match.note_id;
        }
    }
    if (state.selectedNoteId && findNoteById(score, state.selectedNoteId)) {
        return state.selectedNoteId;
    }
    return firstNoteId(score);
}

function findMatchingNote(score, measureNo, noteDraft) {
    const measure = (score.measures || []).find((item) => Number(item.measure_no) === Number(measureNo));
    return (measure?.notes || []).find((note) => {
        return (
            note.pitch === noteDraft.pitch &&
            Number(note.start_beat) === Number(noteDraft.start_beat) &&
            Number(note.beats) === Number(noteDraft.beats)
        );
    });
}

function firstNoteId(score) {
    for (const measure of score?.measures || []) {
        if (measure.notes && measure.notes.length > 0) {
            return measure.notes[0].note_id;
        }
    }
    return null;
}

function clearNoteSelection() {
    state.selectedNoteId = null;
    renderAll();
    setAppStatus("已清除音符选中状态。你可以点击某个小节来预填新音符。");
}

function getSelectedNoteContext() {
    return findNoteById(state.currentScore, state.selectedNoteId);
}

function findNoteById(score, noteId) {
    if (!score || !noteId) {
        return null;
    }
    for (const measure of score.measures || []) {
        const note = (measure.notes || []).find((item) => item.note_id === noteId);
        if (note) {
            return { measure, note };
        }
    }
    return null;
}

function populateNoteInputsFromSelection() {
    const selected = getSelectedNoteContext();
    if (!selected) {
        return;
    }
    els.noteMeasureInput.value = selected.measure.measure_no;
    els.noteBeatInput.value = formatBeat(selected.note.start_beat);
    els.notePitchInput.value = selected.note.pitch;
    els.noteBeatsInput.value = formatBeat(selected.note.beats);
}

function renderAll() {
    renderBackendState();
    renderScoreSummary();
    renderScoreCanvas();
    renderAnalysisOutputs();
    renderExportList();
    renderAudioLogs();
    renderExportDetail();
    renderControlState();
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

function renderScoreSummary() {
    const score = state.currentScore;
    const selected = getSelectedNoteContext();

    els.scoreLinkageStatus.textContent = score ? "已连接" : "未连接";
    els.scoreTitleDisplay.textContent = score ? score.title || "未命名乐谱" : "尚未载入乐谱";
    els.scoreIdBadge.textContent = score ? score.score_id : "--";
    els.projectIdBadge.textContent = score ? score.project_id : "--";
    els.scoreVersionBadge.textContent = score ? score.version : "--";
    els.tempoDisplay.textContent = score ? score.tempo : "--";
    els.timeDisplay.textContent = score ? score.time_signature : "--";
    els.keyDisplay.textContent = score ? score.key_signature : "--";
    els.measureCountDisplay.textContent = score ? score.measure_count || score.measures.length : "--";
    els.selectedNoteSummary.textContent = selected
        ? `第 ${selected.measure.measure_no} 小节，第 ${formatBeat(selected.note.start_beat)} 拍，${selected.note.pitch}，时值 ${formatBeat(selected.note.beats)} 拍`
        : "请先在谱面上选择一个音符，或直接新增一个音符。";
}

function renderScoreCanvas() {
    const score = state.currentScore;
    els.scoreEmpty.hidden = Boolean(score);
    els.scoreCanvas.hidden = !score;
    els.scoreCanvas.innerHTML = "";
    if (!score) {
        return;
    }

    score.measures.forEach((measure) => {
        const card = document.createElement("article");
        card.className = "measure-card";

        const header = document.createElement("div");
        header.className = "measure-header";
        header.innerHTML = `<span class="measure-index">第 ${measure.measure_no} 小节</span><span>${formatBeat(measure.used_beats)} / ${formatBeat(measure.total_beats)} 拍</span>`;

        const board = document.createElement("div");
        board.className = "measure-staff-board";
        board.dataset.measureNo = measure.measure_no;
        board.dataset.totalBeats = measure.total_beats;
        board.addEventListener("click", handleScoreCanvasClick);

        for (let index = 0; index < 5; index += 1) {
            const rule = document.createElement("div");
            rule.className = "staff-rule";
            board.appendChild(rule);
        }

        const hint = document.createElement("div");
        hint.className = "click-hint";
        hint.textContent = "点击可预填音符";
        board.appendChild(hint);

        const bar = document.createElement("div");
        bar.className = "measure-bar";
        board.appendChild(bar);

        (measure.notes || []).forEach((note) => board.appendChild(buildNoteElement(note, measure.total_beats)));

        const labels = document.createElement("div");
        labels.className = "score-note-labels";
        (measure.notes || []).forEach((note) => {
            const tag = document.createElement("span");
            tag.className = "note-tag";
            tag.textContent = `${note.pitch} · 第 ${formatBeat(note.start_beat)} 拍`;
            labels.appendChild(tag);
        });

        card.append(header, board, labels);
        els.scoreCanvas.appendChild(card);
    });
}

function buildNoteElement(note, totalBeats) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "score-note";
    button.dataset.noteId = note.note_id;
    if (note.note_id === state.selectedNoteId) {
        button.classList.add("selected");
    }
    button.style.left = `${noteLeftPosition(note, totalBeats)}%`;
    button.style.top = note.is_rest ? `${BOTTOM_LINE_Y - 22}px` : `${noteTopPosition(note.pitch)}px`;
    button.title = `${note.pitch}，第 ${formatBeat(note.start_beat)} 拍，时值 ${formatBeat(note.beats)} 拍`;
    button.addEventListener("click", (event) => {
        event.stopPropagation();
        state.selectedNoteId = note.note_id;
        populateNoteInputsFromSelection();
        renderAll();
    });

    if (note.is_rest) {
        button.appendChild(buildRestElement(note));
        return button;
    }

    const step = pitchToStaffStep(note.pitch);
    const stemDirection = step >= 4 ? "down" : "up";
    appendLedgerLines(button, step);

    const head = document.createElement("span");
    head.className = "score-note-head";
    if (note.beats >= 2) {
        head.classList.add("hollow");
    }
    button.appendChild(head);

    if (note.beats < 4) {
        const stem = document.createElement("span");
        stem.className = `score-note-stem ${stemDirection}`;
        button.appendChild(stem);
    }

    for (let flag = 0; flag < flagCountForBeats(note.beats); flag += 1) {
        const tail = document.createElement("span");
        tail.className = `score-note-tail ${stemDirection}`;
        tail.style.top = `${stemDirection === "up" ? -6 + flag * 8 : 20 - flag * 8}px`;
        button.appendChild(tail);
    }
    return button;
}

function appendLedgerLines(button, step) {
    const steps = [];
    for (let current = -2; current >= step; current -= 2) {
        steps.push(current);
    }
    for (let current = 9; current <= step; current += 2) {
        steps.push(current);
    }
    steps.forEach((ledgerStep) => {
        const line = document.createElement("span");
        line.style.position = "absolute";
        line.style.left = "2px";
        line.style.width = "20px";
        line.style.height = "1px";
        line.style.background = "var(--line-strong)";
        line.style.top = `${BOTTOM_LINE_Y - ledgerStep * STEP_HEIGHT + 13}px`;
        button.appendChild(line);
    });
}

function buildRestElement(note) {
    const variant = restVariantForBeats(note.beats);
    const container = document.createElement("span");
    container.className = "rest-symbol";

    const body = document.createElement("span");
    body.className = `rest-body ${variant}`;
    container.appendChild(body);

    if (variant === "eighth" || variant === "sixteenth") {
        const hook = document.createElement("span");
        hook.className = `rest-hook ${variant}`;
        container.appendChild(hook);
    }
    if (variant === "sixteenth") {
        const secondHook = document.createElement("span");
        secondHook.className = "rest-hook sixteenth-two";
        container.appendChild(secondHook);
    }
    return container;
}

function noteLeftPosition(note, totalBeats) {
    const progress = ((Number(note.start_beat) - 1) + Number(note.beats) / 2) / Math.max(totalBeats, 1);
    return 14 + Math.min(Math.max(progress, 0.04), 0.96) * 72;
}

function noteTopPosition(pitch) {
    return BOTTOM_LINE_Y - pitchToStaffStep(pitch) * STEP_HEIGHT + 12;
}

function pitchToStaffStep(pitch) {
    if (!pitch || pitch === "Rest") {
        return 2;
    }
    const letterMatch = pitch.match(/^([A-G])/);
    const octaveMatch = pitch.match(/(-?\d+)$/);
    if (!letterMatch || !octaveMatch) {
        return 2;
    }
    const letters = ["C", "D", "E", "F", "G", "A", "B"];
    return Number(octaveMatch[1]) * 7 + letters.indexOf(letterMatch[1]) - (4 * 7 + 2);
}

function staffStepToPitch(step) {
    const letters = ["C", "D", "E", "F", "G", "A", "B"];
    const absoluteStep = step + (4 * 7 + 2);
    const letterIndex = ((absoluteStep % 7) + 7) % 7;
    return `${letters[letterIndex]}${Math.floor(absoluteStep / 7)}`;
}

function guessPitchFromBoardY(y) {
    return staffStepToPitch(Math.round((BOTTOM_LINE_Y - y) / STEP_HEIGHT));
}

function flagCountForBeats(beats) {
    if (beats <= 0.25) {
        return 2;
    }
    if (beats <= 0.5) {
        return 1;
    }
    return 0;
}

function restVariantForBeats(beats) {
    if (beats >= 4) {
        return "whole";
    }
    if (beats >= 2) {
        return "half";
    }
    if (beats >= 1) {
        return "quarter";
    }
    if (beats >= 0.5) {
        return "eighth";
    }
    return "sixteenth";
}

function handleScoreCanvasClick(event) {
    const board = event.currentTarget;
    const rect = board.getBoundingClientRect();
    const usableWidth = Math.max(rect.width - 24, 1);
    const x = Math.min(Math.max(event.clientX - rect.left - 12, 0), usableWidth);
    const totalBeats = Number(board.dataset.totalBeats) || 4;

    els.noteMeasureInput.value = board.dataset.measureNo;
    els.noteBeatInput.value = formatBeat(quantizeBeat(1 + (x / usableWidth) * Math.max(totalBeats - 1, 0)));
    els.notePitchInput.value = guessPitchFromBoardY(event.clientY - rect.top);
    state.selectedNoteId = null;
    renderAll();
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

async function loadExportList(preferredId = null) {
    if (!state.currentScore || isBusy("load-exports")) {
        return;
    }
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
            await loadExportDetail(nextId);
        }
    } catch (error) {
        state.exportList = [];
        state.selectedExportRecordId = null;
        state.selectedExportDetail = null;
        renderAll();
        setAppStatus(`导出历史加载失败：${error.message}`, true);
    } finally {
        setBusy("load-exports", false);
    }
}

async function loadExportDetail(exportRecordId) {
    if (!state.currentScore || !exportRecordId) {
        return;
    }
    try {
        state.selectedExportDetail = await requestJson(
            `/scores/${state.currentScore.score_id}/exports/${exportRecordId}`
        );
        state.selectedExportRecordId = exportRecordId;
        renderAll();
    } catch (error) {
        setAppStatus(`导出详情加载失败：${error.message}`, true);
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
    const hasSelectedNote = Boolean(getSelectedNoteContext());
    const hasExport = Boolean(state.selectedExportDetail);
    const hasAnalysisFile = Boolean(els.analysisFileInput.files?.length);

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
    els.pitchUpBtn.disabled = !hasSelectedNote || isBusy("transpose-up");
    els.pitchDownBtn.disabled = !hasSelectedNote || isBusy("transpose-down");
    els.deleteNoteBtn.disabled = !hasSelectedNote || isBusy("note-delete");
    els.updateNoteBtn.disabled = !hasSelectedNote || isBusy("note-update");
    els.addNoteBtn.disabled = !hasScore || isBusy("note-add");
    els.refreshScoreViewBtn.disabled = !hasScore;
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
