const STORAGE_KEYS = {
    apiBase: "seemusic.transcription.apiBase",
    userId: "seemusic.transcription.userId",
    title: "seemusic.transcription.title",
    analysisId: "seemusic.transcription.analysisId",
    instrumentType: "seemusic.transcription.instrumentType",
    pianoResultMode: "seemusic.transcription.pianoResultMode",
    jianpuLayoutMode: "seemusic.transcription.jianpuLayoutMode",
    jianpuAnnotationLayer: "seemusic.transcription.jianpuAnnotationLayer",
    guitarViewMode: "seemusic.transcription.guitarViewMode",
    guitarDebugExpanded: "seemusic.transcription.guitarDebugExpanded",
    guzhengDebugExpanded: "seemusic.transcription.guzhengDebugExpanded",
    diziDebugExpanded: "seemusic.transcription.diziDebugExpanded",
    diziFluteType: "seemusic.transcription.diziFluteType",
    scoreId: "seemusic.transcription.scoreId",
    tempo: "seemusic.transcription.tempo",
    timeSignature: "seemusic.transcription.timeSignature",
    keySignature: "seemusic.transcription.keySignature",
    pitchSequence: "seemusic.transcription.pitchSequence",
};

const TRANSCRIPTION_UI_BUILD = "2026-04-19-traditional-lilypond-renderer-v1";
const DEFAULT_BACKEND_ORIGIN = "http://127.0.0.1:8000";
const DEFAULT_API_BASE = `${DEFAULT_BACKEND_ORIGIN}/api/v1`;
const MIN_RELIABLE_BEAT_CONFIDENCE = 0.05;
const MIN_RELIABLE_BEAT_COUNT = 3;
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
const DEFAULT_TRANSCRIPTION_SETTINGS = {
    tempo: 120,
    timeSignature: "4/4",
    keySignature: "C",
};
const SUPPORTED_INSTRUMENT_TYPES = new Set(["piano", "guzheng", "guitar", "dizi"]);
const SUPPORTED_PIANO_RESULT_MODES = new Set(["arranged"]);
const SUPPORTED_JIANPU_LAYOUT_MODES = new Set(["preview", "print"]);
const SUPPORTED_JIANPU_ANNOTATION_LAYERS = new Set(["basic", "fingering", "technique", "all"]);
const SUPPORTED_GUITAR_VIEW_MODES = new Set(["screen", "print"]);
const SUPPORTED_DIZI_FLUTE_TYPES = new Set(["C", "D", "E", "F", "G", "A", "Bb"]);

const state = {
    apiBase: "",
    backendHealthy: false,
    instrumentType: "piano",
    pianoResultMode: "arranged",
    jianpuLayoutMode: "preview",
    jianpuAnnotationLayer: "basic",
    guitarViewMode: "screen",
    guitarDebugExpanded: false,
    guzhengDebugExpanded: false,
    diziDebugExpanded: false,
    guitarHighlightedChordSymbol: "",
    currentScore: null,
    guzhengResult: null,
    guzhengEngravedPreview: null,
    guitarLeadSheetResult: null,
    diziResult: null,
    diziEngravedPreview: null,
    diziFluteType: "G",
    preferredTempo: DEFAULT_TRANSCRIPTION_SETTINGS.tempo,
    preferredTimeSignature: DEFAULT_TRANSCRIPTION_SETTINGS.timeSignature,
    preferredKeySignature: DEFAULT_TRANSCRIPTION_SETTINGS.keySignature,
    latestPitchSequence: [],
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
        "linkage-label",
        "score-linkage-status",
        "user-id-input",
        "project-title-input",
        "analysis-id-input",
        "dizi-flute-type-field",
        "dizi-flute-type-input",
        "instrument-toggle",
        "piano-result-switch",
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
        "score-summary-panel",
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
        "preview-panel-title",
        "preview-panel-copy",
        "score-editor-grid",
        "score-empty",
        "score-viewer-entry",
        "guzheng-score-empty",
        "guzheng-score-view",
        "guitar-lead-sheet-empty",
        "guitar-lead-sheet-view",
        "dizi-score-empty",
        "dizi-score-view",
        "analysis-panel-title",
        "analysis-panel-copy",
        "piano-analysis-grid",
        "guzheng-debug-panel",
        "guitar-debug-panel",
        "dizi-debug-panel",
        "export-score-pdf-btn",
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
        "export-workbench-panel",
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
    els.instrumentToggleButtons = Array.from(document.querySelectorAll("[data-instrument-type]"));
    els.pianoResultModeButtons = Array.from(document.querySelectorAll("[data-piano-result-mode]"));
}

function hydrateInputs() {
    els.apiBaseInput.value = loadPreferredApiBase();
    els.userIdInput.value = String(resolveCachedScoreOwnerUserId() || localStorage.getItem(STORAGE_KEYS.userId) || "");
    els.projectTitleInput.value = localStorage.getItem(STORAGE_KEYS.title) || "我的智能识谱项目";
    els.analysisIdInput.value = localStorage.getItem(STORAGE_KEYS.analysisId) || "";
    state.instrumentType = resolveInstrumentType(localStorage.getItem(STORAGE_KEYS.instrumentType) || "piano");
    state.pianoResultMode = resolvePianoResultMode(localStorage.getItem(STORAGE_KEYS.pianoResultMode) || "arranged");
    state.jianpuLayoutMode = resolveJianpuLayoutMode(localStorage.getItem(STORAGE_KEYS.jianpuLayoutMode) || "preview");
    state.jianpuAnnotationLayer = resolveJianpuAnnotationLayer(localStorage.getItem(STORAGE_KEYS.jianpuAnnotationLayer) || "basic");
    state.guitarViewMode = resolveGuitarViewMode(localStorage.getItem(STORAGE_KEYS.guitarViewMode) || "screen");
    state.guitarDebugExpanded = localStorage.getItem(STORAGE_KEYS.guitarDebugExpanded) === "true";
    state.guzhengDebugExpanded = localStorage.getItem(STORAGE_KEYS.guzhengDebugExpanded) === "true";
    state.diziDebugExpanded = localStorage.getItem(STORAGE_KEYS.diziDebugExpanded) === "true";
    state.diziFluteType = resolveDiziFluteType(localStorage.getItem(STORAGE_KEYS.diziFluteType) || "G");
    state.preferredTempo = parseStoredTempo(localStorage.getItem(STORAGE_KEYS.tempo));
    state.preferredTimeSignature = normalizeTimeSignature(localStorage.getItem(STORAGE_KEYS.timeSignature));
    state.preferredKeySignature = normalizeKeySignature(localStorage.getItem(STORAGE_KEYS.keySignature));
    state.latestPitchSequence = loadStoredPitchSequence();
    if (els.diziFluteTypeInput) {
        els.diziFluteTypeInput.value = state.diziFluteType;
    }
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

function resolveInstrumentType(value) {
    const normalized = String(value || "").trim().toLowerCase();
    return SUPPORTED_INSTRUMENT_TYPES.has(normalized) ? normalized : "piano";
}

function resolvePianoResultMode(value) {
    void value;
    return "arranged";
}

function resolveJianpuLayoutMode(value) {
    const normalized = String(value || "").trim().toLowerCase();
    return SUPPORTED_JIANPU_LAYOUT_MODES.has(normalized) ? normalized : "preview";
}

function resolveJianpuAnnotationLayer(value) {
    const normalized = String(value || "").trim().toLowerCase();
    return SUPPORTED_JIANPU_ANNOTATION_LAYERS.has(normalized) ? normalized : "basic";
}

function resolveTraditionalMarkupMode(value) {
    return resolveJianpuAnnotationLayer(value) === "basic" ? "plain" : "annotated";
}

function resolveGuitarViewMode(value) {
    const normalized = String(value || "").trim().toLowerCase();
    return SUPPORTED_GUITAR_VIEW_MODES.has(normalized) ? normalized : "screen";
}

function resolveDiziFluteType(value) {
    const raw = String(value || "").trim().replace("♭", "b");
    if (!raw) {
        return "G";
    }
    const lowered = raw.toLowerCase();
    if (lowered === "bb") {
        return "Bb";
    }
    const upper = raw.toUpperCase();
    if (upper === "BB") {
        return "Bb";
    }
    return SUPPORTED_DIZI_FLUTE_TYPES.has(upper) ? upper : "G";
}

function parseStoredTempo(value) {
    const parsed = Number.parseInt(String(value || "").trim(), 10);
    if (!Number.isFinite(parsed) || parsed <= 0) {
        return DEFAULT_TRANSCRIPTION_SETTINGS.tempo;
    }
    return parsed;
}

function normalizeTimeSignature(value) {
    const normalized = String(value || "").trim();
    return normalized || DEFAULT_TRANSCRIPTION_SETTINGS.timeSignature;
}

function normalizeKeySignature(value) {
    const normalized = String(value || "").trim();
    return normalized || DEFAULT_TRANSCRIPTION_SETTINGS.keySignature;
}

function loadStoredPitchSequence() {
    const raw = localStorage.getItem(STORAGE_KEYS.pitchSequence);
    if (!raw) {
        return [...DEFAULT_SEQUENCE];
    }
    try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [...DEFAULT_SEQUENCE];
    } catch {
        return [...DEFAULT_SEQUENCE];
    }
}

function setLatestPitchSequence(sequence, { persist = true } = {}) {
    state.latestPitchSequence = Array.isArray(sequence) ? sequence : [];
    if (persist) {
        setLocalStorageSafely(STORAGE_KEYS.pitchSequence, JSON.stringify(state.latestPitchSequence), { silent: true });
    }
}

function isGuitarMode() {
    return resolveInstrumentType(state.instrumentType) === "guitar";
}

function isGuzhengMode() {
    return resolveInstrumentType(state.instrumentType) === "guzheng";
}

function isDiziMode() {
    return resolveInstrumentType(state.instrumentType) === "dizi";
}

function isPianoMode() {
    return resolveInstrumentType(state.instrumentType) === "piano";
}

function isCustomLeadSheetMode() {
    return isGuitarMode() || isGuzhengMode() || isDiziMode();
}

function isPianoArrangementMode() {
    return true;
}

function resolvePianoArrangementModeValue() {
    return "piano_solo";
}

function resolvePianoResultModeFromScore(score) {
    void score;
    return "arranged";
}

function setInstrumentType(value, { persist = true, announce = false } = {}) {
    const resolved = resolveInstrumentType(value);
    state.instrumentType = resolved;
    if (persist) {
        localStorage.setItem(STORAGE_KEYS.instrumentType, resolved);
    }
    if (resolved !== "piano" && state.scoreViewerOpen) {
        closeScoreViewer();
    }
    if (announce) {
        setAppStatus(
            resolved === "guitar"
                ? "已切换到吉他弹唱谱模式。主流程会优先展示 lead sheet 正文，并把和弦图、扫弦和识谱过程放到辅助区。"
                : resolved === "guzheng"
                    ? "已切换到古筝谱模式。主流程会优先展示连续简谱正文，并把弦位与技法放进可切换的辅助标注层。"
                    : resolved === "dizi"
                        ? `已切换到笛子谱模式。当前按 ${localizeFluteType(state.diziFluteType)} 展示连续简谱，并把指法与技法放进共享标注层。`
                    : "已切换到钢琴五线谱模式。当前固定输出带左手伴奏的双手钢琴谱。"
        );
    }
}

function setPianoResultMode(value, { persist = true, announce = false } = {}) {
    void value;
    const resolved = "arranged";
    state.pianoResultMode = resolved;
    if (persist) {
        localStorage.setItem(STORAGE_KEYS.pianoResultMode, resolved);
    }
    if (announce) {
        setAppStatus("钢琴模式固定输出双手钢琴谱。下一次生成会继续保留左手织体与双手分配。");
    }
}

function setJianpuLayoutMode(value, { persist = true, announce = false } = {}) {
    const resolved = resolveJianpuLayoutMode(value);
    state.jianpuLayoutMode = resolved;
    if (persist) {
        localStorage.setItem(STORAGE_KEYS.jianpuLayoutMode, resolved);
    }
    if (announce) {
        setAppStatus(
            resolved === "print"
                ? "已切换到简谱打印视图。古筝和笛子的正文会更接近分页排版，方便打印或继续润色。"
                : "已切换到简谱预览视图。古筝和笛子的正文会优先保证屏幕浏览时的清晰度。"
        );
    }
}

function setJianpuAnnotationLayer(value, { persist = true, announce = false } = {}) {
    const resolved = resolveJianpuAnnotationLayer(value);
    state.jianpuAnnotationLayer = resolved;
    if (persist) {
        localStorage.setItem(STORAGE_KEYS.jianpuAnnotationLayer, resolved);
    }
    if (announce) {
        const labelMap = {
            basic: "基础正文层",
            fingering: "指法/弦位层",
            technique: "技法提示层",
            all: "完整标注层",
        };
        setAppStatus(`已切换到${labelMap[resolved] || "基础正文层"}。`);
    }
}

function setTraditionalMarkupMode(value, { announce = false } = {}) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "plain") {
        setJianpuAnnotationLayer("basic", { persist: true, announce: false });
        if (announce) {
            setAppStatus("已切换到纯净简谱，只保留单音本身，不显示额外标注。");
        }
        return;
    }

    if (normalized === "annotated") {
        const currentLayer = resolveJianpuAnnotationLayer(state.jianpuAnnotationLayer);
        setJianpuAnnotationLayer(currentLayer === "basic" ? "all" : currentLayer, { persist: true, announce: false });
        if (announce) {
            setAppStatus("已切换到带标注简谱，会显示当前可用的弦位、指法和技法提示。");
        }
    }
}

function setGuitarViewMode(value, { persist = true, announce = false } = {}) {
    const resolved = resolveGuitarViewMode(value);
    state.guitarViewMode = resolved;
    if (persist) {
        localStorage.setItem(STORAGE_KEYS.guitarViewMode, resolved);
    }
    if (announce) {
        setAppStatus(
            resolved === "print"
                ? "已切换到吉他打印视图。正文会更接近分页打印排版，方便导出或打印。"
                : "已切换到吉他屏幕视图。正文会优先保证浏览和弹唱时的清晰度。"
        );
    }
}

function setGuitarDebugExpanded(value, { persist = true } = {}) {
    state.guitarDebugExpanded = Boolean(value);
    if (persist) {
        localStorage.setItem(STORAGE_KEYS.guitarDebugExpanded, state.guitarDebugExpanded ? "true" : "false");
    }
}

function setGuzhengDebugExpanded(value, { persist = true } = {}) {
    state.guzhengDebugExpanded = Boolean(value);
    if (persist) {
        localStorage.setItem(STORAGE_KEYS.guzhengDebugExpanded, state.guzhengDebugExpanded ? "true" : "false");
    }
}

function setDiziDebugExpanded(value, { persist = true } = {}) {
    state.diziDebugExpanded = Boolean(value);
    if (persist) {
        localStorage.setItem(STORAGE_KEYS.diziDebugExpanded, state.diziDebugExpanded ? "true" : "false");
    }
}

function setGuitarHighlightedChordSymbol(value) {
    state.guitarHighlightedChordSymbol = String(value || "").trim();
}

function setDiziFluteType(value, { persist = true, announce = false } = {}) {
    const resolved = resolveDiziFluteType(value);
    state.diziFluteType = resolved;
    if (els.diziFluteTypeInput && els.diziFluteTypeInput.value !== resolved) {
        els.diziFluteTypeInput.value = resolved;
    }
    if (persist) {
        localStorage.setItem(STORAGE_KEYS.diziFluteType, resolved);
    }
    if (announce) {
        setAppStatus(`笛型已切换为 ${resolved} 调笛。下一次生成会按该笛型的筒音关系显示简谱与指法。`);
    }
}

function resolveTraditionalResult(instrumentType) {
    return instrumentType === "dizi" ? state.diziResult : state.guzhengResult;
}

function resolveTraditionalEngravedPreview(instrumentType) {
    return instrumentType === "dizi" ? state.diziEngravedPreview : state.guzhengEngravedPreview;
}

function setTraditionalEngravedPreview(instrumentType, preview) {
    if (instrumentType === "dizi") {
        state.diziEngravedPreview = preview;
        return;
    }
    state.guzhengEngravedPreview = preview;
}

function buildTraditionalPreviewSignature(instrumentType, result) {
    const ir = result?.jianpu_ir && typeof result.jianpu_ir === "object" ? result.jianpu_ir : {};
    const stats = ir.statistics && typeof ir.statistics === "object" ? ir.statistics : {};
    const pitchRange = result?.pitch_range || {};
    return JSON.stringify({
        instrument: instrumentType,
        layoutMode: resolveJianpuLayoutMode(state.jianpuLayoutMode),
        annotationLayer: resolveJianpuAnnotationLayer(state.jianpuAnnotationLayer),
        fluteType: instrumentType === "dizi" ? resolveDiziFluteType(result?.flute_type || state.diziFluteType) : "",
        title: result?.title || "",
        key: result?.key || "",
        tempo: result?.tempo || 0,
        timeSignature: result?.time_signature || "4/4",
        measureCount: Number(stats.measure_count || result?.measures?.length || 0),
        noteCount: Number(stats.note_count || result?.melody_size || 0),
        lowest: pitchRange?.lowest || "",
        highest: pitchRange?.highest || "",
    });
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

function handleInstrumentTypeChange(event) {
    const nextType = event.currentTarget?.dataset?.instrumentType;
    if (!nextType) {
        return;
    }
    setInstrumentType(nextType, { announce: true });
    renderAll();
}

function handlePianoResultModeChange(event) {
    const nextMode = event.currentTarget?.dataset?.pianoResultMode;
    if (!nextMode) {
        return;
    }
    setPianoResultMode(nextMode, { announce: true });
    renderAll();
}

function handleDiziFluteTypeChange(event) {
    const nextType = event.currentTarget?.value;
    setDiziFluteType(nextType, { announce: true });
    renderAll();
}

async function handleTraditionalScoreInteraction(event) {
    const activeInstrument = isGuzhengMode() ? "guzheng" : "dizi";
    const exportButton = event.target.closest("[data-traditional-export-format]");
    if (exportButton) {
        const exportFormat = String(exportButton.dataset.traditionalExportFormat || "").trim();
        if (exportFormat) {
            await requestTraditionalExport(activeInstrument, exportFormat);
        }
        return;
    }

    const markupButton = event.target.closest("[data-jianpu-markup-mode]");
    if (markupButton) {
        setTraditionalMarkupMode(markupButton.dataset.jianpuMarkupMode, { announce: true });
        renderAll();
        if (resolveTraditionalResult(activeInstrument)) {
            await requestTraditionalEngravedPreview(activeInstrument, { force: true, silent: true });
        }
        return;
    }

    const layoutButton = event.target.closest("[data-jianpu-layout-mode]");
    if (layoutButton) {
        setJianpuLayoutMode(layoutButton.dataset.jianpuLayoutMode, { announce: true });
        renderAll();
        if (resolveTraditionalResult(activeInstrument)) {
            await requestTraditionalEngravedPreview(activeInstrument, { force: true, silent: true });
        }
        return;
    }

    const annotationButton = event.target.closest("[data-jianpu-annotation-layer]");
    if (annotationButton) {
        setJianpuAnnotationLayer(annotationButton.dataset.jianpuAnnotationLayer, { announce: true });
        renderAll();
        if (resolveTraditionalResult(activeInstrument)) {
            await requestTraditionalEngravedPreview(activeInstrument, { force: true, silent: true });
        }
    }
}

function handleTraditionalScoreInputChange(event) {
    const fluteTypeInput = event.target.closest("[data-dizi-inline-flute-type]");
    if (!fluteTypeInput) {
        return;
    }
    setDiziFluteType(fluteTypeInput.value, { announce: true });
    renderAll();
}

function handleGuitarLeadSheetInteraction(event) {
    const exportButton = event.target.closest("[data-guitar-export-format]");
    if (exportButton) {
        const exportFormat = String(exportButton.dataset.guitarExportFormat || "").trim();
        if (exportFormat) {
            void requestGuitarLeadSheetExport(exportFormat);
        }
        return;
    }

    const modeButton = event.target.closest("[data-guitar-view-mode]");
    if (modeButton) {
        setGuitarViewMode(modeButton.dataset.guitarViewMode, { announce: true });
        renderAll();
        return;
    }

    const debugToggle = event.target.closest("[data-guitar-toggle-debug]");
    if (debugToggle) {
        setGuitarDebugExpanded(!state.guitarDebugExpanded);
        renderAnalysisOutputs();
        renderGuitarLeadSheetPanel();
        return;
    }

    const chordButton = event.target.closest("[data-guitar-chord-symbol]");
    if (!chordButton) {
        return;
    }
    const chordSymbol = String(chordButton.dataset.guitarChordSymbol || "").trim();
    setGuitarHighlightedChordSymbol(state.guitarHighlightedChordSymbol === chordSymbol ? "" : chordSymbol);
    renderGuitarLeadSheetPanel();
}

function handleGuitarDebugPanelInteraction(event) {
    const debugToggle = event.target.closest("[data-guitar-toggle-debug]");
    if (!debugToggle) {
        return;
    }
    setGuitarDebugExpanded(!state.guitarDebugExpanded);
    renderAnalysisOutputs();
    renderGuitarLeadSheetPanel();
}

function handleGuzhengDebugPanelInteraction(event) {
    const debugToggle = event.target.closest("[data-guzheng-toggle-debug]");
    if (!debugToggle) {
        return;
    }
    setGuzhengDebugExpanded(!state.guzhengDebugExpanded);
    renderAnalysisOutputs();
}

function handleDiziDebugPanelInteraction(event) {
    const debugToggle = event.target.closest("[data-dizi-toggle-debug]");
    if (!debugToggle) {
        return;
    }
    setDiziDebugExpanded(!state.diziDebugExpanded);
    renderAnalysisOutputs();
}

function bindEvents() {
    els.saveApiBaseBtn.addEventListener("click", handleSaveApiBase);
    els.pingBackendBtn.addEventListener("click", checkBackendConnection);
    els.createScoreBtn.addEventListener("click", handleCreateScore);
    els.pitchDetectBtn.addEventListener("click", handlePitchDetect);
    els.pitchDetectAndScoreBtn.addEventListener("click", handlePitchDetectAndScore);
    els.beatDetectBtn.addEventListener("click", handleBeatDetect);
    els.separateTracksBtn.addEventListener("click", handleSeparateTracks);
    els.generateChordsBtn.addEventListener("click", handleGenerateChords);
    els.instrumentToggleButtons.forEach((button) => button.addEventListener("click", handleInstrumentTypeChange));
    els.pianoResultModeButtons.forEach((button) => button.addEventListener("click", handlePianoResultModeChange));
    els.diziFluteTypeInput?.addEventListener("change", handleDiziFluteTypeChange);
    els.guzhengScoreView?.addEventListener("click", handleTraditionalScoreInteraction);
    els.guitarLeadSheetView?.addEventListener("click", handleGuitarLeadSheetInteraction);
    els.diziScoreView?.addEventListener("change", handleTraditionalScoreInputChange);
    els.diziScoreView?.addEventListener("click", handleTraditionalScoreInteraction);
    els.guzhengDebugPanel?.addEventListener("click", handleGuzhengDebugPanelInteraction);
    els.guitarDebugPanel?.addEventListener("click", handleGuitarDebugPanelInteraction);
    els.diziDebugPanel?.addEventListener("click", handleDiziDebugPanelInteraction);
    els.rhythmScoreBtn.addEventListener("click", handleRhythmScore);
    els.refreshAudioLogsBtn.addEventListener("click", () => loadAudioLogs());
    els.applyScoreSettingsBtn.addEventListener("click", handleApplyScoreSettings);
    els.undoBtn.addEventListener("click", handleUndo);
    els.redoBtn.addEventListener("click", handleRedo);
    els.downloadMusicxmlBtn.addEventListener("click", handleDownloadMusicxml);
    els.refreshScoreBtn.addEventListener("click", handleRefreshScore);
    els.replaceScoreFromFileBtn.addEventListener("click", handleReplaceScoreFromFile);
    els.loadScoreFileIntoEditorBtn.addEventListener("click", handleLoadScoreFileIntoEditor);
    els.exportScorePdfBtn.addEventListener("click", handleExportScorePdf);
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
        [els.diziFluteTypeInput, STORAGE_KEYS.diziFluteType],
    ].forEach(([element, key]) => {
        if (!element) {
            return;
        }
        element.addEventListener("input", () => setLocalStorageSafely(key, element.value, { silent: true }));
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
        setLocalStorageSafely(STORAGE_KEYS.apiBase, state.apiBase, { silent: true });
    }
}

function isStorageQuotaExceededError(error) {
    return (
        error instanceof DOMException &&
        (error.name === "QuotaExceededError" || error.name === "NS_ERROR_DOM_QUOTA_REACHED" || error.code === 22)
    );
}

function setLocalStorageSafely(key, value, { silent = false } = {}) {
    try {
        localStorage.setItem(key, value);
        return true;
    } catch (error) {
        if (!isStorageQuotaExceededError(error)) {
            throw error;
        }
        if (!silent) {
            setAppStatus("本地缓存空间不足：结果已生成，但未写入浏览器缓存。可清理缓存后重试。", true);
        }
        return false;
    }
}

function triggerFileDownload(url, fileName = "") {
    if (!url) {
        return;
    }
    const link = document.createElement("a");
    link.href = url;
    if (fileName) {
        link.download = fileName;
    }
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
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
    if (!Array.isArray(state.latestPitchSequence) || state.latestPitchSequence.length === 0) {
        throw new Error("请先通过音频识别获得音高序列");
    }
    return state.latestPitchSequence;
}

function parsePitchSequenceOrEmpty() {
    if (!Array.isArray(state.latestPitchSequence) || state.latestPitchSequence.length === 0) {
        return [];
    }
    return state.latestPitchSequence;
}

function resolveCustomLeadSheetSource({ allowScoreFallback = true } = {}) {
    const pitchSequence = parsePitchSequenceOrEmpty();
    if (pitchSequence.length) {
        return { analysisId: null, pitchSequence, scoreId: null };
    }
    const analysisId = (els.analysisIdInput.value || "").trim() || null;
    if (analysisId) {
        return { analysisId, pitchSequence: [], scoreId: null };
    }
    if (allowScoreFallback && state.currentScore?.score_id) {
        return { analysisId: null, pitchSequence: [], scoreId: state.currentScore.score_id };
    }
    return { analysisId: null, pitchSequence: [], scoreId: null };
}

function resolveCustomLeadSheetBase(scoreId = null) {
    const usingScoreSource = Boolean(scoreId);
    const fallbackTempo = Number(state.preferredTempo) || DEFAULT_TRANSCRIPTION_SETTINGS.tempo;
    const fallbackTimeSignature = normalizeTimeSignature(state.preferredTimeSignature);
    const fallbackKeySignature = normalizeKeySignature(state.preferredKeySignature);
    return {
        title: (els.projectTitleInput.value || "").trim() || null,
        key: (
            usingScoreSource
                ? state.currentScore?.key_signature || fallbackKeySignature
                : fallbackKeySignature
        ).trim() || null,
        tempo: parsePositiveInteger(String(usingScoreSource ? state.currentScore?.tempo || fallbackTempo : fallbackTempo), "速度"),
        timeSignature: (
            usingScoreSource ? state.currentScore?.time_signature || fallbackTimeSignature : fallbackTimeSignature
        ).trim() || DEFAULT_TRANSCRIPTION_SETTINGS.timeSignature,
    };
}

function hidePianoPreviewSurfaces() {
    els.scoreEmpty.hidden = true;
    els.scoreViewerEntry.hidden = true;
    els.scoreViewerEntry.innerHTML = "";
    state.previewPageCount = 0;
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

function applyDetectedKeySignature(keySignature) {
    const resolved = String(keySignature || "").trim();
    if (!resolved) {
        return "";
    }
    state.preferredKeySignature = normalizeKeySignature(resolved);
    localStorage.setItem(STORAGE_KEYS.keySignature, resolved);
    return resolved;
}

function ensurePitchDetectFile() {
    const file = els.pitchDetectFileInput.files?.[0];
    if (!file) {
        throw new Error("请先在上方选择音频文件");
    }
    return file;
}

function activeResultLabel() {
    if (isGuitarMode()) {
        return "吉他弹唱谱";
    }
    if (isGuzhengMode()) {
        return "古筝谱";
    }
    if (isDiziMode()) {
        return "笛子谱";
    }
    return "乐谱";
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

function buildBeatDetectFormData(file) {
    const formData = new FormData();
    formData.append("file", file);
    if (els.beatBpmHintInput.value) {
        formData.append("bpm_hint", els.beatBpmHintInput.value);
    }
    formData.append("sensitivity", els.beatSensitivityInput.value || "0.5");
    return formData;
}

function applyDetectedTempo(tempo, { persist = true } = {}) {
    const numericTempo = Number(tempo);
    if (!Number.isFinite(numericTempo) || numericTempo <= 0) {
        return null;
    }
    const resolvedTempo = Math.max(1, Math.round(numericTempo));
    state.preferredTempo = resolvedTempo;
    if (persist) {
        localStorage.setItem(STORAGE_KEYS.tempo, String(resolvedTempo));
    }
    return resolvedTempo;
}

function resolveReliableBeatTempo(result) {
    const bpm = Number(result?.bpm || 0);
    const confidence = Number(result?.beat_quality?.confidence || 0);
    const beatCount = Number(
        result?.num_beats || (Array.isArray(result?.beat_times) ? result.beat_times.length : 0)
    );
    if (!Number.isFinite(bpm) || bpm <= 0) {
        return null;
    }
    if (!Number.isFinite(confidence) || confidence < MIN_RELIABLE_BEAT_CONFIDENCE) {
        return null;
    }
    if (!Number.isFinite(beatCount) || beatCount < MIN_RELIABLE_BEAT_COUNT) {
        return null;
    }
    return Math.round(bpm);
}

async function requestBeatDetect(file, { syncAnalysisId = true, refreshAudioLogs = false } = {}) {
    const formData = buildBeatDetectFormData(file);
    const result = await requestJson("/rhythm/beat-detect", { method: "POST", body: formData });
    state.beatDetectResult = result;
    if (syncAnalysisId) {
        els.analysisIdInput.value = result.analysis_id || els.analysisIdInput.value;
        setLocalStorageSafely(STORAGE_KEYS.analysisId, els.analysisIdInput.value, { silent: true });
    }
    if (els.userBeatsInput) {
        els.userBeatsInput.value = JSON.stringify(result.beats || result.beat_times || [], null, 2);
    }
    renderAll();
    if (refreshAudioLogs) {
        await loadAudioLogs();
    }
    return result;
}

async function requestPianoScoreFromAudio(file) {
    const config = getPitchDetectConfig();
    const resolvedUserId = await ensureScoreOwnerUserId();
    setAnalysisToolsOpen(true);
    const arrangementMode = resolvePianoArrangementModeValue();
    const defaultTitle = "Untitled Piano Arrangement";
    const formData = new FormData();
    formData.append("file", file);
    formData.append("user_id", String(resolvedUserId));
    formData.append("sample_rate", "16000");
    formData.append("frame_ms", String(config.frameMs));
    formData.append("hop_ms", String(config.hopMs));
    formData.append("algorithm", config.algorithm);
    formData.append("title", (els.projectTitleInput.value || "").trim() || defaultTitle);
    formData.append("tempo", String(parsePositiveInteger(String(state.preferredTempo), "速度")));
    formData.append("time_signature", normalizeTimeSignature(state.preferredTimeSignature));
    if (els.beatBpmHintInput.value) {
        formData.append("bpm_hint", els.beatBpmHintInput.value);
    }
    formData.append("beat_sensitivity", els.beatSensitivityInput.value || "0.5");
    formData.append("separation_model", (els.separationModelInput.value || "").trim() || "demucs");
    formData.append("separation_stems", els.separationStemsInput.value || "2");
    formData.append("arrangement_mode", arrangementMode);

    const result = await requestJson("/score/from-audio", {
        method: "POST",
        body: formData,
    });
    state.beatDetectResult = result.beat_result
        ? { ...result.beat_result, analysis_id: result.analysis_id, audio_log: result.audio_log }
        : null;
    state.separateTracksResult = result.separation || null;
    state.chordGenerationResult = result.piano_arrangement || null;
    setLatestPitchSequence(result.pitch_sequence || []);
    els.analysisIdInput.value = result.analysis_id || "";
    setLocalStorageSafely(STORAGE_KEYS.analysisId, els.analysisIdInput.value, { silent: true });
    applyDetectedTempo(result.tempo_detection?.resolved_tempo || result.tempo);
    applyDetectedKeySignature(result.detected_key_signature || result.key_signature);
    state.exportList = [];
    state.selectedExportRecordId = null;
    state.selectedExportDetail = null;
    applyScoreResult(result);
    await loadAudioLogs();
    queueExportRefresh();
    return result;
}

async function requestGuzhengScore({ pitchSequence = null, analysisId = null, scoreId = null } = {}) {
    const base = resolveCustomLeadSheetBase(scoreId);
    const payload = {
        title: base.title,
        key: base.key,
        tempo: base.tempo,
        time_signature: base.timeSignature,
        style: "traditional",
    };
    if (scoreId) {
        payload.score_id = scoreId;
    } else if (Array.isArray(pitchSequence) && pitchSequence.length) {
        payload.pitch_sequence = pitchSequence;
    } else if (analysisId) {
        payload.analysis_id = analysisId;
    } else {
        const parsedSequence = parsePitchSequenceOrEmpty();
        if (parsedSequence.length) {
            payload.pitch_sequence = parsedSequence;
        }
    }

    const result = await requestJson("/generation/guzheng-score", {
        method: "POST",
        body: payload,
    });
    state.guzhengResult = result;
    setTraditionalEngravedPreview("guzheng", null);
    applyDetectedKeySignature(result.key);
    await requestTraditionalEngravedPreview("guzheng", { force: true, silent: true });
    return result;
}

function buildTraditionalExportPayload(instrumentType, format) {
    const source = resolveCustomLeadSheetSource();
    const base = resolveCustomLeadSheetBase(source.scoreId);
    const payload = {
        title: base.title,
        key: base.key,
        tempo: base.tempo,
        time_signature: base.timeSignature,
        style: "traditional",
        format,
        layout_mode: resolveJianpuLayoutMode(state.jianpuLayoutMode),
        annotation_layer: resolveJianpuAnnotationLayer(state.jianpuAnnotationLayer),
    };
    if (source.scoreId) {
        payload.score_id = source.scoreId;
    } else if (Array.isArray(source.pitchSequence) && source.pitchSequence.length) {
        payload.pitch_sequence = source.pitchSequence;
    } else if (source.analysisId) {
        payload.analysis_id = source.analysisId;
    } else {
        throw new Error("当前没有可导出的旋律来源，请先生成或保留当前识谱结果。");
    }
    if (instrumentType === "dizi") {
        payload.flute_type = resolveDiziFluteType(state.diziFluteType || els.diziFluteTypeInput?.value || "G");
    }
    return payload;
}

async function requestTraditionalExport(instrumentType, format) {
    const normalizedInstrument = instrumentType === "dizi" ? "dizi" : "guzheng";
    const busyKey = `traditional-export-${normalizedInstrument}`;
    if (isBusy(busyKey)) {
        return null;
    }
    setBusy(busyKey, true);
    renderAll();
    try {
        const payload = buildTraditionalExportPayload(normalizedInstrument, format);
        const endpoint = normalizedInstrument === "guzheng"
            ? "/generation/guzheng-score/export"
            : "/generation/dizi-score/export";
        const result = await requestJson(endpoint, {
            method: "POST",
            body: payload,
        });
        triggerFileDownload(buildServerUrl(result.download_url || ""), result.file_name || "");
        const targetName = normalizedInstrument === "guzheng" ? "古筝" : "笛子";
        const formatLabel = format === "jianpu"
            ? "jianpu-ly 源"
            : format === "ly"
                ? "LilyPond 源"
                : format === "svg"
                    ? "SVG 页面"
                    : "PDF";
        setAppStatus(`${targetName}${formatLabel}已导出：${result.file_name}`);
        return result;
    } catch (error) {
        setAppStatus(`导出失败：${error.message}`, true);
        return null;
    } finally {
        setBusy(busyKey, false);
        renderAll();
    }
}

async function requestTraditionalEngravedPreview(instrumentType, { force = false, silent = false } = {}) {
    const normalizedInstrument = instrumentType === "dizi" ? "dizi" : "guzheng";
    const result = resolveTraditionalResult(normalizedInstrument);
    if (!result) {
        setTraditionalEngravedPreview(normalizedInstrument, null);
        return null;
    }

    const signature = buildTraditionalPreviewSignature(normalizedInstrument, result);
    const existing = resolveTraditionalEngravedPreview(normalizedInstrument);
    if (!force && existing?.signature === signature && Array.isArray(existing.preview_pages) && existing.preview_pages.length) {
        return existing;
    }

    const busyKey = `traditional-render-${normalizedInstrument}`;
    if (isBusy(busyKey)) {
        return existing;
    }

    setTraditionalEngravedPreview(normalizedInstrument, {
        signature,
        preview_pages: [],
        layout_mode: resolveJianpuLayoutMode(state.jianpuLayoutMode),
        annotation_layer: resolveJianpuAnnotationLayer(state.jianpuAnnotationLayer),
        error: "",
    });
    setBusy(busyKey, true);
    renderAll();
    try {
        const payload = buildTraditionalExportPayload(normalizedInstrument, "svg");
        const endpoint = normalizedInstrument === "guzheng"
            ? "/generation/guzheng-score/export"
            : "/generation/dizi-score/export";
        const preview = await requestJson(endpoint, {
            method: "POST",
            body: payload,
        });
        const nextPreview = {
            ...preview,
            signature,
            render_engine: "lilypond",
        };
        setTraditionalEngravedPreview(normalizedInstrument, nextPreview);
        if (!silent) {
            const label = normalizedInstrument === "guzheng" ? "古筝" : "笛子";
            setAppStatus(`${label}简谱已切换到 jianpu-ly / LilyPond 统一排版预览。`);
        }
        return nextPreview;
    } catch (error) {
        setTraditionalEngravedPreview(normalizedInstrument, {
            signature,
            preview_pages: [],
            layout_mode: resolveJianpuLayoutMode(state.jianpuLayoutMode),
            annotation_layer: resolveJianpuAnnotationLayer(state.jianpuAnnotationLayer),
            error: error.message,
        });
        if (!silent) {
            setAppStatus(`统一排版预览生成失败：${error.message}`, true);
        }
        return null;
    } finally {
        setBusy(busyKey, false);
        renderAll();
    }
}

function buildGuitarExportPayload(format) {
    const source = resolveCustomLeadSheetSource();
    const base = resolveCustomLeadSheetBase(source.scoreId);
    const payload = {
        title: base.title,
        key: base.key,
        tempo: base.tempo,
        time_signature: base.timeSignature,
        style: (els.chordStyleInput.value || "").trim() || "pop",
        format,
        layout_mode: resolveGuitarViewMode(state.guitarViewMode),
    };
    if (source.scoreId) {
        payload.score_id = source.scoreId;
    } else if (Array.isArray(source.pitchSequence) && source.pitchSequence.length) {
        payload.pitch_sequence = source.pitchSequence;
    } else if (source.analysisId) {
        payload.analysis_id = source.analysisId;
    } else {
        throw new Error("当前没有可导出的吉他弹唱谱来源，请先生成或保留当前识谱结果。");
    }
    return payload;
}

async function requestGuitarLeadSheetExport(format) {
    const busyKey = `guitar-export-${format}`;
    if (isBusy(busyKey)) {
        return null;
    }
    setBusy(busyKey, true);
    renderAll();
    try {
        const payload = buildGuitarExportPayload(format);
        const result = await requestJson("/generation/guitar-lead-sheet/export", {
            method: "POST",
            body: payload,
        });
        triggerFileDownload(buildServerUrl(result.download_url || ""), result.file_name || "");
        setAppStatus(`吉他弹唱谱 PDF 已导出：${result.file_name}`);
        return result;
    } catch (error) {
        setAppStatus(`吉他弹唱谱导出失败：${error.message}`, true);
        return null;
    } finally {
        setBusy(busyKey, false);
        renderAll();
    }
}

async function requestDiziScore({ pitchSequence = null, analysisId = null, scoreId = null } = {}) {
    const base = resolveCustomLeadSheetBase(scoreId);
    const payload = {
        title: base.title,
        key: base.key,
        tempo: base.tempo,
        time_signature: base.timeSignature,
        style: "traditional",
        flute_type: resolveDiziFluteType(state.diziFluteType || els.diziFluteTypeInput?.value || "G"),
    };
    if (scoreId) {
        payload.score_id = scoreId;
    } else if (Array.isArray(pitchSequence) && pitchSequence.length) {
        payload.pitch_sequence = pitchSequence;
    } else if (analysisId) {
        payload.analysis_id = analysisId;
    } else {
        const parsedSequence = parsePitchSequenceOrEmpty();
        if (parsedSequence.length) {
            payload.pitch_sequence = parsedSequence;
        }
    }

    const result = await requestJson("/generation/dizi-score", {
        method: "POST",
        body: payload,
    });
    state.diziResult = result;
    setTraditionalEngravedPreview("dizi", null);
    setDiziFluteType(result.flute_type || payload.flute_type, { persist: true, announce: false });
    applyDetectedKeySignature(result.key);
    await requestTraditionalEngravedPreview("dizi", { force: true, silent: true });
    return result;
}

async function requestGuitarLeadSheet({ pitchSequence = null, analysisId = null, scoreId = null } = {}) {
    const base = resolveCustomLeadSheetBase(scoreId);
    const payload = {
        title: base.title,
        key: base.key,
        tempo: base.tempo,
        time_signature: base.timeSignature,
        style: (els.chordStyleInput.value || "").trim() || "pop",
    };
    if (scoreId) {
        payload.score_id = scoreId;
    } else if (Array.isArray(pitchSequence) && pitchSequence.length) {
        payload.pitch_sequence = pitchSequence;
    } else if (analysisId) {
        payload.analysis_id = analysisId;
    } else {
        const parsedSequence = parsePitchSequenceOrEmpty();
        if (parsedSequence.length) {
            payload.pitch_sequence = parsedSequence;
        }
    }

    const result = await requestJson("/generation/guitar-lead-sheet", {
        method: "POST",
        body: payload,
    });
    state.guitarLeadSheetResult = result;
    state.chordGenerationResult = result;
    applyDetectedKeySignature(result.key);
    renderAll();
    return result;
}

async function requestGuzhengScoreFromAudio(file) {
    const config = getPitchDetectConfig();
    const base = resolveCustomLeadSheetBase(null);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("sample_rate", "16000");
    formData.append("frame_ms", String(config.frameMs));
    formData.append("hop_ms", String(config.hopMs));
    formData.append("algorithm", config.algorithm);
    formData.append("title", base.title || "Untitled Guzheng Chart");
    formData.append("key", base.key || "");
    formData.append("tempo", String(base.tempo));
    formData.append("time_signature", base.timeSignature);
    formData.append("style", "traditional");
    if (els.beatBpmHintInput.value) {
        formData.append("bpm_hint", els.beatBpmHintInput.value);
    }
    formData.append("beat_sensitivity", els.beatSensitivityInput.value || "0.5");
    formData.append("separation_model", (els.separationModelInput.value || "").trim() || "demucs");
    formData.append("separation_stems", els.separationStemsInput.value || "2");

    const result = await requestJson("/generation/guzheng-score-from-audio", {
        method: "POST",
        body: formData,
    });
    state.guzhengResult = result;
    setTraditionalEngravedPreview("guzheng", null);
    state.beatDetectResult = result.beat_result
        ? { ...result.beat_result, analysis_id: result.analysis_id, audio_log: result.audio_log }
        : null;
    state.separateTracksResult = result.separation || null;
    setLatestPitchSequence(result.pitch_sequence || []);
    els.analysisIdInput.value = result.analysis_id || "";
    setLocalStorageSafely(STORAGE_KEYS.analysisId, els.analysisIdInput.value, { silent: true });
    applyDetectedTempo(result.tempo_detection?.resolved_tempo || result.tempo);
    applyDetectedKeySignature(result.key || result.detected_key_signature);
    await requestTraditionalEngravedPreview("guzheng", { force: true, silent: true });
    return result;
}

async function requestDiziScoreFromAudio(file) {
    const config = getPitchDetectConfig();
    const fluteType = resolveDiziFluteType(state.diziFluteType || els.diziFluteTypeInput?.value || "G");
    const base = resolveCustomLeadSheetBase(null);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("sample_rate", "16000");
    formData.append("frame_ms", String(config.frameMs));
    formData.append("hop_ms", String(config.hopMs));
    formData.append("algorithm", config.algorithm);
    formData.append("title", base.title || "Untitled Dizi Chart");
    formData.append("key", base.key || "");
    formData.append("tempo", String(base.tempo));
    formData.append("time_signature", base.timeSignature);
    formData.append("style", "traditional");
    formData.append("flute_type", fluteType);
    if (els.beatBpmHintInput.value) {
        formData.append("bpm_hint", els.beatBpmHintInput.value);
    }
    formData.append("beat_sensitivity", els.beatSensitivityInput.value || "0.5");
    formData.append("separation_model", (els.separationModelInput.value || "").trim() || "demucs");
    formData.append("separation_stems", els.separationStemsInput.value || "2");

    const result = await requestJson("/generation/dizi-score-from-audio", {
        method: "POST",
        body: formData,
    });
    state.diziResult = result;
    setTraditionalEngravedPreview("dizi", null);
    state.beatDetectResult = result.beat_result
        ? { ...result.beat_result, analysis_id: result.analysis_id, audio_log: result.audio_log }
        : null;
    state.separateTracksResult = result.separation || null;
    setLatestPitchSequence(result.pitch_sequence || []);
    els.analysisIdInput.value = result.analysis_id || "";
    setLocalStorageSafely(STORAGE_KEYS.analysisId, els.analysisIdInput.value, { silent: true });
    setDiziFluteType(result.flute_type || fluteType, { persist: true, announce: false });
    applyDetectedTempo(result.tempo_detection?.resolved_tempo || result.tempo);
    applyDetectedKeySignature(result.key || result.detected_key_signature);
    await requestTraditionalEngravedPreview("dizi", { force: true, silent: true });
    return result;
}

async function requestGuitarLeadSheetFromAudio(file) {
    const config = getPitchDetectConfig();
    const base = resolveCustomLeadSheetBase(null);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("sample_rate", "16000");
    formData.append("frame_ms", String(config.frameMs));
    formData.append("hop_ms", String(config.hopMs));
    formData.append("algorithm", config.algorithm);
    formData.append("title", base.title || "Untitled Guitar Lead Sheet");
    formData.append("key", base.key || "");
    formData.append("tempo", String(base.tempo));
    formData.append("time_signature", base.timeSignature);
    formData.append("style", (els.chordStyleInput.value || "").trim() || "pop");
    formData.append("separation_model", "demucs");
    formData.append("separation_stems", "2");

    const result = await requestJson("/generation/guitar-lead-sheet-from-audio", {
        method: "POST",
        body: formData,
    });
    state.guitarLeadSheetResult = result;
    state.chordGenerationResult = result;
    state.separateTracksResult = result.separation || null;
    setLatestPitchSequence(result.pitch_sequence || []);
    els.analysisIdInput.value = result.analysis_id || "";
    setLocalStorageSafely(STORAGE_KEYS.analysisId, els.analysisIdInput.value, { silent: true });
    applyDetectedKeySignature(result.detected_key_signature || result.key);
    renderAll();
    return result;
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
        setLatestPitchSequence(sequence);
        els.analysisIdInput.value = result.analysis_id || "";
        setLocalStorageSafely(STORAGE_KEYS.analysisId, els.analysisIdInput.value, { silent: true });
        const detectedKeySignature = applyDetectedKeySignature(result.detected_key_signature);
        const msg = detectedKeySignature
            ? `音高识别完成：识别到 ${sequence.length} 个音高点，建议调号 ${detectedKeySignature}`
            : `音高识别完成：识别到 ${sequence.length} 个音高点`;
        setPitchDetectStatus(msg);
        setAppStatus(
            detectedKeySignature
                ? `音高识别已完成，系统建议调号 ${detectedKeySignature}，可以继续生成${activeResultLabel()}。`
                : `音高识别已完成，可以继续生成${activeResultLabel()}。`
        );
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
        if (isGuitarMode()) {
            setPitchDetectStatus("正在分离人声并提取主旋律，随后生成吉他弹唱谱…");
            setAppStatus("吉他模式已启用人声优先识别，正在生成弹唱谱。");
            let generatedLeadSheet;
            try {
                generatedLeadSheet = await requestGuitarLeadSheetFromAudio(file);
            } catch (error) {
                setPitchDetectStatus(`吉他弹唱谱生成失败：${error.message}`, true);
                setAppStatus("吉他弹唱谱生成未完成，请查看识别区域提示。", true);
                return;
            }
            const melodyTrackName = generatedLeadSheet.melody_track?.name || "mix";
            const warnings = Array.isArray(generatedLeadSheet.warnings) && generatedLeadSheet.warnings.length
                ? `，附带 ${generatedLeadSheet.warnings.length} 条提示`
                : "";
            setPitchDetectStatus(
                `吉他弹唱谱生成完成：已优先使用 ${melodyTrackName} 轨识别旋律，生成 ${generatedLeadSheet.measures?.length || 0} 小节${warnings}。`
            );
            setAppStatus(`吉他弹唱谱已生成，当前调号 ${generatedLeadSheet.key || "--"}，旋律来源 ${melodyTrackName}。`);
            return;
        }
        if (isGuzhengMode()) {
            setPitchDetectStatus("正在分离主旋律、检测节拍速度，并生成古筝谱…");
            setAppStatus("古筝模式会先分离主旋律，再做定速、定调与简谱/弦位映射。");
            let generatedScore;
            try {
                generatedScore = await requestGuzhengScoreFromAudio(file);
            } catch (error) {
                setPitchDetectStatus(`古筝谱生成失败：${error.message}`, true);
                setAppStatus("古筝智能识谱未完成，请查看识别区域提示。", true);
                return;
            }
            const melodyTrackName = localizeTrackName(generatedScore.melody_track?.name || "mix");
            const tempoSummary = generatedScore.tempo_detection?.used_detected_tempo
                ? `${generatedScore.tempo || "--"} BPM`
                : `${generatedScore.tempo || "--"} BPM（测速回退）`;
            const pressCandidates = generatedScore.pentatonic_summary?.press_note_candidates || 0;
            setPitchDetectStatus(
                `古筝谱生成完成：旋律来源 ${melodyTrackName}，调号 ${generatedScore.key || "--"}，速度 ${tempoSummary}，共 ${generatedScore.measures?.length || 0} 小节，按音候选 ${pressCandidates} 个。`
            );
            setAppStatus(`古筝谱已生成，当前调号 ${generatedScore.key || "--"}，旋律来源 ${melodyTrackName}，速度 ${tempoSummary}。`);
            return;
        }
        if (isDiziMode()) {
            setPitchDetectStatus("正在分离主旋律、检测节拍速度，并生成笛子谱…");
            setAppStatus("笛子模式会先分离主旋律，再做定速、定调、筒音映射与指法生成。");
            let generatedScore;
            try {
                generatedScore = await requestDiziScoreFromAudio(file);
            } catch (error) {
                setPitchDetectStatus(`笛子谱生成失败：${error.message}`, true);
                setAppStatus("笛子智能识谱未完成，请查看识别区域提示。", true);
                return;
            }
            const melodyTrackName = localizeTrackName(generatedScore.melody_track?.name || "mix");
            const tempoSummary = generatedScore.tempo_detection?.used_detected_tempo
                ? `${generatedScore.tempo || "--"} BPM`
                : `${generatedScore.tempo || "--"} BPM（测速回退）`;
            const halfHoleCandidates = generatedScore.playability_summary?.half_hole_candidates || 0;
            const specialCandidates = generatedScore.playability_summary?.special_fingering_candidates || 0;
            setPitchDetectStatus(
                `笛子谱生成完成：旋律来源 ${melodyTrackName}，笛型 ${generatedScore.flute_type || "--"} 调，调号 ${generatedScore.key || "--"}，速度 ${tempoSummary}，半孔 ${halfHoleCandidates} 个，特殊指法 ${specialCandidates} 个。`
            );
            setAppStatus(
                `笛子谱已生成，当前笛型 ${generatedScore.flute_type || "--"} 调，旋律来源 ${melodyTrackName}，速度 ${tempoSummary}。`
            );
            return;
        }
        setPitchDetectStatus("正在分离主旋律、检测节拍速度，并生成双手钢琴谱…");
        setAppStatus("钢琴模式会先分离主旋律，再做定速、定调、和弦分析与双手编配。");
        let created;
        try {
            created = await requestPianoScoreFromAudio(file);
        } catch (error) {
            setPitchDetectStatus(`双手钢琴谱生成失败：${error.message}`, true);
            setAppStatus("钢琴智能识谱未完成，请查看识别区域提示。", true);
            return;
        }
        const melodyTrackName = localizeTrackName(created.melody_track?.name || "mix");
        const usedDetectedTempo = created.tempo_detection?.used_detected_tempo;
        const tempoSummary = usedDetectedTempo
            ? `${created.tempo || "--"} BPM`
            : `${created.tempo || "--"} BPM（测速回退）`;
        if (!created.piano_arrangement) {
            setPitchDetectStatus("钢琴谱生成完成，但未返回双手编配结果。", true);
            setAppStatus("当前结果缺少左手编配，请重新生成或检查后端处理链路。", true);
            return;
        }
        const chordCount = Array.isArray(created.piano_arrangement?.chords) ? created.piano_arrangement.chords.length : 0;
        const msg = `双手钢琴谱生成完成：旋律来源 ${melodyTrackName}，调号 ${created.key_signature || "--"}，速度 ${tempoSummary}，和弦 ${chordCount} 组，乐谱 ${created.score_id} 已生成`;
        setPitchDetectStatus(msg);
        setAppStatus(`双手钢琴谱已完成，已生成带左手伴奏的钢琴谱，旋律来源 ${melodyTrackName}，速度 ${tempoSummary}。`);
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
        if (isGuzhengMode()) {
            const source = resolveCustomLeadSheetSource();
            const generatedScore = await requestGuzhengScore({
                scoreId: source.scoreId,
                pitchSequence: source.pitchSequence,
                analysisId: source.analysisId,
            });
            setAppStatus(`古筝谱已生成，共 ${generatedScore.measures?.length || 0} 小节。`);
            return;
        }
        if (isDiziMode()) {
            const source = resolveCustomLeadSheetSource();
            const generatedScore = await requestDiziScore({
                scoreId: source.scoreId,
                pitchSequence: source.pitchSequence,
                analysisId: source.analysisId,
            });
            setAppStatus(
                `笛子谱已生成，共 ${generatedScore.measures?.length || 0} 小节，当前笛型 ${generatedScore.flute_type || "--"} 调。`
            );
            return;
        }
        if (isGuitarMode()) {
            const source = resolveCustomLeadSheetSource();
            const generatedLeadSheet = await requestGuitarLeadSheet({
                scoreId: source.scoreId,
                pitchSequence: source.pitchSequence,
                analysisId: source.analysisId,
            });
            setAppStatus(`吉他弹唱谱已生成，共 ${generatedLeadSheet.measures?.length || 0} 小节。`);
            return;
        }
        const payload = {
            user_id: await ensureScoreOwnerUserId(),
            title: (els.projectTitleInput.value || "").trim() || null,
            analysis_id: (els.analysisIdInput.value || "").trim() || null,
            tempo: parsePositiveInteger(String(state.preferredTempo), "速度"),
            time_signature: normalizeTimeSignature(state.preferredTimeSignature),
            key_signature: normalizeKeySignature(state.preferredKeySignature),
            auto_detect_key: false,
            arrangement_mode: resolvePianoArrangementModeValue(),
            pitch_sequence: parsePitchSequence(),
        };
        const created = await requestJson("/score/from-pitch-sequence", { method: "POST", body: payload });
        state.exportList = [];
        state.selectedExportRecordId = null;
        state.selectedExportDetail = null;
        applyScoreResult(created);
        setAppStatus(`${created.piano_arrangement ? "双手钢琴谱" : "钢琴谱"}已生成并关联：${created.score_id}`);
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
        const result = await requestBeatDetect(file, { syncAnalysisId: true, refreshAudioLogs: true });
        const detectedTempo = resolveReliableBeatTempo(result);
        if (detectedTempo) {
            applyDetectedTempo(detectedTempo);
            setAppStatus(`节拍检测完成，已自动回填速度 ${detectedTempo} BPM。`);
            return;
        }
        setAppStatus("节拍检测完成，但当前结果置信度不足，未自动覆盖速度。");
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
        setLocalStorageSafely(STORAGE_KEYS.analysisId, els.analysisIdInput.value, { silent: true });
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
        if (isGuitarMode()) {
            const source = resolveCustomLeadSheetSource();
            const result = await requestGuitarLeadSheet({
                scoreId: source.scoreId,
                analysisId: source.analysisId,
                pitchSequence: source.pitchSequence,
            });
            state.chordGenerationResult = result;
            renderAll();
            setAppStatus(`吉他弹唱谱刷新完成，共返回 ${result.chords?.length || 0} 个和弦。`);
            return;
        }
        if (isGuzhengMode()) {
            const source = resolveCustomLeadSheetSource();
            const result = await requestGuzhengScore({
                scoreId: source.scoreId,
                analysisId: source.analysisId,
                pitchSequence: source.pitchSequence,
            });
            renderAll();
            setAppStatus(`古筝谱刷新完成，共 ${result.measures?.length || 0} 小节。`);
            return;
        }
        if (isDiziMode()) {
            const source = resolveCustomLeadSheetSource();
            const result = await requestDiziScore({
                scoreId: source.scoreId,
                analysisId: source.analysisId,
                pitchSequence: source.pitchSequence,
            });
            renderAll();
            setAppStatus(
                `笛子谱刷新完成，共 ${result.measures?.length || 0} 小节，当前笛型 ${result.flute_type || "--"} 调。`
            );
            return;
        }
        if (state.currentScore?.piano_arrangement && isPianoArrangementMode()) {
            state.chordGenerationResult = state.currentScore.piano_arrangement;
            renderAll();
            setAppStatus("已展示当前双手钢琴谱的和弦、分手规则和左手织体。");
            return;
        }
        const key = (state.currentScore?.key_signature || normalizeKeySignature(state.preferredKeySignature)).trim() || "C";
        const tempo = parsePositiveInteger(String(state.currentScore?.tempo || state.preferredTempo), "速度");
        const timeSignature = (state.currentScore?.time_signature || normalizeTimeSignature(state.preferredTimeSignature)).trim() || "4/4";
        const style = (els.chordStyleInput.value || "").trim() || "pop";
        const melody = buildMelodyFromScore();
        const result = await requestJson("/generation/chords", {
            method: "POST",
            body: { key, tempo, time_signature: timeSignature, style, melody },
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

async function handleExportScorePdf() {
    if (!state.currentScore?.score_id || isBusy("piano-export-pdf")) {
        if (!state.currentScore?.score_id) {
            setAppStatus("请先生成或载入一份钢琴乐谱。", true);
        }
        return;
    }
    setBusy("piano-export-pdf", true);
    renderAll();
    try {
        const created = await requestJson(`/scores/${state.currentScore.score_id}/export`, {
            method: "POST",
            body: {
                format: "pdf",
                page_size: "A4",
                with_annotations: true,
            },
        });
        state.selectedExportRecordId = created.export_record_id || state.selectedExportRecordId;
        state.selectedExportDetail = created;
        queueExportRefresh(created.export_record_id || null);
        triggerFileDownload(buildServerUrl(created.download_api_url || created.download_url || ""), created.file_name || "");
        setAppStatus(`钢琴乐谱 PDF 已导出：${created.file_name}`);
    } catch (error) {
        setAppStatus(`钢琴乐谱导出失败：${error.message}`, true);
    } finally {
        setBusy("piano-export-pdf", false);
        renderAll();
    }
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
    if (score) {
        setPianoResultMode(resolvePianoResultModeFromScore(score), { persist: true, announce: false });
    }
    if (isPianoMode()) {
        state.chordGenerationResult = score?.piano_arrangement || null;
    }
    state.selectedScoreId = score?.score_id || "";
    state.selectedNotationElementId = null;
    localStorage.setItem(STORAGE_KEYS.scoreId, state.selectedScoreId);

    state.preferredTempo = parseStoredTempo(score.tempo || state.preferredTempo);
    state.preferredTimeSignature = normalizeTimeSignature(score.time_signature || state.preferredTimeSignature);
    state.preferredKeySignature = normalizeKeySignature(score.key_signature || state.preferredKeySignature);
    localStorage.setItem(STORAGE_KEYS.tempo, String(state.preferredTempo));
    localStorage.setItem(STORAGE_KEYS.timeSignature, state.preferredTimeSignature);
    localStorage.setItem(STORAGE_KEYS.keySignature, state.preferredKeySignature);
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

function renderInstrumentToggleButtons() {
    const currentType = resolveInstrumentType(state.instrumentType);
    els.instrumentToggleButtons.forEach((button) => {
        const isActive = button.dataset.instrumentType === currentType;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-selected", isActive ? "true" : "false");
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
        button.tabIndex = isActive ? 0 : -1;
    });
}

function renderPianoResultModeButtons() {
    const currentMode = resolvePianoResultMode(state.pianoResultMode);
    els.pianoResultModeButtons.forEach((button) => {
        const isActive = button.dataset.pianoResultMode === currentMode;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-selected", isActive ? "true" : "false");
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
        button.tabIndex = isActive ? 0 : -1;
    });
}

function renderInstrumentMode() {
    const guitarMode = isGuitarMode();
    const guzhengMode = isGuzhengMode();
    const diziMode = isDiziMode();
    const pianoMode = isPianoMode();
    const customMode = isCustomLeadSheetMode();
    renderInstrumentToggleButtons();
    renderPianoResultModeButtons();
    els.pianoResultSwitch.hidden = !pianoMode;
    els.pianoResultSwitch.style.display = pianoMode ? "" : "none";
    els.pianoResultSwitch.setAttribute("aria-hidden", pianoMode ? "false" : "true");
    if (els.diziFluteTypeField) {
        els.diziFluteTypeField.hidden = !diziMode;
    }
    els.linkageLabel.textContent = guitarMode
        ? "当前弹唱谱"
        : guzhengMode
            ? "当前古筝谱"
            : diziMode
                ? "当前笛子谱"
                : "当前双手钢琴谱";
    els.previewPanelTitle.textContent = guitarMode
        ? "吉他弹唱谱预览"
        : guzhengMode
            ? "古筝谱预览"
            : diziMode
                ? "笛子谱预览"
                : "双手钢琴谱预览";
    els.previewPanelCopy.textContent = guitarMode
        ? "当前页面只展示吉他弹唱谱结果。主视图会优先呈现 lead sheet 正文，和弦图与识谱过程会下沉到辅助区和调试面板。"
        : guzhengMode
            ? "当前页面只展示古筝智能识谱结果。主视图会统一走简谱正文页，弦位和技法改为可切换标注层，技术过程默认折叠。"
            : diziMode
                ? "当前页面只展示笛子智能识谱结果。主视图会统一走简谱正文页，笛型、孔位和技法通过共享标注层呈现，技术过程默认折叠。"
                : "当前页面固定展示带左手伴奏的双手钢琴谱，并同步展示和弦时间轴、左手织体与双手分配。";
    els.analysisPanelTitle.textContent = guitarMode
        ? "吉他识谱调试面板"
        : guzhengMode
            ? "古筝识谱调试面板"
            : diziMode
                ? "笛子识谱调试面板"
                : "双手钢琴谱分析";
    els.analysisPanelCopy.textContent = guitarMode
        ? "上传样例音频并执行吉他识谱后，这里会展示折叠后的识谱过程摘要；展开后可查看分离轨、定调结果、和弦来源和流程提示。"
        : guzhengMode
            ? "上传样例音频并执行古筝识谱后，这里会先显示折叠后的流程摘要；展开后可查看分离轨、定调结果、五声音阶统计与技法候选。"
            : diziMode
                ? "上传样例音频并执行笛子识谱后，这里会先显示折叠后的流程摘要；展开后可查看分离轨、定调结果、可吹性统计与指法候选。"
                : "双手钢琴模式下会展示节拍、分轨、和弦时间轴、左手织体和双手分配规则。";
    els.pitchDetectAndScoreBtn.textContent = guitarMode
        ? "识别并生成吉他弹唱谱"
        : guzhengMode
            ? "识别并生成古筝谱"
            : diziMode
                ? "识别并生成笛子谱"
                : "识别并生成双手钢琴谱";
    els.createScoreBtn.textContent = guitarMode
        ? "生成吉他弹唱谱"
        : guzhengMode
            ? "生成古筝谱"
            : diziMode
                ? "生成笛子谱"
                : "生成双手钢琴谱";
    els.generateChordsBtn.textContent = guitarMode
        ? "生成吉他弹唱谱"
        : guzhengMode
            ? "刷新古筝谱"
            : diziMode
                ? "刷新笛子谱"
                : "查看编配和弦";
    els.exportScorePdfBtn.hidden = customMode;
    els.openScoreViewerBtn.hidden = customMode;
    els.scoreSummaryPanel.hidden = customMode;
    els.scoreEditorGrid.hidden = customMode;
    els.exportWorkbenchPanel.hidden = customMode;
}

function renderAll() {
    renderBackendState();
    renderInstrumentMode();
    renderScoreSummary();
    renderGuzhengScorePanel();
    renderDiziScorePanel();
    renderGuitarLeadSheetPanel();
    renderAnalysisOutputs();
    renderExportList();
    renderAudioLogs();
    renderExportDetail();
    renderControlState();
    if (isPianoMode()) {
        scheduleNotationRender();
    } else {
        hidePianoPreviewSurfaces();
    }
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
    if (!isPianoMode()) {
        return;
    }
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
    if (!isPianoMode()) {
        hidePianoPreviewSurfaces();
        return;
    }
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

function localizeStrummingDifficulty(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "easy") return "简单";
    if (normalized === "medium") return "中等";
    if (normalized === "hard") return "进阶";
    return value || "--";
}

function strummingPatternToArrows(pattern) {
    return String(pattern || "--")
        .replace(/D/g, "↓")
        .replace(/U/g, "↑")
        .replace(/-/g, "·");
}

function resolveStrummingDisplayPattern(pattern) {
    if (!pattern) {
        return "--";
    }
    if (pattern.display_pattern) {
        return String(pattern.display_pattern);
    }
    if (pattern.pattern) {
        return strummingPatternToArrows(pattern.pattern);
    }
    return "--";
}

function renderStrummingStrokeGrid(pattern) {
    const strokeGrid = Array.isArray(pattern?.stroke_grid) ? pattern.stroke_grid : [];
    if (!strokeGrid.length) {
        return '<div class="analysis-note">当前还没有节拍口令可视化。</div>';
    }
    return `
        <div class="guitar-count-grid">
            ${strokeGrid.map((item) => `
                <div class="guitar-count-slot ${item.accent ? "accent" : ""}">
                    <span class="guitar-count-label">${escapeHtmlText(item.count || "--")}</span>
                    <strong class="guitar-count-stroke ${item.stroke ? "" : "empty"}">${escapeHtmlText(item.display_stroke || "·")}</strong>
                </div>
            `).join("")}
        </div>
    `;
}

function renderStrummingSectionCards(sectionPatterns) {
    const patterns = Array.isArray(sectionPatterns) ? sectionPatterns : [];
    if (!patterns.length) {
        return '<div class="analysis-note">当前还没有可展示的分段扫弦建议。</div>';
    }
    return `
        <div class="guitar-strumming-section-grid">
            ${patterns.map((item) => `
                <article class="guitar-strumming-section-card">
                    <div class="guitar-strumming-section-head">
                        <div>
                            <span class="guitar-section-kicker">${escapeHtmlText(item.section_title || item.section_role_label || "段落建议")}</span>
                            <strong class="guitar-section-range">第 ${escapeHtmlText(String(item.measure_start || "--"))}-${escapeHtmlText(String(item.measure_end || "--"))} 小节</strong>
                        </div>
                        <span class="guitar-section-meta">${escapeHtmlText(localizeStrummingDifficulty(item.difficulty || "--"))}</span>
                    </div>
                    <div class="guitar-strumming-section-pattern">${escapeHtmlText(resolveStrummingDisplayPattern(item))}</div>
                    <p class="guitar-strumming-section-copy">${escapeHtmlText(item.description || "按当前段落给出的推荐扫弦。")}</p>
                    <div class="guitar-strumming-section-foot">
                        <span class="guitar-meta-subtle">口令：${escapeHtmlText(item.counting || "--")}</span>
                        <span class="guitar-meta-subtle">${escapeHtmlText(item.practice_tip || "")}</span>
                    </div>
                </article>
            `).join("")}
        </div>
    `;
}

function localizeGuitarSectionRole(role) {
    const normalized = String(role || "").trim().toLowerCase();
    if (normalized === "chorus") return "副歌";
    if (normalized === "bridge") return "Bridge";
    if (normalized === "intro") return "前奏";
    if (normalized === "interlude") return "间奏";
    if (normalized === "outro") return "尾奏";
    return "主歌";
}

function localizeGuitarCadence(value) {
    if (value === "resolved") return "终止收束";
    if (value === "half") return "半终止";
    if (value === "applied") return "副属推进";
    return "开放进行";
}

function normalizeGuitarSectionRole(value, index = 0) {
    const raw = String(value || "").trim();
    const normalized = raw.toLowerCase();
    if (normalized.includes("chorus") || raw.includes("副歌")) return "chorus";
    if (normalized.includes("bridge") || raw.includes("bridge") || raw.includes("桥")) return "bridge";
    if (normalized.includes("intro") || raw.includes("前奏")) return "intro";
    if (normalized.includes("outro") || raw.includes("尾奏") || raw.includes("结尾")) return "outro";
    if (normalized.includes("interlude") || raw.includes("间奏")) return "interlude";
    if (normalized.includes("verse") || raw.includes("主歌")) return "verse";
    return index % 2 === 0 ? "verse" : "chorus";
}

function resolveGuitarMeasureWidthRem(measure) {
    const chordCount = Math.max(Array.isArray(measure?.chords) ? measure.chords.length : 0, 1);
    return Math.min(Math.max(8.5 + chordCount * 2.25, 9.5), 18);
}

function buildGuitarDisplayTokens(measures, lyricText) {
    const tokens = [];
    (Array.isArray(measures) ? measures : []).forEach((measure, measureIndex) => {
        tokens.push({ type: "bar", measureNo: Number(measure?.measure_no || measureIndex + 1) });
        const chords = Array.isArray(measure?.chords) ? measure.chords : [];
        if (!chords.length) {
            tokens.push({ type: "spacer", measureNo: Number(measure?.measure_no || measureIndex + 1), width: "measure" });
        } else {
            chords.forEach((chord, chordIndex) => {
                tokens.push({
                    type: "chord",
                    symbol: chord?.symbol || "--",
                    source: chord?.source || "diatonic",
                    measureNo: Number(chord?.measure_no || measure?.measure_no || measureIndex + 1),
                    beatInMeasure: Number(chord?.beat_in_measure || 1),
                });
                if (chordIndex < chords.length - 1) {
                    tokens.push({ type: "spacer", measureNo: Number(measure?.measure_no || measureIndex + 1), width: "beat" });
                }
            });
        }
        if (measureIndex === 0) {
            tokens.push({ type: "lyric", text: lyricText || "歌词待补", measureNo: Number(measure?.measure_no || 1) });
        }
    });
    return tokens;
}

function parseGuitarFingeringPattern(fingering) {
    const raw = String(fingering || "").trim();
    if (!/^[xX0-9]{6}$/.test(raw)) {
        return null;
    }
    return raw.split("").map((value) => (/[xX]/.test(value) ? "x" : Number(value)));
}

function renderGuitarChordDiagramGlyph(shape) {
    const fingering = String(shape?.fingering || "").trim();
    const parsed = parseGuitarFingeringPattern(fingering);
    if (!parsed) {
        return `
            <div class="guitar-diagram-fallback">
                <span class="guitar-diagram-fallback-label">按法</span>
                <strong class="guitar-diagram-fallback-value">${escapeHtmlText(fingering || shape?.display_name || "--")}</strong>
            </div>
        `;
    }

    const fretted = parsed.filter((value) => Number.isFinite(value) && value > 0);
    const startFret = fretted.length ? Math.min(...fretted) : 1;
    const displayStart = startFret > 1 ? startFret : 1;
    const headMarkers = parsed.map((value, index) => `
        <span class="guitar-diagram-head-marker" style="--string:${index + 1}">${value === "x" ? "×" : value === 0 ? "○" : ""}</span>
    `).join("");
    const stringLines = Array.from({ length: 6 }, (_, index) => `
        <span class="guitar-diagram-string-line" style="--string:${index + 1}"></span>
    `).join("");
    const fretLines = Array.from({ length: 5 }, (_, index) => `
        <span class="guitar-diagram-fret-line" style="--fret:${index + 1}"></span>
    `).join("");
    const dots = parsed.map((value, index) => {
        if (!Number.isFinite(value) || value <= 0) {
            return "";
        }
        const relativeFret = displayStart === 1 ? value : value - displayStart + 1;
        if (relativeFret < 1 || relativeFret > 5) {
            return "";
        }
        return `<span class="guitar-diagram-dot" style="--string:${index + 1}; --fret:${relativeFret}"></span>`;
    }).join("");
    return `
        <div class="guitar-diagram-glyph">
            <div class="guitar-diagram-head">${headMarkers}</div>
            <div class="guitar-diagram-board ${displayStart === 1 ? "open-position" : ""}">
                ${stringLines}
                ${fretLines}
                ${dots}
            </div>
            <div class="guitar-diagram-base">${displayStart > 1 ? `${escapeHtmlText(String(displayStart))}fr` : "Open"}</div>
        </div>
    `;
}

function findMatchingGuitarSectionPattern(sectionPatterns, section, sectionIndex) {
    const patterns = Array.isArray(sectionPatterns) ? sectionPatterns : [];
    if (!patterns.length) {
        return null;
    }
    const exact = patterns.find((pattern) => (
        Number(pattern?.measure_start || 0) === Number(section?.measure_start || 0)
        && Number(pattern?.measure_end || 0) === Number(section?.measure_end || 0)
    ));
    return exact || patterns[sectionIndex] || patterns[0] || null;
}

function buildGuitarSongSheetModel(result) {
    const measures = Array.isArray(result?.measures) ? result.measures : [];
    const chords = Array.isArray(result?.chords) ? result.chords : [];
    const sectionPatterns = Array.isArray(result?.strumming_pattern?.section_patterns) ? result.strumming_pattern.section_patterns : [];
    const fallbackLineMeasures = measures.length
        ? [{
            line_no: 1,
            line_label: "歌词行 1",
            measure_start: measures[0].measure_no || 1,
            measure_end: measures[measures.length - 1].measure_no || measures.length,
            measure_count: measures.length,
            cadence: measures.length ? "open" : "resolved",
            lyric_placeholder: "歌词待补",
            measures,
        }]
        : [];
    const fallbackSections = measures.length
        ? [{
            section_no: 1,
            section_label: "A",
            section_title: "主歌",
            measure_start: fallbackLineMeasures[0]?.measure_start || 1,
            measure_end: fallbackLineMeasures[0]?.measure_end || 1,
            measure_count: measures.length,
            cadence: fallbackLineMeasures[fallbackLineMeasures.length - 1]?.cadence || "open",
            lyric_lines: fallbackLineMeasures,
        }]
        : [];
    const sourceSections = Array.isArray(result?.display_sections) && result.display_sections.length
        ? result.display_sections
        : Array.isArray(result?.sections) && result.sections.length
            ? result.sections
            : fallbackSections;
    const roleCounts = new Map();
    const sections = sourceSections.map((section, sectionIndex) => {
        const sectionPattern = findMatchingGuitarSectionPattern(sectionPatterns, section, sectionIndex);
        const role = normalizeGuitarSectionRole(
            section?.section_role
                || sectionPattern?.section_role
                || sectionPattern?.section_title
                || section?.section_title
                || section?.section_label,
            sectionIndex,
        );
        const nextRoleCount = (roleCounts.get(role) || 0) + 1;
        roleCounts.set(role, nextRoleCount);
        const genericTitle = !section?.section_title || /^段落\s+[A-Z]/i.test(String(section.section_title));
        const title = sectionPattern?.section_title
            || (genericTitle ? `${localizeGuitarSectionRole(role)}${nextRoleCount > 1 ? ` ${nextRoleCount}` : ""}` : section.section_title)
            || `${localizeGuitarSectionRole(role)}${nextRoleCount > 1 ? ` ${nextRoleCount}` : ""}`;
        const sourceLines = Array.isArray(section?.lines) && section.lines.length
            ? section.lines
            : Array.isArray(section?.display_lines) && section.display_lines.length
                ? section.display_lines
                : Array.isArray(section?.lyric_lines) && section.lyric_lines.length
                    ? section.lyric_lines
                    : fallbackLineMeasures;
        const lines = sourceLines.map((line, lineIndex) => {
            const lineMeasures = Array.isArray(line?.measures) ? line.measures : [];
            const lyricText = String(line?.lyric || line?.lyric_text || line?.lyric_placeholder || "歌词待补").trim() || "歌词待补";
            const measureSegments = lineMeasures.map((measure, measureIndex) => ({
                measureNo: Number(measure?.measure_no || measureIndex + 1),
                widthRem: resolveGuitarMeasureWidthRem(measure),
                chords: Array.isArray(measure?.chords) ? measure.chords : [],
                lyricText: measureIndex === 0 ? lyricText : "",
                hasLyrics: Boolean(line?.lyric || line?.lyric_text),
            }));
            return {
                lineNo: Number(line?.line_no || lineIndex + 1),
                label: line?.line_label || `第 ${line?.measure_start || measureSegments[0]?.measureNo || 1}-${line?.measure_end || measureSegments[measureSegments.length - 1]?.measureNo || 1} 小节`,
                measureStart: Number(line?.measure_start || measureSegments[0]?.measureNo || 1),
                measureEnd: Number(line?.measure_end || measureSegments[measureSegments.length - 1]?.measureNo || 1),
                measureCount: Number(line?.measure_count || measureSegments.length || 0),
                cadence: line?.cadence || "open",
                lyricText,
                hasLyrics: Boolean(line?.lyric || line?.lyric_text),
                measureSegments,
                tokens: Array.isArray(line?.tokens) && line.tokens.length
                    ? line.tokens
                    : buildGuitarDisplayTokens(lineMeasures, lyricText),
            };
        });
        return {
            id: `section-${sectionIndex + 1}`,
            sectionNo: Number(section?.section_no || sectionIndex + 1),
            role,
            title,
            measureStart: Number(section?.measure_start || lines[0]?.measureStart || 1),
            measureEnd: Number(section?.measure_end || lines[lines.length - 1]?.measureEnd || 1),
            measureCount: Number(section?.measure_count || (lines.reduce((total, line) => total + Number(line.measureCount || 0), 0))),
            cadence: section?.cadence || lines[lines.length - 1]?.cadence || "open",
            strumming: sectionPattern,
            lines,
        };
    });

    const usageByChord = new Map();
    const providedDiagrams = Array.isArray(result?.chord_diagrams) ? result.chord_diagrams : [];
    const shapeLookup = new Map(
        [
            ...providedDiagrams,
            ...(result?.guitar_shapes && typeof result.guitar_shapes === "object" ? Object.values(result.guitar_shapes) : []),
        ]
            .map((shape) => [String(shape?.symbol || shape?.display_name || "").trim(), shape])
            .filter(([symbol]) => symbol)
    );
    chords.forEach((chord, index) => {
        const symbol = String(chord?.symbol || "").trim();
        if (!symbol) {
            return;
        }
        const existing = usageByChord.get(symbol) || {
            symbol,
            useCount: 0,
            firstIndex: index,
            firstMeasure: Number(chord?.measure_no || 1),
            shape: chord?.shape || shapeLookup.get(symbol) || null,
            source: chord?.source || "diatonic",
        };
        existing.useCount += 1;
        existing.firstMeasure = Math.min(existing.firstMeasure, Number(chord?.measure_no || existing.firstMeasure || 1));
        if (!existing.shape && chord?.shape) {
            existing.shape = chord.shape;
        }
        usageByChord.set(symbol, existing);
    });
    shapeLookup.forEach((shape, symbol) => {
        if (!usageByChord.has(symbol)) {
            usageByChord.set(symbol, {
                symbol,
                useCount: 0,
                firstIndex: Number.POSITIVE_INFINITY,
                firstMeasure: Number.POSITIVE_INFINITY,
                shape,
                source: "diatonic",
            });
        }
    });

    const diagramCandidates = Array.from(usageByChord.values())
        .map((item) => ({
            symbol: item.symbol,
            useCount: item.useCount,
            firstMeasure: Number.isFinite(item.firstMeasure) ? item.firstMeasure : null,
            firstIndex: item.firstIndex,
            source: item.source || "diatonic",
            ...(item.shape || { display_name: item.symbol, fingering: "see arranger", difficulty: "medium", family: "custom" }),
        }))
        .sort((left, right) => {
            if (right.useCount !== left.useCount) {
                return right.useCount - left.useCount;
            }
            return (left.firstIndex || Number.POSITIVE_INFINITY) - (right.firstIndex || Number.POSITIVE_INFINITY);
        });

    const highlightedSymbol = String(state.guitarHighlightedChordSymbol || "").trim();
    const highlightedIndex = highlightedSymbol
        ? diagramCandidates.findIndex((item) => item.symbol === highlightedSymbol)
        : -1;
    if (highlightedIndex > 5) {
        const [highlighted] = diagramCandidates.splice(highlightedIndex, 1);
        diagramCandidates.unshift(highlighted);
    }

    return {
        meta: {
            title: result?.title || "未命名吉他弹唱谱",
            artist: result?.artist || "",
            subtitle: result?.subtitle || "可弹、可唱、可打印的 lead sheet 视图",
            key: result?.key || "--",
            capoText: Number.isFinite(Number(result?.capo_suggestion?.capo))
                ? `Capo ${Number(result.capo_suggestion.capo)}`
                : "--",
            transposedKey: result?.capo_suggestion?.transposed_key || "--",
            tempo: result?.tempo || "--",
            timeSignature: result?.time_signature || "--",
            style: result?.style || "--",
            strumming: result?.strumming_pattern || {},
            melodyTrackName: result?.melody_track?.name || "--",
            melodyTrackSource: result?.melody_track?.source || "--",
            melodyTrackQuality: Number.isFinite(Number(result?.melody_track?.average_confidence))
                ? `${Math.round(Number(result.melody_track.average_confidence) * 100)}% / voiced ${Math.round(Number(result?.melody_track?.voiced_ratio || 0) * 100)}%`
                : "--",
        },
        sections,
        diagrams: diagramCandidates,
        visibleDiagrams: diagramCandidates.slice(0, 6),
        hiddenDiagramCount: Math.max(diagramCandidates.length - 6, 0),
        measures,
        chords,
        warnings: Array.isArray(result?.warnings) ? result.warnings : [],
    };
}

function renderGuitarViewModeToggle(mode) {
    const current = resolveGuitarViewMode(mode);
    return `
        <div class="guitar-view-mode">
            <span class="instrument-switch-label">视图模式</span>
            <div class="instrument-toggle guitar-view-mode-toggle" role="tablist" aria-label="吉他弹唱谱视图模式">
                <button class="instrument-toggle-button ${current === "screen" ? "active" : ""}" data-guitar-view-mode="screen" role="tab" type="button" aria-selected="${current === "screen" ? "true" : "false"}">屏幕模式</button>
                <button class="instrument-toggle-button ${current === "print" ? "active" : ""}" data-guitar-view-mode="print" role="tab" type="button" aria-selected="${current === "print" ? "true" : "false"}">打印模式</button>
            </div>
        </div>
    `;
}

function renderGuitarExportButton() {
    const busy = isBusy("guitar-export-pdf");
    return `
        <button
            class="secondary-button guitar-export-button"
            data-guitar-export-format="pdf"
            type="button"
            ${busy ? "disabled" : ""}
        >${busy ? "导出中..." : "导出 PDF"}</button>
    `;
}

function renderGuitarInlineStrumming(pattern) {
    if (!pattern) {
        return "";
    }
    return `
        <div class="guitar-inline-strumming">
            <span class="guitar-inline-strumming-label">${escapeHtmlText(pattern.section_title || pattern.role_label || "段落扫弦")}</span>
            <strong class="guitar-inline-strumming-pattern">${escapeHtmlText(resolveStrummingDisplayPattern(pattern))}</strong>
            <span class="guitar-inline-strumming-copy">${escapeHtmlText(pattern.counting || "--")} · ${escapeHtmlText(localizeStrummingDifficulty(pattern.difficulty || "--"))}</span>
        </div>
    `;
}

/**
 * Split a lyric string into per-chord segments.
 * Strategy: split lyric by whitespace; each chord gets one token; the last
 * chord absorbs any overflow tokens so nothing is dropped.
 */
function buildChordLyricPairs(allChords, lyricText) {
    const segments = String(lyricText || "").trim().split(/\s+/).filter((s) => s.length > 0);
    if (!allChords.length && !segments.length) {
        return [];
    }
    if (!allChords.length) {
        return segments.map((seg) => ({ chord: "", lyric: seg, source: "diatonic" }));
    }
    return allChords.map((chord, index) => {
        let lyric = "";
        if (index < segments.length) {
            // Last chord absorbs all remaining segments
            lyric = index === allChords.length - 1
                ? segments.slice(index).join(" ")
                : segments[index];
        }
        return { chord: String(chord?.symbol || ""), lyric, source: chord?.source || "diatonic" };
    });
}

/**
 * Inline chord-over-lyric layout matching popular guitar sheet apps.
 * Each chord name floats above its corresponding lyric segment in a flex row
 * that wraps naturally – no horizontal scroll, no separate measure boxes.
 */
function renderGuitarLeadLineInline(line, { highlightedChordSymbol = "" } = {}) {
    const measureSegments = Array.isArray(line?.measureSegments) ? line.measureSegments : [];
    if (!measureSegments.length) {
        return '<div class="analysis-note">当前这一行还没有可展示的弹唱内容。</div>';
    }
    const allChords = measureSegments.flatMap((m) => Array.isArray(m.chords) ? m.chords : []);
    const lyricText = line?.lyricText || "";
    const pairs = buildChordLyricPairs(allChords, lyricText);

    if (!pairs.length) {
        return `
            <div class="guitar-inline-lyric-line">
                <span class="guitar-inline-pair">
                    <span class="guitar-inline-chord is-empty">\u00a0</span>
                    <span class="guitar-inline-syllable">${escapeHtmlText(lyricText || "\u00a0")}</span>
                </span>
            </div>
        `;
    }

    return `
        <div class="guitar-inline-lyric-line">
            ${pairs.map((pair) => `
                <span class="guitar-inline-pair${pair.chord && highlightedChordSymbol === pair.chord ? " is-highlighted" : ""}">
                    <span class="guitar-inline-chord ${pair.chord ? escapeHtmlText(pair.source || "diatonic") : "is-empty"}"
                          ${pair.chord ? `data-guitar-chord-symbol="${escapeHtmlAttribute(pair.chord)}" role="button" tabindex="0"` : ""}>
                        ${pair.chord ? escapeHtmlText(pair.chord) : "\u00a0"}
                    </span>
                    <span class="guitar-inline-syllable">${escapeHtmlText(pair.lyric || "\u00a0")}</span>
                </span>
            `).join("")}
        </div>
    `;
}

/** Legacy measure-grid line renderer kept for reference; not used in main flow. */
function renderGuitarLeadLine(line, { highlightedChordSymbol = "" } = {}) {
    const measureSegments = Array.isArray(line?.measureSegments) ? line.measureSegments : [];
    if (!measureSegments.length) {
        return '<div class="analysis-note">当前这一行还没有可展示的弹唱内容。</div>';
    }
    return `
        <article class="guitar-lead-line-shell">
            <div class="guitar-lead-line-meta">
                <span class="guitar-lead-line-label">${escapeHtmlText(line.label || "正文行")}</span>
                <span class="guitar-lead-line-summary">${escapeHtmlText(String(line.measureCount || measureSegments.length))} 小节 · ${escapeHtmlText(localizeGuitarCadence(line.cadence))}</span>
            </div>
            <div class="guitar-lead-line-scroll">
                <div class="guitar-lead-line">
                    ${measureSegments.map((measure) => `
                        <div class="guitar-lead-measure" style="--measure-width:${measure.widthRem}rem">
                            <div class="guitar-lead-measure-head">
                                <span class="guitar-lead-measure-bar">|</span>
                                <span class="guitar-lead-measure-number">${escapeHtmlText(String(measure.measureNo || "--"))}</span>
                            </div>
                            <div class="guitar-lead-chord-row">
                                ${measure.chords.length ? measure.chords.map((chord) => `
                                    <button
                                        class="guitar-lead-chord-chip ${escapeHtmlText(chord.source || "diatonic")} ${highlightedChordSymbol && highlightedChordSymbol === chord.symbol ? "active" : ""}"
                                        data-guitar-chord-symbol="${escapeHtmlAttribute(chord.symbol || "--")}"
                                        type="button"
                                    >
                                        ${escapeHtmlText(chord.symbol || "--")}
                                    </button>
                                `).join("") : '<span class="guitar-lead-spacer">—</span>'}
                            </div>
                            <div class="guitar-lead-lyric-row ${measure.hasLyrics ? "" : "is-placeholder"} ${measure.lyricText ? "" : "is-empty"}">
                                <span class="guitar-lead-lyric-text">${escapeHtmlText(measure.lyricText || "")}</span>
                            </div>
                        </div>
                    `).join("")}
                    <span class="guitar-lead-final-bar">|</span>
                </div>
            </div>
        </article>
    `;
}

function renderGuitarLeadSection(section, options = {}) {
    const lines = Array.isArray(section?.lines) ? section.lines : [];
    const sectionLabel = [
        localizeGuitarSectionRole(section.role),
        section.title || "",
    ].filter(Boolean).join(" ");
    return `
        <section class="guitar-lead-section">
            <header class="guitar-lead-section-header">
                <div class="guitar-lead-section-copy">
                    <span class="guitar-lead-section-title">${escapeHtmlText(sectionLabel || "段落")}</span>
                    <span class="guitar-lead-section-meta">第 ${escapeHtmlText(String(section.measureStart || "--"))}-${escapeHtmlText(String(section.measureEnd || "--"))} 小节</span>
                </div>
                ${renderGuitarInlineStrumming(section.strumming)}
            </header>
            <div class="guitar-lead-lines">
                ${lines.map((line) => renderGuitarLeadLineInline(line, options)).join("")}
            </div>
        </section>
    `;
}

function renderGuitarChordRail(visibleDiagrams, totalCount, highlightedChordSymbol = "") {
    const items = Array.isArray(visibleDiagrams) ? visibleDiagrams : [];
    return `
        <aside class="guitar-chord-rail">
            <div class="guitar-chord-rail-head">
                <div>
                    <span class="guitar-sheet-kicker">Chord Diagram Rail</span>
                    <h4 class="guitar-chord-rail-title">常用和弦</h4>
                </div>
                <span class="guitar-meta-subtle">${escapeHtmlText(String(items.length))}/${escapeHtmlText(String(totalCount || items.length))} 个</span>
            </div>
            <div class="guitar-chord-rail-grid">
                ${items.map((shape) => `
                    <button
                        class="guitar-diagram-card ${highlightedChordSymbol && highlightedChordSymbol === shape.symbol ? "active" : ""}"
                        data-guitar-chord-symbol="${escapeHtmlAttribute(shape.symbol || "--")}"
                        type="button"
                    >
                        <div class="guitar-diagram-card-head">
                            <strong class="guitar-diagram-title">${escapeHtmlText(shape.symbol || shape.display_name || "--")}</strong>
                            <span class="guitar-diagram-usage">×${escapeHtmlText(String(shape.useCount || 0))}</span>
                        </div>
                        ${renderGuitarChordDiagramGlyph(shape)}
                        <div class="guitar-diagram-card-foot">
                            <span>${escapeHtmlText(shape.fingering || "--")}</span>
                            <span>${escapeHtmlText(localizeStrummingDifficulty(shape.difficulty || "medium"))}</span>
                        </div>
                    </button>
                `).join("") || '<div class="analysis-note">当前还没有可展示的常用和弦图。</div>'}
            </div>
            ${totalCount > items.length ? `<p class="guitar-meta-subtle">其余 ${escapeHtmlText(String(totalCount - items.length))} 个和弦暂时收起，避免把正文挤散。</p>` : ""}
        </aside>
    `;
}

function renderGuitarAuxBlocks(songSheet, result) {
    const measures = Array.isArray(songSheet?.measures) ? songSheet.measures : [];
    const chords = Array.isArray(songSheet?.chords) ? songSheet.chords : [];
    const measureMarkup = measures.slice(0, 12).map((measure) => `
        <span class="guitar-measure-chip">
            <strong>${escapeHtmlText(String(measure.measure_no || "--"))}</strong>
            <span>${escapeHtmlText((measure.chords || []).map((chord) => chord.symbol || "--").join(" · ") || "--")}</span>
        </span>
    `).join("");
    const sourceSummary = summarizeChordSources(chords);
    return `
        <section class="guitar-aux-grid">
            <article class="guitar-aux-card">
                <div class="guitar-aux-head">
                    <div>
                        <span class="guitar-sheet-kicker">Measure Summary</span>
                        <h4 class="guitar-aux-title">小节摘要</h4>
                    </div>
                </div>
                <div class="guitar-measure-chip-row">
                    ${measureMarkup || '<span class="analysis-note">当前还没有小节摘要。</span>'}
                </div>
            </article>
            <article class="guitar-aux-card">
                <div class="guitar-aux-head">
                    <div>
                        <span class="guitar-sheet-kicker">Chord Timeline</span>
                        <h4 class="guitar-aux-title">和弦时间轴</h4>
                    </div>
                </div>
                <div class="analysis-list">
                    ${chords.slice(0, 12).map((chord) => `
                        <div class="analysis-item">
                            <div>
                                <div class="analysis-item-title">${escapeHtmlText(chord.symbol || "--")}</div>
                                <div class="analysis-item-meta">第 ${escapeHtmlText(String(chord.measure_no || "--"))} 小节 / 第 ${escapeHtmlText(formatBeat(chord.beat_in_measure || 1))} 拍 / ${escapeHtmlText(localizeChordSource(chord.source || "diatonic"))}</div>
                            </div>
                            <div class="analysis-item-value">${formatBeat(chord.time || 0)} 秒</div>
                        </div>
                    `).join("") || '<div class="analysis-note">当前没有和弦时间轴结果。</div>'}
                </div>
            </article>
            <article class="guitar-aux-card">
                <div class="guitar-aux-head">
                    <div>
                        <span class="guitar-sheet-kicker">Process</span>
                        <h4 class="guitar-aux-title">识谱过程</h4>
                    </div>
                    <button class="ghost-button guitar-debug-toggle-btn" data-guitar-toggle-debug type="button">${state.guitarDebugExpanded ? "收起流程面板" : "查看流程面板"}</button>
                </div>
                <div class="analysis-chip-row">
                    ${sourceSummary.map((item) => `
                        <span class="analysis-chip">${escapeHtmlText(localizeChordSource(item.source))} ${escapeHtmlText(String(item.count))} 个</span>
                    `).join("") || '<span class="analysis-chip">当前没有和弦来源统计</span>'}
                </div>
                <p class="guitar-meta-subtle">分离轨、定调结果和和弦来源已经下沉到调试面板，默认收起，避免抢正文焦点。</p>
                ${Array.isArray(result?.warnings) && result.warnings.length ? `<div class="analysis-note">${escapeHtmlText(result.warnings.join("；"))}</div>` : ""}
            </article>
        </section>
    `;
}

function renderGuzhengOctaveMarks(note) {
    const above = Number(note?.octave_marks?.above || 0);
    const below = Number(note?.octave_marks?.below || 0);
    return `
        <span class="guzheng-octave guzheng-octave-top">${"•".repeat(Math.max(above, 0))}</span>
        <span class="guzheng-octave guzheng-octave-bottom">${"•".repeat(Math.max(below, 0))}</span>
    `;
}

function renderGuzhengTechniquePills(tags) {
    const items = Array.isArray(tags) ? tags : [];
    if (!items.length) {
        return '<span class="guzheng-technique-pill subtle">直弹为主</span>';
    }
    return items.map((tag) => `<span class="guzheng-technique-pill">${escapeHtmlText(tag)}</span>`).join("");
}

function parseNumericTimeSignature(timeSignature) {
    const match = String(timeSignature || "").trim().match(/^(\d+)\s*\/\s*(\d+)$/);
    if (!match) {
        return { numerator: 4, denominator: 4 };
    }
    return {
        numerator: Math.max(Number(match[1]) || 4, 1),
        denominator: Math.max(Number(match[2]) || 4, 1),
    };
}

function quantizeGuzhengDuration(beats) {
    const value = Number(beats);
    if (!Number.isFinite(value) || value <= 0) {
        return 1;
    }
    const candidates = [0.25, 0.5, 0.75, 1, 1.5, 2, 2.5, 3, 3.5, 4, 6];
    return candidates.reduce((closest, current) => (
        Math.abs(current - value) < Math.abs(closest - value) ? current : closest
    ), candidates[0]);
}

function resolveGuzhengMeasureLineWidth(measures, timeSignature) {
    const items = Array.isArray(measures) ? measures : [];
    const { numerator, denominator } = parseNumericTimeSignature(timeSignature);
    const averageDensity = items.length
        ? items.reduce((total, measure) => total + (Array.isArray(measure.notes) ? measure.notes.length : 0), 0) / items.length
        : 0;
    if (denominator === 8 && numerator >= 6) {
        return 2;
    }
    if (averageDensity >= 5) {
        return 2;
    }
    if (averageDensity >= 3.25) {
        return 3;
    }
    if (items.length <= 6) {
        return 3;
    }
    return 4;
}

function splitGuzhengMeasuresIntoLines(measures, timeSignature) {
    const items = Array.isArray(measures) ? measures : [];
    const measuresPerLine = resolveGuzhengMeasureLineWidth(items, timeSignature);
    const lines = [];
    for (let index = 0; index < items.length; index += measuresPerLine) {
        lines.push(items.slice(index, index + measuresPerLine));
    }
    return lines;
}

function paginateGuzhengLines(lines) {
    const items = Array.isArray(lines) ? lines : [];
    const linesPerPage = 5;
    const pages = [];
    for (let index = 0; index < items.length; index += linesPerPage) {
        pages.push(items.slice(index, index + linesPerPage));
    }
    return pages;
}

function createGuzhengRestToken(measureNo, startBeat, beats, index) {
    return {
        note_id: `gz_rest_${measureNo}_${index}`,
        measure_no: measureNo,
        start_beat: startBeat,
        beats,
        display_beats: beats,
        degree_display: "0",
        pitch: "Rest",
        octave_marks: { above: 0, below: 0 },
        technique_tags: [],
        is_rest: true,
    };
}

function buildGuzhengDisplayTokens(measure) {
    const notes = [...(Array.isArray(measure?.notes) ? measure.notes : [])]
        .sort((left, right) => Number(left?.start_beat || 1) - Number(right?.start_beat || 1));
    const totalBeats = Math.max(Number(measure?.beats || 4), 1);
    const measureEndBeat = totalBeats + 1;
    const tokens = [];
    let cursor = 1;
    let restIndex = 0;

    notes.forEach((note) => {
        const startBeat = Math.max(Number(note?.start_beat || cursor), 1);
        if (startBeat > cursor + 0.05) {
            const restBeats = quantizeGuzhengDuration(startBeat - cursor);
            tokens.push(createGuzhengRestToken(measure?.measure_no || 1, cursor, restBeats, restIndex));
            restIndex += 1;
            cursor = startBeat;
        }
        const duration = quantizeGuzhengDuration(note?.beats || 1);
        tokens.push({ ...note, display_beats: duration });
        cursor = Math.max(cursor, startBeat + duration);
    });

    if (cursor < measureEndBeat - 0.05) {
        const trailingRest = quantizeGuzhengDuration(measureEndBeat - cursor);
        tokens.push(createGuzhengRestToken(measure?.measure_no || 1, cursor, trailingRest, restIndex));
    }
    return tokens;
}

function splitGuzhengDegreeDisplay(display) {
    const raw = String(display || "0").trim() || "0";
    const match = raw.match(/^([#b]?)([0-7])$/i);
    if (!match) {
        return { accidental: "", digit: raw };
    }
    return {
        accidental: match[1] || "",
        digit: match[2] || raw,
    };
}

function resolveGuzhengRhythmDecorations(beats) {
    const duration = quantizeGuzhengDuration(beats);
    const table = [
        { beats: 0.25, underlineCount: 2, sustainCount: 0, dotted: false },
        { beats: 0.5, underlineCount: 1, sustainCount: 0, dotted: false },
        { beats: 0.75, underlineCount: 1, sustainCount: 0, dotted: true },
        { beats: 1, underlineCount: 0, sustainCount: 0, dotted: false },
        { beats: 1.5, underlineCount: 0, sustainCount: 0, dotted: true },
        { beats: 2, underlineCount: 0, sustainCount: 1, dotted: false },
        { beats: 2.5, underlineCount: 0, sustainCount: 1, dotted: true },
        { beats: 3, underlineCount: 0, sustainCount: 2, dotted: false },
        { beats: 3.5, underlineCount: 0, sustainCount: 2, dotted: true },
        { beats: 4, underlineCount: 0, sustainCount: 3, dotted: false },
        { beats: 6, underlineCount: 0, sustainCount: 5, dotted: false },
    ];
    return table.reduce((closest, current) => (
        Math.abs(current.beats - duration) < Math.abs(closest.beats - duration) ? current : closest
    ), table[0]);
}

function resolveGuzhengTechniqueMark(note) {
    const tags = Array.isArray(note?.technique_tags) ? note.technique_tags : [];
    if (tags.includes("上滑音候选")) {
        return "↗";
    }
    if (tags.includes("下滑音候选")) {
        return "↘";
    }
    if (tags.includes("摇指候选")) {
        return "∿";
    }
    if (tags.includes("按音候选") || note?.press_note_candidate) {
        return "按";
    }
    return "&nbsp;";
}

function renderGuzhengPaperOrnaments(note) {
    const tags = Array.isArray(note?.technique_tags) ? note.technique_tags : [];
    const items = [];
    if (tags.includes("摇指候选")) {
        items.push('<span class="guzheng-jianpu-wave-line">〰〰</span>');
    }
    if (tags.includes("上滑音候选")) {
        items.push('<span class="guzheng-jianpu-slide-arc slide-up"></span>');
    } else if (tags.includes("下滑音候选")) {
        items.push('<span class="guzheng-jianpu-slide-arc slide-down"></span>');
    } else if (tags.includes("按音候选") || note?.press_note_candidate) {
        items.push('<span class="guzheng-jianpu-bend-mark">⌒</span>');
    }
    if (!items.length) {
        return '<span class="guzheng-jianpu-ornament-placeholder"></span>';
    }
    return items.join("");
}

function resolveGuzhengPressText(note) {
    if (!note?.press_note_candidate) {
        return "";
    }
    const openDegree = Number(note?.open_degree);
    if (!Number.isFinite(openDegree) || openDegree <= 0) {
        return "按";
    }
    return String(openDegree);
}

function renderGuzhengPaperOctaveMarks(note) {
    const above = Number(note?.octave_marks?.above || 0);
    const below = Number(note?.octave_marks?.below || 0);
    return {
        above: "•".repeat(Math.max(above, 0)),
        below: "•".repeat(Math.max(below, 0)),
    };
}

function renderGuzhengUnderlineRows(underlineCount) {
    const count = Math.max(Number(underlineCount) || 0, 0);
    if (!count) {
        return '<span class="guzheng-jianpu-underline guzheng-jianpu-underline-empty"></span>';
    }
    return Array.from({ length: count }, () => '<span class="guzheng-jianpu-underline"></span>').join("");
}

function pitchToMidiValue(pitch) {
    const raw = String(pitch || "").trim();
    if (!raw || /^rest$/i.test(raw)) {
        return null;
    }
    try {
        const normalized = normalizePitchInput(raw);
        const match = normalized.match(/^([A-G])(#?)(-?\d+)$/);
        if (!match) {
            return null;
        }
        const noteName = `${match[1]}${match[2] || ""}`;
        const octave = Number(match[3]);
        if (!Object.prototype.hasOwnProperty.call(NOTE_INDEX, noteName) || !Number.isFinite(octave)) {
            return null;
        }
        return (octave + 1) * 12 + NOTE_INDEX[noteName];
    } catch {
        return null;
    }
}

function isGuzhengGraceCandidate(note, nextNote) {
    if (!note || !nextNote || note.is_rest || nextNote.is_rest) {
        return false;
    }
    const duration = Number(note.display_beats || note.beats || 0);
    const nextDuration = Number(nextNote.display_beats || nextNote.beats || 0);
    if (!Number.isFinite(duration) || duration > 0.5 || !Number.isFinite(nextDuration) || nextDuration < 1) {
        return false;
    }
    const currentMidi = pitchToMidiValue(note.pitch);
    const nextMidi = pitchToMidiValue(nextNote.pitch);
    if (currentMidi === null || nextMidi === null) {
        return false;
    }
    return Math.abs(nextMidi - currentMidi) <= 2;
}

function shouldGuzhengSlurBetween(currentNote, nextNote) {
    if (!currentNote || !nextNote || currentNote.is_rest || nextNote.is_rest) {
        return false;
    }
    const currentMidi = pitchToMidiValue(currentNote.pitch);
    const nextMidi = pitchToMidiValue(nextNote.pitch);
    if (currentMidi === null || nextMidi === null) {
        return false;
    }
    const interval = Math.abs(nextMidi - currentMidi);
    if (interval > 3) {
        return false;
    }
    const currentTags = Array.isArray(currentNote.technique_tags) ? currentNote.technique_tags : [];
    const nextTags = Array.isArray(nextNote.technique_tags) ? nextNote.technique_tags : [];
    if (
        currentTags.includes("上滑音候选") ||
        currentTags.includes("下滑音候选") ||
        nextTags.includes("上滑音候选") ||
        nextTags.includes("下滑音候选")
    ) {
        return true;
    }
    return Number(currentNote.display_beats || currentNote.beats || 0) <= 1
        && Number(nextNote.display_beats || nextNote.beats || 0) <= 1.5;
}

function buildGuzhengMeasureSignature(measure) {
    return buildGuzhengDisplayTokens(measure)
        .map((note) => {
            const octave = note.octave_marks || {};
            return [
                note.is_rest ? "R" : note.degree_display || "--",
                quantizeGuzhengDuration(note.display_beats || note.beats || 1),
                Number(octave.above || 0),
                Number(octave.below || 0),
                note.press_note_candidate ? "P" : "O",
            ].join(":");
        })
        .join("|");
}

function buildGuzhengVisualNoteItems(measure) {
    const tokens = buildGuzhengDisplayTokens(measure);
    const visualItems = [];
    let pendingGraceNotes = [];
    for (let index = 0; index < tokens.length; index += 1) {
        const current = tokens[index];
        const next = tokens[index + 1];
        if (isGuzhengGraceCandidate(current, next)) {
            pendingGraceNotes.push(current);
            continue;
        }
        visualItems.push({
            note: current,
            graceNotes: pendingGraceNotes,
            slurStart: false,
            slurEnd: false,
        });
        pendingGraceNotes = [];
    }
    pendingGraceNotes.forEach((note) => {
        visualItems.push({
            note,
            graceNotes: [],
            slurStart: false,
            slurEnd: false,
        });
    });
    for (let index = 0; index < visualItems.length - 1; index += 1) {
        if (shouldGuzhengSlurBetween(visualItems[index].note, visualItems[index + 1].note)) {
            visualItems[index].slurStart = true;
            visualItems[index + 1].slurEnd = true;
        }
    }
    return visualItems;
}

function renderGuzhengGraceNotes(graceNotes) {
    const items = Array.isArray(graceNotes) ? graceNotes : [];
    if (!items.length) {
        return "";
    }
    return `
        <span class="guzheng-jianpu-grace-cluster">
            ${items.map((note) => {
                const { accidental, digit } = splitGuzhengDegreeDisplay(note?.degree_display || "--");
                const octave = renderGuzhengPaperOctaveMarks(note);
                return `
                    <span class="guzheng-jianpu-grace-note ${note?.press_note_candidate ? "requires-press" : ""}">
                        <span class="guzheng-jianpu-grace-top">${escapeHtmlText(octave.above || "")}</span>
                        <span class="guzheng-jianpu-grace-glyph">
                            ${accidental ? `<span class="guzheng-jianpu-grace-accidental">${escapeHtmlText(accidental)}</span>` : ""}
                            <span class="guzheng-jianpu-grace-digit">${escapeHtmlText(digit)}</span>
                        </span>
                        <span class="guzheng-jianpu-grace-bottom">${escapeHtmlText(octave.below || "")}</span>
                    </span>
                `;
            }).join("")}
        </span>
    `;
}

function renderGuzhengPaperNote(note, options = {}) {
    const isRest = Boolean(note?.is_rest);
    const { accidental, digit } = splitGuzhengDegreeDisplay(isRest ? "0" : note?.degree_display || "--");
    const rhythm = resolveGuzhengRhythmDecorations(note?.display_beats || note?.beats || 1);
    const octave = renderGuzhengPaperOctaveMarks(note);
    const graceMarkup = renderGuzhengGraceNotes(options.graceNotes || []);
    return `
        <span class="guzheng-jianpu-note-group ${options.slurStart ? "slur-start" : ""} ${options.slurEnd ? "slur-end" : ""}">
            ${options.slurStart ? '<span class="guzheng-jianpu-slur-part slur-start"></span>' : ""}
            ${options.slurEnd ? '<span class="guzheng-jianpu-slur-part slur-end"></span>' : ""}
            ${graceMarkup}
            <span class="guzheng-jianpu-note ${note?.press_note_candidate ? "requires-press" : ""} ${isRest ? "is-rest" : ""}" title="${escapeHtmlText(isRest ? "休止" : `${note?.pitch || "--"} · ${formatBeat(note?.beats || 0)} 拍`)}">
                <span class="guzheng-jianpu-ornaments">${renderGuzhengPaperOrnaments(note)}</span>
                <span class="guzheng-jianpu-octave-top">${escapeHtmlText(octave.above || "")}</span>
                <span class="guzheng-jianpu-glyph">
                    ${accidental ? `<span class="guzheng-jianpu-accidental">${escapeHtmlText(accidental)}</span>` : ""}
                    <span class="guzheng-jianpu-digit">${escapeHtmlText(digit)}</span>
                    ${rhythm.dotted ? '<span class="guzheng-jianpu-dot">.</span>' : ""}
                    ${Array.from({ length: Math.max(Number(rhythm.sustainCount) || 0, 0) }, () => '<span class="guzheng-jianpu-sustain">—</span>').join("")}
                </span>
                <span class="guzheng-jianpu-underlines">${renderGuzhengUnderlineRows(rhythm.underlineCount)}</span>
                <span class="guzheng-jianpu-octave-bottom">${escapeHtmlText(octave.below || "")}</span>
                <span class="guzheng-jianpu-press-text">${escapeHtmlText(resolveGuzhengPressText(note))}</span>
            </span>
        </span>
    `;
}

function renderGuzhengJianpuPaper(measures, result) {
    const items = Array.isArray(measures) ? measures : [];
    if (!items.length) {
        return '<div class="analysis-note">当前还没有可展示的古筝简谱。</div>';
    }
    const lines = splitGuzhengMeasuresIntoLines(items, result?.time_signature || "4/4");
    const pages = paginateGuzhengLines(lines);
    const keyText = String(result?.key || "C").replace(/m$/i, "");
    const modeText = /m$/i.test(String(result?.key || "")) ? "小调" : "大调";
    const measureRepeatLookup = new Map();
    let previousSignature = "";
    items.forEach((measure) => {
        const signature = buildGuzhengMeasureSignature(measure);
        measureRepeatLookup.set(Number(measure?.measure_no || 0), Boolean(signature && signature === previousSignature));
        previousSignature = signature;
    });
    return `
        <article class="guzheng-jianpu-paper">
            <header class="guzheng-jianpu-header">
                <div class="guzheng-jianpu-signature">
                    <div class="guzheng-jianpu-signature-main">1 = ${escapeHtmlText(keyText || "C")}</div>
                    <div class="guzheng-jianpu-signature-sub">${escapeHtmlText(result?.time_signature || "4/4")}</div>
                    <div class="guzheng-jianpu-signature-tempo">♩ = ${escapeHtmlText(String(result?.tempo || "--"))}</div>
                </div>
                <div class="guzheng-jianpu-title-block">
                    <h4 class="guzheng-jianpu-title">${escapeHtmlText(result?.title || "未命名古筝谱")}</h4>
                    <p class="guzheng-jianpu-subtitle">古筝简谱 · ${escapeHtmlText(modeText)} · ${escapeHtmlText(result?.instrument_profile?.tuning || "21弦 D调定弦")}</p>
                </div>
                <div class="guzheng-jianpu-meta">
                    <span>${escapeHtmlText(result?.style || "traditional")}</span>
                    <span>${escapeHtmlText(result?.instrument_profile?.range || "--")}</span>
                </div>
            </header>
            <div class="guzheng-jianpu-pages">
                ${pages.map((pageLines, pageIndex) => `
                    <section class="guzheng-jianpu-page">
                        <header class="guzheng-jianpu-running-header">
                            <div class="guzheng-jianpu-running-title">${escapeHtmlText(result?.title || "未命名古筝谱")}</div>
                            <div class="guzheng-jianpu-running-meta">1 = ${escapeHtmlText(keyText || "C")} · ${escapeHtmlText(result?.time_signature || "4/4")} · ♩ = ${escapeHtmlText(String(result?.tempo || "--"))}</div>
                            <div class="guzheng-jianpu-running-page">第 ${pageIndex + 1} 页</div>
                        </header>
                        <div class="guzheng-jianpu-body">
                            ${pageLines.map((line, lineIndex) => `
                                <div class="guzheng-jianpu-line">
                                    <div class="guzheng-jianpu-line-marker">
                                        ${pageIndex === 0 && lineIndex === 0 ? "&nbsp;" : escapeHtmlText(String(line[0]?.measure_no || ""))}
                                    </div>
                                    <div class="guzheng-jianpu-line-content" style="--guzheng-line-measure-count:${Math.max(line.length, 1)};">
                                        ${line.map((measure, measureIndex) => `
                                            <div class="guzheng-jianpu-measure ${measureIndex === line.length - 1 ? "is-line-end" : ""}">
                                                <div class="guzheng-jianpu-measure-notes">
                                                    ${measureRepeatLookup.get(Number(measure?.measure_no || 0))
                                                        ? '<span class="guzheng-jianpu-repeat-sign" title="同前小节">〃</span>'
                                                        : (buildGuzhengVisualNoteItems(measure).map((item) => renderGuzhengPaperNote(item.note, item)).join("") || '<span class="guzheng-jianpu-note-group"><span class="guzheng-jianpu-note is-rest"><span class="guzheng-jianpu-ornaments"><span class="guzheng-jianpu-ornament-placeholder"></span></span><span class="guzheng-jianpu-octave-top">&nbsp;</span><span class="guzheng-jianpu-glyph"><span class="guzheng-jianpu-digit">0</span></span><span class="guzheng-jianpu-underlines"><span class="guzheng-jianpu-underline guzheng-jianpu-underline-empty"></span></span><span class="guzheng-jianpu-octave-bottom">&nbsp;</span><span class="guzheng-jianpu-press-text">&nbsp;</span></span></span>')}
                                                </div>
                                                <span class="guzheng-jianpu-bar"></span>
                                            </div>
                                        `).join("")}
                                    </div>
                                </div>
                            `).join("")}
                        </div>
                        <div class="guzheng-jianpu-page-footer">第 ${pageIndex + 1} / ${pages.length} 页</div>
                    </section>
                `).join("")}
            </div>
        </article>
    `;
}

function buildTraditionalFallbackMeasures(result, instrumentType) {
    const measures = Array.isArray(result?.measures) ? result.measures : [];
    return measures.map((measure) => ({
        measure_no: Number(measure?.measure_no || 1),
        beats: Number(measure?.beats || 4),
        notes: (Array.isArray(measure?.notes) ? measure.notes : []).map((note) => ({
            ...note,
            annotation_text: instrumentType === "guzheng"
                ? resolveGuzhengPressText(note)
                : note?.out_of_range
                    ? "超"
                    : note?.special_fingering_candidate
                        ? "特"
                        : note?.half_hole_candidate
                            ? "半"
                            : "",
            annotation_hint: instrumentType === "guzheng"
                ? note?.position_hint || ""
                : note?.fingering_hint || "",
            fingering_text: instrumentType === "guzheng"
                ? note?.string_label || ""
                : note?.hole_pattern || "",
            fingering_hint: instrumentType === "guzheng"
                ? note?.position_hint || note?.zone_label || ""
                : note?.register_label || note?.fingering_hint || "",
            display_beats: Number(note?.display_beats || note?.beats || 1),
        })),
    }));
}

function buildTraditionalJianpuSheetModel(result, instrumentType) {
    const ir = result?.jianpu_ir && typeof result.jianpu_ir === "object" ? result.jianpu_ir : {};
    const measures = Array.isArray(ir.measures) && ir.measures.length
        ? ir.measures
        : buildTraditionalFallbackMeasures(result, instrumentType);
    const lines = Array.isArray(ir.lines) && ir.lines.length
        ? ir.lines
        : splitGuzhengMeasuresIntoLines(measures, result?.time_signature || "4/4").map((line, index) => ({
            line_no: index + 1,
            measure_start: Number(line[0]?.measure_no || 1),
            measure_end: Number(line[line.length - 1]?.measure_no || 1),
            measures: line,
        }));
    const pages = Array.isArray(ir.pages) && ir.pages.length
        ? ir.pages
        : paginateGuzhengLines(lines.map((line) => line.measures)).map((pageLines, pageIndex) => ({
            page_no: pageIndex + 1,
            lines: pageLines.map((line, lineIndex) => ({
                line_no: pageIndex * 5 + lineIndex + 1,
                measure_start: Number(line[0]?.measure_no || 1),
                measure_end: Number(line[line.length - 1]?.measure_no || 1),
                measures: line,
            })),
        }));
    const noteCount = measures.reduce((total, measure) => total + (Array.isArray(measure.notes) ? measure.notes.length : 0), 0);
    const meta = ir.meta && typeof ir.meta === "object" ? ir.meta : {};

    return {
        instrumentType,
        result,
        measures,
        lines,
        pages,
        noteCount,
        warnings: Array.isArray(result?.warnings) ? result.warnings : [],
        layoutMode: resolveJianpuLayoutMode(state.jianpuLayoutMode),
        annotationLayer: resolveJianpuAnnotationLayer(state.jianpuAnnotationLayer),
        meta: {
            title: meta.title || result?.title || (instrumentType === "guzheng" ? "未命名古筝谱" : "未命名笛子谱"),
            keyDisplay: meta.key_display || String(result?.key || "C").replace(/m$/i, ""),
            keySignature: meta.key_signature || result?.key || "C",
            modeText: meta.mode_text || (/m$/i.test(String(result?.key || "")) ? "小调" : "大调"),
            timeSignature: meta.time_signature || result?.time_signature || "4/4",
            tempo: Number(meta.tempo || result?.tempo || 0),
            instrumentName: meta.instrument_name || (instrumentType === "guzheng" ? "古筝" : "笛子"),
            instrumentSubtitle: meta.instrument_subtitle
                || (instrumentType === "guzheng"
                    ? `古筝简谱 · ${/m$/i.test(String(result?.key || "")) ? "小调" : "大调"} · ${result?.instrument_profile?.tuning || "21弦 D调定弦"}`
                    : `笛子简谱 · 按 ${localizeFluteType(result?.flute_type || "G")} 的筒音关系显示`),
            instrumentRange: meta.instrument_range || result?.instrument_profile?.range || "--",
            instrumentBadge: meta.instrument_badge
                || (instrumentType === "guzheng"
                    ? result?.instrument_profile?.tuning || "21弦 D调定弦"
                    : localizeFluteType(result?.flute_type || "G")),
            fluteType: meta.flute_type || result?.flute_type || "",
        },
        statistics: ir.statistics && typeof ir.statistics === "object" ? ir.statistics : {},
    };
}

function renderTraditionalLayoutModeToggle(current) {
    return `
        <div class="instrument-toggle traditional-view-mode-toggle" role="tablist" aria-label="简谱视图模式">
            <button class="instrument-toggle-button ${current === "preview" ? "active" : ""}" data-jianpu-layout-mode="preview" role="tab" type="button" aria-selected="${current === "preview" ? "true" : "false"}">预览模式</button>
            <button class="instrument-toggle-button ${current === "print" ? "active" : ""}" data-jianpu-layout-mode="print" role="tab" type="button" aria-selected="${current === "print" ? "true" : "false"}">打印模式</button>
        </div>
    `;
}

function renderTraditionalMarkupModeToggle(currentLayer, instrumentType) {
    const mode = resolveTraditionalMarkupMode(currentLayer);
    const annotatedLabel = instrumentType === "guzheng" ? "带弦位/技法" : "带指法/技法";
    return `
        <div class="instrument-toggle traditional-markup-mode-toggle" role="tablist" aria-label="简谱标注模式">
            <button class="instrument-toggle-button ${mode === "plain" ? "active" : ""}" data-jianpu-markup-mode="plain" role="tab" type="button" aria-selected="${mode === "plain" ? "true" : "false"}">纯净简谱</button>
            <button class="instrument-toggle-button ${mode === "annotated" ? "active" : ""}" data-jianpu-markup-mode="annotated" role="tab" type="button" aria-selected="${mode === "annotated" ? "true" : "false"}">${escapeHtmlText(annotatedLabel)}</button>
        </div>
    `;
}

function renderTraditionalAnnotationLayerToggle(current, instrumentType) {
    const labelPrefix = instrumentType === "guzheng" ? "弦位" : "指法";
    const options = [
        { value: "basic", label: "基础正文" },
        { value: "fingering", label: `${labelPrefix}层` },
        { value: "technique", label: "技法层" },
        { value: "all", label: "完整标注" },
    ];
    return `
        <div class="instrument-toggle traditional-annotation-toggle" role="tablist" aria-label="简谱标注层">
            ${options.map((option) => `
                <button class="instrument-toggle-button ${current === option.value ? "active" : ""}" data-jianpu-annotation-layer="${option.value}" role="tab" type="button" aria-selected="${current === option.value ? "true" : "false"}">${escapeHtmlText(option.label)}</button>
            `).join("")}
        </div>
    `;
}

function renderTraditionalExportButtons(instrumentType) {
    const busy = isBusy(`traditional-export-${instrumentType}`);
    const buttons = [
        { format: "jianpu", label: "导出 jianpu-ly 源" },
        { format: "ly", label: "导出 LilyPond 源" },
        { format: "pdf", label: "导出 PDF" },
    ];
    return `
        <div class="traditional-export-row">
            ${buttons.map((button) => `
                <button
                    class="secondary-button traditional-export-button"
                    data-traditional-export-format="${button.format}"
                    type="button"
                    ${busy ? "disabled" : ""}
                >${busy ? "导出中..." : escapeHtmlText(button.label)}</button>
            `).join("")}
        </div>
    `;
}

function buildTraditionalPreviewPageUrl(preview, page) {
    const baseUrl = buildServerUrl(page?.download_url || "");
    if (!baseUrl) {
        return "";
    }
    const cacheToken = encodeURIComponent(String(preview?.signature || preview?.file_name || TRANSCRIPTION_UI_BUILD));
    return `${baseUrl}${baseUrl.includes("?") ? "&" : "?"}v=${cacheToken}`;
}

function renderTraditionalEngravedPreview(model, preview, instrumentType) {
    const busy = isBusy(`traditional-render-${instrumentType}`);
    const previewPages = Array.isArray(preview?.preview_pages) ? preview.preview_pages : [];
    const renderEngine = previewPages.length ? "jianpu-ly + LilyPond" : "统一排版器";
    const pageCount = Number(preview?.manifest?.page_count || previewPages.length || 0);
    const markupMode = resolveTraditionalMarkupMode(model.annotationLayer);
    const layerLabels = {
        basic: "基础正文",
        fingering: instrumentType === "guzheng" ? "弦位层" : "指法层",
        technique: "技法层",
        all: "完整标注",
    };

    if (busy && !previewPages.length) {
        return `
            <div class="traditional-engraved-shell is-loading">
                <div class="traditional-engraved-status">
                    <strong>${renderEngine}</strong>
                    <span>正在根据当前 ${model.layoutMode === "print" ? "打印" : "预览"} 模式和标注层重新排版…</span>
                </div>
            </div>
        `;
    }

    if (preview?.error && !previewPages.length) {
        return `
            <div class="traditional-engraved-shell has-error">
                <div class="analysis-note">当前未能生成统一排版预览：${escapeHtmlText(preview.error)}</div>
            </div>
        `;
    }

    if (!previewPages.length) {
        return '<div class="analysis-note">当前还没有可展示的统一排版页面。</div>';
    }

    return `
        <div class="traditional-engraved-shell ${model.layoutMode === "print" ? "print-mode" : "preview-mode"}">
            <div class="traditional-engraved-status">
                <div>
                    <span class="traditional-engraved-kicker">统一排版器</span>
                    <strong>${renderEngine}</strong>
                </div>
                <div class="analysis-chip-row">
                    <span class="analysis-chip">${pageCount} 页</span>
                    <span class="analysis-chip">${model.layoutMode === "print" ? "打印模式" : "预览模式"}</span>
                    <span class="analysis-chip">${markupMode === "plain" ? "纯净简谱" : "带标注简谱"}</span>
                    <span class="analysis-chip">${escapeHtmlText(layerLabels[resolveJianpuAnnotationLayer(model.annotationLayer)] || "基础正文")}</span>
                </div>
            </div>
            <div class="traditional-engraved-pages">
                ${previewPages.map((page) => `
                    <figure class="traditional-engraved-page">
                        <img
                            class="traditional-engraved-image"
                            src="${escapeHtmlText(buildTraditionalPreviewPageUrl(preview, page))}"
                            alt="${escapeHtmlText(`${instrumentType === "guzheng" ? "古筝" : "笛子"}简谱第 ${Number(page.page_number || 1)} 页`)}"
                            loading="lazy"
                        />
                        <figcaption class="traditional-engraved-caption">第 ${Number(page.page_number || 1)} 页</figcaption>
                    </figure>
                `).join("")}
            </div>
        </div>
    `;
}

function renderDiziInlineFluteTypeSelect(current) {
    const resolved = resolveDiziFluteType(current);
    return `
        <label class="traditional-inline-field">
            <span class="traditional-inline-label">笛型</span>
            <select class="traditional-inline-select" data-dizi-inline-flute-type>
                ${["C", "D", "E", "F", "G", "A", "Bb"].map((value) => `
                    <option value="${value}" ${resolved === value ? "selected" : ""}>${escapeHtmlText(localizeFluteType(value))}</option>
                `).join("")}
            </select>
            <span class="traditional-inline-copy">正文按当前笛型的筒音关系显示</span>
        </label>
    `;
}

function renderTraditionalPaperOrnaments(note, instrumentType) {
    const tags = Array.isArray(note?.technique_tags) ? note.technique_tags : [];
    const items = [];
    if (tags.includes("摇指候选") || tags.includes("颤音/长音保持候选")) {
        items.push('<span class="guzheng-jianpu-wave-line">〰〰</span>');
    }
    if (tags.includes("上滑音候选")) {
        items.push('<span class="guzheng-jianpu-slide-arc slide-up"></span>');
    } else if (tags.includes("下滑音候选")) {
        items.push('<span class="guzheng-jianpu-slide-arc slide-down"></span>');
    } else if (tags.includes("滑音候选")) {
        items.push('<span class="guzheng-jianpu-slide-arc traditional-slide-arc-plain"></span>');
    }
    if (tags.includes("换气点")) {
        items.push('<span class="traditional-jianpu-breath-mark">∨</span>');
    }
    if ((tags.includes("按音候选") || note?.press_note_candidate) && instrumentType === "guzheng") {
        items.push('<span class="guzheng-jianpu-bend-mark">⌒</span>');
    }
    if (!items.length) {
        return '<span class="guzheng-jianpu-ornament-placeholder"></span>';
    }
    return items.join("");
}

function resolveTraditionalAnnotationText(note, instrumentType, annotationLayer) {
    if (note?.is_rest) {
        return "";
    }
    const layer = resolveJianpuAnnotationLayer(annotationLayer);
    const annotationText = String(note?.annotation_text || "").trim();
    const fingeringText = String(note?.fingering_text || "").trim();
    if (instrumentType === "guzheng") {
        if (layer === "fingering") {
            return fingeringText;
        }
        if (layer === "technique") {
            return annotationText;
        }
        if (layer === "all") {
            return annotationText || fingeringText;
        }
        return annotationText;
    }
    if (layer === "fingering" || layer === "all") {
        return fingeringText;
    }
    if (layer === "technique") {
        return annotationText;
    }
    return "";
}

function buildTraditionalMeasureSignature(measure, instrumentType) {
    return buildGuzhengDisplayTokens(measure)
        .map((note) => {
            const octave = note.octave_marks || {};
            return [
                note.is_rest ? "R" : note.degree_display || "--",
                quantizeGuzhengDuration(note.display_beats || note.beats || 1),
                Number(octave.above || 0),
                Number(octave.below || 0),
                resolveTraditionalAnnotationText(note, instrumentType, "all") || "N",
            ].join(":");
        })
        .join("|");
}

function renderTraditionalPaperNote(note, options = {}, instrumentType, annotationLayer) {
    const isRest = Boolean(note?.is_rest);
    const { accidental, digit } = splitGuzhengDegreeDisplay(isRest ? "0" : note?.degree_display || "--");
    const rhythm = resolveGuzhengRhythmDecorations(note?.display_beats || note?.beats || 1);
    const octave = renderGuzhengPaperOctaveMarks(note);
    const graceMarkup = renderGuzhengGraceNotes(options.graceNotes || []);
    const annotationText = resolveTraditionalAnnotationText(note, instrumentType, annotationLayer);
    const noteTitle = isRest
        ? "休止"
        : [
            note?.pitch || "--",
            `${formatBeat(note?.beats || 0)} 拍`,
            note?.annotation_hint || note?.fingering_hint || "",
        ].filter(Boolean).join(" · ");
    return `
        <span class="guzheng-jianpu-note-group ${options.slurStart ? "slur-start" : ""} ${options.slurEnd ? "slur-end" : ""}">
            ${options.slurStart ? '<span class="guzheng-jianpu-slur-part slur-start"></span>' : ""}
            ${options.slurEnd ? '<span class="guzheng-jianpu-slur-part slur-end"></span>' : ""}
            ${graceMarkup}
            <span class="guzheng-jianpu-note traditional-jianpu-note instrument-${instrumentType} ${note?.press_note_candidate ? "requires-press" : ""} ${isRest ? "is-rest" : ""}" title="${escapeHtmlText(noteTitle)}">
                <span class="guzheng-jianpu-ornaments">${renderTraditionalPaperOrnaments(note, instrumentType)}</span>
                <span class="guzheng-jianpu-octave-top">${escapeHtmlText(octave.above || "")}</span>
                <span class="guzheng-jianpu-glyph">
                    ${accidental ? `<span class="guzheng-jianpu-accidental">${escapeHtmlText(accidental)}</span>` : ""}
                    <span class="guzheng-jianpu-digit">${escapeHtmlText(digit)}</span>
                    ${rhythm.dotted ? '<span class="guzheng-jianpu-dot">.</span>' : ""}
                    ${Array.from({ length: Math.max(Number(rhythm.sustainCount) || 0, 0) }, () => '<span class="guzheng-jianpu-sustain">—</span>').join("")}
                </span>
                <span class="guzheng-jianpu-underlines">${renderGuzhengUnderlineRows(rhythm.underlineCount)}</span>
                <span class="guzheng-jianpu-octave-bottom">${escapeHtmlText(octave.below || "")}</span>
                <span class="guzheng-jianpu-press-text traditional-jianpu-annotation ${instrumentType === "dizi" ? "is-dizi" : "is-guzheng"}">${escapeHtmlText(annotationText)}</span>
            </span>
        </span>
    `;
}

function renderTraditionalJianpuPaper(model) {
    const pages = Array.isArray(model?.pages) ? model.pages : [];
    if (!pages.length) {
        return '<div class="analysis-note">当前还没有可展示的简谱正文。</div>';
    }

    const measureRepeatLookup = new Map();
    let previousSignature = "";
    model.measures.forEach((measure) => {
        const signature = buildTraditionalMeasureSignature(measure, model.instrumentType);
        measureRepeatLookup.set(Number(measure?.measure_no || 0), Boolean(signature && signature === previousSignature));
        previousSignature = signature;
    });

    return `
        <article class="guzheng-jianpu-paper traditional-jianpu-paper instrument-${model.instrumentType} ${model.layoutMode === "print" ? "print-mode" : "preview-mode"}">
            <header class="guzheng-jianpu-header">
                <div class="guzheng-jianpu-signature">
                    <div class="guzheng-jianpu-signature-main">1 = ${escapeHtmlText(model.meta.keyDisplay || "C")}</div>
                    <div class="guzheng-jianpu-signature-sub">${escapeHtmlText(model.meta.timeSignature || "4/4")}</div>
                    <div class="guzheng-jianpu-signature-tempo">♩ = ${escapeHtmlText(String(model.meta.tempo || "--"))}</div>
                </div>
                <div class="guzheng-jianpu-title-block">
                    <h4 class="guzheng-jianpu-title">${escapeHtmlText(model.meta.title || "未命名简谱")}</h4>
                    <p class="guzheng-jianpu-subtitle">${escapeHtmlText(model.meta.instrumentSubtitle || "")}</p>
                </div>
                <div class="guzheng-jianpu-meta">
                    <span>${escapeHtmlText(model.meta.instrumentBadge || "--")}</span>
                    <span>${escapeHtmlText(model.meta.instrumentRange || "--")}</span>
                </div>
            </header>
            <div class="guzheng-jianpu-pages">
                ${pages.map((page) => `
                    <section class="guzheng-jianpu-page traditional-jianpu-page">
                        <header class="guzheng-jianpu-running-header">
                            <div class="guzheng-jianpu-running-title">${escapeHtmlText(model.meta.title || "未命名简谱")}</div>
                            <div class="guzheng-jianpu-running-meta">1 = ${escapeHtmlText(model.meta.keyDisplay || "C")} · ${escapeHtmlText(model.meta.timeSignature || "4/4")} · ♩ = ${escapeHtmlText(String(model.meta.tempo || "--"))} · ${escapeHtmlText(model.meta.instrumentBadge || "--")}</div>
                            <div class="guzheng-jianpu-running-page">第 ${Number(page?.page_no || 1)} 页</div>
                        </header>
                        <div class="guzheng-jianpu-body">
                            ${(Array.isArray(page?.lines) ? page.lines : []).map((line, lineIndex) => {
                                const measures = Array.isArray(line?.measures) ? line.measures : [];
                                return `
                                    <div class="guzheng-jianpu-line">
                                        <div class="guzheng-jianpu-line-marker">
                                            ${Number(page?.page_no || 1) === 1 && lineIndex === 0 ? "&nbsp;" : escapeHtmlText(String(measures[0]?.measure_no || ""))}
                                        </div>
                                        <div class="guzheng-jianpu-line-content" style="--guzheng-line-measure-count:${Math.max(measures.length, 1)};">
                                            ${measures.map((measure, measureIndex) => `
                                                <div class="guzheng-jianpu-measure ${measureIndex === measures.length - 1 ? "is-line-end" : ""}">
                                                    <div class="guzheng-jianpu-measure-notes">
                                                        ${measureRepeatLookup.get(Number(measure?.measure_no || 0))
                                                            ? '<span class="guzheng-jianpu-repeat-sign" title="同前小节">〃</span>'
                                                            : (buildGuzhengVisualNoteItems(measure).map((item) => renderTraditionalPaperNote(item.note, item, model.instrumentType, model.annotationLayer)).join("") || '<span class="guzheng-jianpu-note-group"><span class="guzheng-jianpu-note is-rest"><span class="guzheng-jianpu-ornaments"><span class="guzheng-jianpu-ornament-placeholder"></span></span><span class="guzheng-jianpu-octave-top">&nbsp;</span><span class="guzheng-jianpu-glyph"><span class="guzheng-jianpu-digit">0</span></span><span class="guzheng-jianpu-underlines"><span class="guzheng-jianpu-underline guzheng-jianpu-underline-empty"></span></span><span class="guzheng-jianpu-octave-bottom">&nbsp;</span><span class="guzheng-jianpu-press-text">&nbsp;</span></span></span>')}
                                                    </div>
                                                    <span class="guzheng-jianpu-bar"></span>
                                                </div>
                                            `).join("")}
                                        </div>
                                    </div>
                                `;
                            }).join("")}
                        </div>
                        <div class="guzheng-jianpu-page-footer">第 ${Number(page?.page_no || 1)} / ${pages.length} 页</div>
                    </section>
                `).join("")}
            </div>
        </article>
    `;
}

function renderTraditionalWarningMarkup(warnings) {
    return warnings.length ? `<div class="analysis-note">${escapeHtmlText(warnings.join("；"))}</div>` : "";
}

function renderTraditionalQuickFacts(model) {
    if (model.instrumentType === "guzheng") {
        const summary = model.result?.pentatonic_summary || {};
        return `
            <div class="traditional-summary-grid">
                <article class="traditional-summary-card">
                    <span class="traditional-summary-label">当前定弦</span>
                    <strong class="traditional-summary-value">${escapeHtmlText(model.result?.instrument_profile?.tuning || "21弦 D调定弦")}</strong>
                    <span class="traditional-summary-copy">正文优先，弦位建议改成辅助层显示，不再抢占主视图。</span>
                </article>
                <article class="traditional-summary-card">
                    <span class="traditional-summary-label">弦位辅助</span>
                    <div class="analysis-chip-row">
                        ${(Array.isArray(model.result?.string_positions) ? model.result.string_positions : [])
                            .slice(0, 8)
                            .map((item) => `<span class="analysis-chip">${escapeHtmlText(item.string_label || "--")} · ${escapeHtmlText(item.degree_display || "--")}</span>`)
                            .join("") || '<span class="analysis-chip">暂无弦位摘要</span>'}
                    </div>
                </article>
                <article class="traditional-summary-card">
                    <span class="traditional-summary-label">五声音阶统计</span>
                    <div class="analysis-chip-row">
                        <span class="analysis-chip">直弹 ${escapeHtmlText(String(summary.direct_open_notes || 0))}</span>
                        <span class="analysis-chip">按音 ${escapeHtmlText(String(summary.press_note_candidates || 0))}</span>
                        <span class="analysis-chip">调外 ${escapeHtmlText(String(summary.non_scale_tone_notes || 0))}</span>
                    </div>
                </article>
            </div>
        `;
    }
    const playability = model.result?.playability_summary || {};
    return `
        <div class="traditional-summary-grid">
            <article class="traditional-summary-card">
                <span class="traditional-summary-label">当前笛型</span>
                <strong class="traditional-summary-value">${escapeHtmlText(localizeFluteType(model.result?.flute_type || "G"))}</strong>
                <span class="traditional-summary-copy">页头和正文都按当前笛型的筒音关系显示，不再以乐句卡片为主阅读。</span>
            </article>
            <article class="traditional-summary-card">
                <span class="traditional-summary-label">常见孔位</span>
                <div class="analysis-chip-row">
                    ${(Array.isArray(model.result?.fingerings) ? model.result.fingerings : [])
                        .slice(0, 8)
                        .map((item) => `<span class="analysis-chip">${escapeHtmlText(item.degree_display || "--")} · ${escapeHtmlText(item.hole_pattern || "--")}</span>`)
                        .join("") || '<span class="analysis-chip">暂无指法摘要</span>'}
                </div>
            </article>
            <article class="traditional-summary-card">
                <span class="traditional-summary-label">可吹性</span>
                <div class="analysis-chip-row">
                    <span class="analysis-chip">可吹 ${escapeHtmlText(String(playability.playable_notes || 0))}</span>
                    <span class="analysis-chip">半孔 ${escapeHtmlText(String(playability.half_hole_candidates || 0))}</span>
                    <span class="analysis-chip">特殊 ${escapeHtmlText(String(playability.special_fingering_candidates || 0))}</span>
                    <span class="analysis-chip">超音域 ${escapeHtmlText(String(playability.out_of_range_notes || 0))}</span>
                </div>
            </article>
        </div>
    `;
}

function renderTraditionalTechniqueSummary(model) {
    const summary = model.result?.technique_summary || {};
    const counts = summary && typeof summary === "object" ? summary.counts || {} : {};
    const entries = Object.entries(counts);
    return `
        <section class="traditional-shell">
            <div class="traditional-shell-head">
                <div>
                    <span class="guzheng-section-kicker">辅助层</span>
                    <h4 class="guzheng-shell-title">${model.instrumentType === "guzheng" ? "弦位 / 按音 / 技法摘要" : "指法 / 技法 / 可吹性摘要"}</h4>
                </div>
            </div>
            ${renderTraditionalQuickFacts(model)}
            <div class="traditional-technique-grid">
                ${entries.map(([label, count]) => metricCard(label, count)).join("") || metricCard("候选技法", 0)}
                ${metricCard("标注总数", summary?.total_tagged_notes || 0)}
            </div>
        </section>
    `;
}

function summarizeGuzhengMeasurePositions(measure) {
    const seen = new Set();
    return (Array.isArray(measure?.notes) ? measure.notes : []).filter((note) => {
        const signature = `${note.position_hint || "--"}::${note.degree_display || "--"}`;
        if (seen.has(signature)) {
            return false;
        }
        seen.add(signature);
        return true;
    });
}

function renderGuzhengStringCards(measures) {
    const items = Array.isArray(measures) ? measures : [];
    if (!items.length) {
        return '<div class="analysis-note">当前还没有弦位建议。</div>';
    }
    return `
        <div class="guzheng-string-grid">
            ${items.map((measure) => {
                const positions = summarizeGuzhengMeasurePositions(measure);
                return `
                    <article class="guzheng-string-card">
                        <div class="guzheng-string-head">
                            <div>
                                <span class="guzheng-section-kicker">按小节查看</span>
                                <strong class="guzheng-section-range">第 ${escapeHtmlText(String(measure.measure_no || "--"))} 小节</strong>
                            </div>
                        </div>
                        <div class="guzheng-string-chip-row">
                            ${positions.map((item) => `
                                <span class="guzheng-string-chip ${item.requires_press ? "requires-press" : ""}">
                                    ${escapeHtmlText(item.position_hint || "--")} · ${escapeHtmlText(item.degree_display || "--")}
                                </span>
                            `).join("") || '<span class="analysis-note">当前小节暂无弦位摘要。</span>'}
                        </div>
                        <p class="guzheng-string-tip">这一小节先稳住主音和节拍，再决定是否加入滑音或按音。</p>
                    </article>
                `;
            }).join("")}
        </div>
    `;
}

function renderGuzhengTechniqueSummary(summary, measures = []) {
    const counts = summary && typeof summary === "object" ? summary.counts || {} : {};
    const entries = Object.entries(counts);
    const measureSuggestions = (Array.isArray(measures) ? measures : [])
        .map((measure) => {
            const tags = Array.from(
                new Set(
                    (Array.isArray(measure.notes) ? measure.notes : []).flatMap((note) => Array.isArray(note.technique_tags) ? note.technique_tags : [])
                )
            );
            return {
                measureNo: measure.measure_no,
                highlights: tags,
                suggestion: tags.length
                    ? "按当前小节的候选标签决定是否加摇指、滑音或按音。"
                    : "当前小节以直弹主旋律为主。",
            };
        })
        .filter((item) => item.highlights.length > 0)
        .slice(0, 12);
    return `
        <div class="guzheng-technique-shell">
            <div class="guzheng-technique-metrics">
                ${entries.map(([label, count]) => metricCard(label, count)).join("") || metricCard("候选技法", 0)}
                ${metricCard("标注总数", summary?.total_tagged_notes || 0)}
            </div>
            <div class="guzheng-technique-suggestions">
                ${measureSuggestions.map((item) => `
                    <article class="guzheng-technique-card">
                        <div class="guzheng-technique-card-head">
                            <strong>第 ${escapeHtmlText(String(item.measureNo || "--"))} 小节</strong>
                            <span class="guzheng-meta-subtle">整曲连续视图中的当前小节提示</span>
                        </div>
                        <p>${escapeHtmlText(item.suggestion || "当前乐句以直弹为主。")}</p>
                        <div class="guzheng-technique-row">${renderGuzhengTechniquePills(item.highlights)}</div>
                    </article>
                `).join("") || '<div class="analysis-note">当前还没有额外技法建议。</div>'}
            </div>
        </div>
    `;
}

function renderGuzhengScorePanel() {
    const guzhengMode = isGuzhengMode();
    const result = state.guzhengResult;
    els.guzhengScoreEmpty.hidden = !guzhengMode || Boolean(result);
    els.guzhengScoreView.hidden = !guzhengMode || !result;
    if (!guzhengMode) {
        els.guzhengScoreView.innerHTML = "";
        return;
    }
    if (!result) {
        return;
    }

    const model = buildTraditionalJianpuSheetModel(result, "guzheng");
    const expectedPreviewSignature = buildTraditionalPreviewSignature("guzheng", result);
    const preview = state.guzhengEngravedPreview?.signature === expectedPreviewSignature ? state.guzhengEngravedPreview : null;
    const markupMode = resolveTraditionalMarkupMode(model.annotationLayer);
    const measures = model.measures;
    const melodyTrackName = result.melody_track?.name || "--";
    const melodyRange = [
        result.pitch_range?.lowest || "",
        result.pitch_range?.highest || "",
    ].filter(Boolean).join(" - ") || "--";
    const pentatonicSummary = result.pentatonic_summary || {};
    const warningMarkup = renderTraditionalWarningMarkup(model.warnings);

    els.guzhengScoreView.innerHTML = `
        <div class="traditional-sheet-stack guzheng-sheet-stack instrument-guzheng ${model.layoutMode === "print" ? "print-mode" : "preview-mode"}">
            <div class="guzheng-sheet-hero traditional-sheet-hero">
                <div>
                    <span class="guzheng-sheet-kicker">LilyPond Engraving</span>
                    <h3 class="guzheng-sheet-title">${escapeHtmlText(model.meta.title)}</h3>
                    <p class="guzheng-sheet-copy">古筝结果页的正文已经切到 jianpu-ly / LilyPond 统一排版。页面本身只负责控制预览、打印模式和辅助摘要，不再自己手工拼正文。</p>
                </div>
                <div class="traditional-sheet-controls">
                    ${renderTraditionalLayoutModeToggle(model.layoutMode)}
                    ${renderTraditionalMarkupModeToggle(model.annotationLayer, "guzheng")}
                    ${markupMode === "annotated" ? renderTraditionalAnnotationLayerToggle(model.annotationLayer, "guzheng") : ""}
                </div>
                <div class="guzheng-sheet-metrics traditional-sheet-metrics">
                    ${metricCard("调号", escapeHtmlText(model.meta.keySignature || "--"))}
                    ${metricCard("速度", model.meta.tempo ? `${model.meta.tempo} BPM` : "--")}
                    ${metricCard("拍号", escapeHtmlText(model.meta.timeSignature || "--"))}
                    ${metricCard("小节", measures.length || 0)}
                    ${metricCard("音符", model.noteCount || 0)}
                    ${metricCard("按音候选", pentatonicSummary.press_note_candidates || 0)}
                </div>
            </div>
            <div class="guzheng-sheet-meta traditional-sheet-meta">
                <div class="guzheng-meta-card">
                    <span class="guzheng-meta-label">定弦</span>
                    <strong class="guzheng-meta-value">${escapeHtmlText(model.meta.instrumentBadge || "21弦 D调定弦")}</strong>
                    <span class="guzheng-meta-subtle">${escapeHtmlText(model.meta.instrumentRange || "--")}</span>
                </div>
                <div class="guzheng-meta-card">
                    <span class="guzheng-meta-label">旋律来源</span>
                    <strong class="guzheng-meta-value">${escapeHtmlText(localizeTrackName(melodyTrackName))}</strong>
                    <span class="guzheng-meta-subtle">${escapeHtmlText(localizePitchSource(result.melody_track?.source || result.pipeline?.pitch_source || "--"))}</span>
                </div>
                <div class="guzheng-meta-card">
                    <span class="guzheng-meta-label">检测音域</span>
                    <strong class="guzheng-meta-value">${escapeHtmlText(melodyRange)}</strong>
                    <span class="guzheng-meta-subtle">当前主旋律估计音域</span>
                </div>
                <div class="guzheng-meta-card">
                    <span class="guzheng-meta-label">五声音阶命中</span>
                    <strong class="guzheng-meta-value">${escapeHtmlText(`${Math.round(Number(pentatonicSummary.direct_ratio || 0) * 100)}%`)}</strong>
                    <span class="guzheng-meta-subtle">直弹 ${escapeHtmlText(String(pentatonicSummary.direct_open_notes || 0))} / 按音 ${escapeHtmlText(String(pentatonicSummary.press_note_candidates || 0))}</span>
                </div>
            </div>
            ${renderTraditionalExportButtons("guzheng")}
            ${warningMarkup}
            <section class="guzheng-shell traditional-shell">
                <div class="guzheng-shell-head">
                    <div>
                        <span class="guzheng-section-kicker">统一排版正文</span>
                        <h4 class="guzheng-shell-title">古筝简谱页面预览</h4>
                    </div>
                </div>
                ${renderTraditionalEngravedPreview(model, preview, "guzheng")}
            </section>
            ${renderTraditionalTechniqueSummary(model)}
        </div>
    `;
}

function localizeFluteType(fluteType) {
    const resolved = resolveDiziFluteType(fluteType);
    return `${resolved} 调笛`;
}

function isCurrentDiziResult(result) {
    if (!result) {
        return false;
    }
    return resolveDiziFluteType(result.flute_type) === resolveDiziFluteType(state.diziFluteType);
}

function renderDiziOctaveMarks(note) {
    const above = Number(note?.octave_marks?.above || 0);
    const below = Number(note?.octave_marks?.below || 0);
    return `
        <span class="dizi-octave dizi-octave-top">${"•".repeat(Math.max(above, 0))}</span>
        <span class="dizi-octave dizi-octave-bottom">${"•".repeat(Math.max(below, 0))}</span>
    `;
}

function renderDiziTechniquePills(tags) {
    const items = Array.isArray(tags) ? tags : [];
    if (!items.length) {
        return '<span class="dizi-technique-pill subtle">平吹为主</span>';
    }
    return items.map((tag) => `<span class="dizi-technique-pill">${escapeHtmlText(tag)}</span>`).join("");
}

function renderDiziPhraseCards(phraseLines) {
    const phrases = Array.isArray(phraseLines) ? phraseLines : [];
    if (!phrases.length) {
        return '<div class="analysis-note">当前还没有可展示的笛子乐句。</div>';
    }
    return phrases.map((phrase) => `
        <section class="dizi-phrase-card">
            <header class="dizi-phrase-head">
                <div>
                    <span class="dizi-section-kicker">${escapeHtmlText(phrase.phrase_label || "乐句")}</span>
                    <strong class="dizi-section-range">第 ${escapeHtmlText(String(phrase.measure_start || "--"))}-${escapeHtmlText(String(phrase.measure_end || "--"))} 小节</strong>
                </div>
                <span class="dizi-section-meta">${escapeHtmlText(String(phrase.measure_count || 0))} 小节 / ${escapeHtmlText(phrase.cadence || "open")}</span>
            </header>
            <div class="dizi-measure-grid">
                ${(Array.isArray(phrase.measures) ? phrase.measures : []).map((measure) => `
                    <article class="dizi-measure-card">
                        <div class="dizi-measure-head">
                            <span class="dizi-measure-index">第 ${escapeHtmlText(String(measure.measure_no || "--"))} 小节</span>
                            <span class="dizi-measure-count">${escapeHtmlText(String(measure.notes?.length || 0))} 音</span>
                        </div>
                        <div class="dizi-note-row">
                            ${(Array.isArray(measure.notes) ? measure.notes : []).map((note) => `
                                <div class="dizi-note-token ${note.out_of_range ? "out-of-range" : ""} ${note.half_hole_candidate ? "half-hole" : ""}">
                                    <div class="dizi-note-jianpu">
                                        ${renderDiziOctaveMarks(note)}
                                        <strong class="dizi-note-degree">${escapeHtmlText(note.degree_display || "--")}</strong>
                                    </div>
                                    <div class="dizi-note-meta">
                                        <span>${escapeHtmlText(note.pitch || "--")}</span>
                                        <span>${escapeHtmlText(note.hole_pattern || "--")} / ${escapeHtmlText(note.register_label || "--")}</span>
                                        <span>${escapeHtmlText(`${formatBeat(note.start_beat || 1)}拍 · ${formatBeat(note.beats || 0)}拍`)}</span>
                                        <span>${escapeHtmlText(note.blow_hint || "--")} / ${escapeHtmlText(note.fingering_hint || "--")}</span>
                                    </div>
                                    <div class="dizi-technique-row">${renderDiziTechniquePills(note.technique_tags)}</div>
                                </div>
                            `).join("") || '<div class="analysis-note">这一小节暂时没有可展示的旋律音。</div>'}
                        </div>
                    </article>
                `).join("")}
            </div>
        </section>
    `).join("");
}

function renderDiziFingeringCards(phraseLines) {
    const phrases = Array.isArray(phraseLines) ? phraseLines : [];
    if (!phrases.length) {
        return '<div class="analysis-note">当前还没有指法建议。</div>';
    }
    return `
        <div class="dizi-fingering-grid">
            ${phrases.map((phrase) => `
                <article class="dizi-fingering-card">
                    <div class="dizi-fingering-head">
                        <div>
                            <span class="dizi-section-kicker">${escapeHtmlText(phrase.phrase_label || "乐句")}</span>
                            <strong class="dizi-section-range">第 ${escapeHtmlText(String(phrase.measure_start || "--"))}-${escapeHtmlText(String(phrase.measure_end || "--"))} 小节</strong>
                        </div>
                    </div>
                    <div class="dizi-fingering-chip-row">
                        ${(Array.isArray(phrase.fingerings) ? phrase.fingerings : []).map((item) => `
                            <span class="dizi-fingering-chip ${item.out_of_range ? "out-of-range" : ""} ${item.half_hole_candidate ? "half-hole" : ""}">
                                ${escapeHtmlText(item.degree_display || "--")} · ${escapeHtmlText(item.hole_pattern || "--")} · ${escapeHtmlText(item.register_label || "--")}
                            </span>
                        `).join("") || '<span class="analysis-note">当前乐句暂无指法摘要。</span>'}
                    </div>
                    <p class="dizi-fingering-tip">${escapeHtmlText(phrase.phrase_tip || "先稳住筒音关系，再根据半孔和特殊指法提示决定是否微调。")}</p>
                </article>
            `).join("")}
        </div>
    `;
}

function renderDiziTechniqueSummary(summary) {
    const counts = summary && typeof summary === "object" ? summary.counts || {} : {};
    const entries = Object.entries(counts);
    const phraseSuggestions = Array.isArray(summary?.phrase_suggestions) ? summary.phrase_suggestions : [];
    return `
        <div class="dizi-technique-shell">
            <div class="dizi-technique-metrics">
                ${entries.map(([label, count]) => metricCard(label, count)).join("") || metricCard("候选技法", 0)}
                ${metricCard("标注总数", summary?.total_tagged_notes || 0)}
            </div>
            <div class="dizi-technique-suggestions">
                ${phraseSuggestions.map((item) => `
                    <article class="dizi-technique-card">
                        <div class="dizi-technique-card-head">
                            <strong>${escapeHtmlText(item.phrase_label || "乐句")}</strong>
                            <span class="dizi-meta-subtle">第 ${escapeHtmlText(String(item.measure_start || "--"))}-${escapeHtmlText(String(item.measure_end || "--"))} 小节</span>
                        </div>
                        <p>${escapeHtmlText(item.suggestion || "当前乐句以主旋律平吹为主。")}</p>
                        <div class="dizi-technique-row">${renderDiziTechniquePills(item.highlights)}</div>
                    </article>
                `).join("") || '<div class="analysis-note">当前还没有额外技法建议。</div>'}
            </div>
        </div>
    `;
}

function renderDiziScorePanel() {
    const diziMode = isDiziMode();
    const result = state.diziResult;
    const isCurrentResult = isCurrentDiziResult(result);
    els.diziScoreEmpty.hidden = !diziMode || isCurrentResult;
    els.diziScoreView.hidden = !diziMode || !isCurrentResult;
    if (!diziMode) {
        els.diziScoreView.innerHTML = "";
        return;
    }
    if (!result) {
        els.diziScoreEmpty.innerHTML = `
            <h3>当前还没有生成笛子谱</h3>
            <p>切换到笛子模式后，系统会基于当前旋律生成笛子简谱，并在这里展示筒音关系、指法/孔位和基础技法建议。</p>
        `;
        return;
    }
    if (!isCurrentResult) {
        if (result && !isCurrentResult) {
            els.diziScoreEmpty.innerHTML = `
                <h3>当前笛型已切换</h3>
                <p>当前选择的是 ${escapeHtmlText(localizeFluteType(state.diziFluteType))}。请重新生成笛子谱，让简谱数字和指法按新的笛型关系重新映射。</p>
            `;
        }
        return;
    }

    const model = buildTraditionalJianpuSheetModel(result, "dizi");
    const expectedPreviewSignature = buildTraditionalPreviewSignature("dizi", result);
    const preview = state.diziEngravedPreview?.signature === expectedPreviewSignature ? state.diziEngravedPreview : null;
    const markupMode = resolveTraditionalMarkupMode(model.annotationLayer);
    const measures = model.measures;
    const melodyTrackName = result.melody_track?.name || "--";
    const melodyRange = [
        result.pitch_range?.lowest || "",
        result.pitch_range?.highest || "",
    ].filter(Boolean).join(" - ") || "--";
    const playabilitySummary = result.playability_summary || {};
    const warningMarkup = renderTraditionalWarningMarkup(model.warnings);

    els.diziScoreView.innerHTML = `
        <div class="traditional-sheet-stack dizi-sheet-stack instrument-dizi ${model.layoutMode === "print" ? "print-mode" : "preview-mode"}">
            <div class="dizi-sheet-hero traditional-sheet-hero">
                <div>
                    <span class="dizi-sheet-kicker">LilyPond Engraving</span>
                    <h3 class="dizi-sheet-title">${escapeHtmlText(model.meta.title)}</h3>
                    <p class="dizi-sheet-copy">笛子结果页的正文已经改成 jianpu-ly / LilyPond 统一排版。页面本身只负责模式切换和辅助摘要，不再自己拼装简谱正文。</p>
                </div>
                <div class="traditional-sheet-controls">
                    ${renderTraditionalLayoutModeToggle(model.layoutMode)}
                    ${renderTraditionalMarkupModeToggle(model.annotationLayer, "dizi")}
                    ${markupMode === "annotated" ? renderTraditionalAnnotationLayerToggle(model.annotationLayer, "dizi") : ""}
                </div>
                <div class="dizi-sheet-metrics traditional-sheet-metrics">
                    ${metricCard("调号", escapeHtmlText(model.meta.keySignature || "--"))}
                    ${metricCard("速度", model.meta.tempo ? `${model.meta.tempo} BPM` : "--")}
                    ${metricCard("拍号", escapeHtmlText(model.meta.timeSignature || "--"))}
                    ${metricCard("小节", measures.length || 0)}
                    ${metricCard("音符", model.noteCount || 0)}
                    ${metricCard("可吹音", playabilitySummary.playable_notes || 0)}
                </div>
            </div>
            <div class="dizi-sheet-meta traditional-sheet-meta">
                <div class="dizi-meta-card">
                    ${renderDiziInlineFluteTypeSelect(model.meta.fluteType || "G")}
                    <span class="dizi-meta-subtle">${escapeHtmlText(model.meta.instrumentRange || "--")}</span>
                </div>
                <div class="dizi-meta-card">
                    <span class="dizi-meta-label">旋律来源</span>
                    <strong class="dizi-meta-value">${escapeHtmlText(localizeTrackName(melodyTrackName))}</strong>
                    <span class="dizi-meta-subtle">${escapeHtmlText(localizePitchSource(result.melody_track?.source || result.pipeline?.pitch_source || "--"))}</span>
                </div>
                <div class="dizi-meta-card">
                    <span class="dizi-meta-label">检测音域</span>
                    <strong class="dizi-meta-value">${escapeHtmlText(melodyRange)}</strong>
                    <span class="dizi-meta-subtle">当前主旋律估计音域</span>
                </div>
                <div class="dizi-meta-card">
                    <span class="dizi-meta-label">可吹性</span>
                    <strong class="dizi-meta-value">${escapeHtmlText(`${Math.round(Number(playabilitySummary.playable_ratio || 0) * 100)}%`)}</strong>
                    <span class="dizi-meta-subtle">半孔 ${escapeHtmlText(String(playabilitySummary.half_hole_candidates || 0))} / 特殊指法 ${escapeHtmlText(String(playabilitySummary.special_fingering_candidates || 0))}</span>
                </div>
            </div>
            ${renderTraditionalExportButtons("dizi")}
            ${warningMarkup}
            <section class="dizi-shell traditional-shell">
                <div class="dizi-shell-head">
                    <div>
                        <span class="dizi-section-kicker">统一排版正文</span>
                        <h4 class="dizi-shell-title">笛子简谱页面预览</h4>
                    </div>
                </div>
                ${renderTraditionalEngravedPreview(model, preview, "dizi")}
            </section>
            ${renderTraditionalTechniqueSummary(model)}
        </div>
    `;
}

function renderGuitarLeadSheetPanel() {
    const guitarMode = isGuitarMode();
    const result = state.guitarLeadSheetResult;
    els.guitarLeadSheetEmpty.hidden = !guitarMode || Boolean(result);
    els.guitarLeadSheetView.hidden = !guitarMode || !result;
    if (!guitarMode) {
        els.guitarLeadSheetView.innerHTML = "";
        return;
    }
    if (!result) {
        return;
    }

    const songSheet = buildGuitarSongSheetModel(result);
    const viewMode = resolveGuitarViewMode(state.guitarViewMode);
    const strummingPattern = songSheet.meta.strumming || {};
    const strummingText = resolveStrummingDisplayPattern(strummingPattern);
    const strummingDescription = strummingPattern.description || "当前会优先用基础扫弦把整首歌扫顺，再把主歌 / 副歌的变化贴到对应段落里。";
    const strummingCounting = strummingPattern.counting || "--";
    const strummingDifficulty = localizeStrummingDifficulty(strummingPattern.difficulty || "--");
    const highlightedChordSymbol = songSheet.chords.some((chord) => chord.symbol === state.guitarHighlightedChordSymbol)
        ? state.guitarHighlightedChordSymbol
        : "";
    if (highlightedChordSymbol !== state.guitarHighlightedChordSymbol) {
        setGuitarHighlightedChordSymbol(highlightedChordSymbol);
    }
    const warningMarkup = songSheet.warnings.length
        ? `<div class="analysis-note">${escapeHtmlText(songSheet.warnings.join("；"))}</div>`
        : "";

    els.guitarLeadSheetView.innerHTML = `
        <div class="guitar-sheet-stack ${viewMode === "print" ? "print-mode" : "screen-mode"}">
            <div class="guitar-sheet-hero">
                <div class="guitar-sheet-hero-main">
                    <div class="guitar-sheet-headline">
                        <div>
                            <span class="guitar-sheet-kicker">Guitar Lead Sheet</span>
                            <h3 class="guitar-sheet-title">${escapeHtmlText(songSheet.meta.title)}</h3>
                            <p class="guitar-sheet-copy">${escapeHtmlText(songSheet.meta.artist || songSheet.meta.subtitle)}</p>
                        </div>
                        <div class="guitar-sheet-actions">
                            ${renderGuitarViewModeToggle(viewMode)}
                            ${renderGuitarExportButton()}
                        </div>
                    </div>
                    <div class="guitar-sheet-metrics">
                        ${metricCard("调号", escapeHtmlText(songSheet.meta.key))}
                        ${metricCard("Capo", escapeHtmlText(songSheet.meta.capoText))}
                        ${metricCard("拍号", escapeHtmlText(songSheet.meta.timeSignature))}
                        ${metricCard("速度", songSheet.meta.tempo ? `${songSheet.meta.tempo} BPM` : "--")}
                        ${metricCard("小节", songSheet.measures.length || 0)}
                        ${metricCard("旋律来源", escapeHtmlText(localizeTrackName(songSheet.meta.melodyTrackName)))}
                    </div>
                    <div class="guitar-sheet-meta">
                        <div class="guitar-meta-card">
                            <span class="guitar-meta-label">推荐扫弦</span>
                            <strong class="guitar-meta-value guitar-arrow-pattern">${escapeHtmlText(strummingText)}</strong>
                            <span class="guitar-meta-subtle">${escapeHtmlText(strummingDescription)}</span>
                        </div>
                        <div class="guitar-meta-card">
                            <span class="guitar-meta-label">节奏口令</span>
                            <strong class="guitar-meta-value">${escapeHtmlText(strummingCounting)}</strong>
                            <span class="guitar-meta-subtle">默认收进折叠说明里，避免正文一开始就被信息卡打散。</span>
                        </div>
                        <div class="guitar-meta-card">
                            <span class="guitar-meta-label">常用调位</span>
                            <strong class="guitar-meta-value">${escapeHtmlText(songSheet.meta.transposedKey)}</strong>
                            <span class="guitar-meta-subtle">当前 Capo 方案下更顺手的开放和弦调位。</span>
                        </div>
                        <div class="guitar-meta-card">
                            <span class="guitar-meta-label">识别质量</span>
                            <strong class="guitar-meta-value">${escapeHtmlText(songSheet.meta.melodyTrackQuality)}</strong>
                            <span class="guitar-meta-subtle">${escapeHtmlText(localizePitchSource(songSheet.meta.melodyTrackSource))}</span>
                        </div>
                    </div>
                </div>
                <aside class="guitar-global-strumming-card">
                    <span class="guitar-sheet-kicker">Strumming Guide</span>
                    <h4 class="guitar-global-strumming-title">基础推荐扫弦卡</h4>
                    <div class="guitar-global-strumming-pattern">${escapeHtmlText(strummingText)}</div>
                    <p class="guitar-sheet-copy">${escapeHtmlText(strummingDescription)}</p>
                    <div class="analysis-chip-row">
                        <span class="analysis-chip">难度 ${escapeHtmlText(strummingDifficulty)}</span>
                        <span class="analysis-chip">拍型 ${escapeHtmlText(songSheet.meta.timeSignature)}</span>
                        <span class="analysis-chip">风格 ${escapeHtmlText(songSheet.meta.style)}</span>
                    </div>
                    <details class="guitar-strumming-details">
                        <summary>展开节拍口令可视化</summary>
                        <div class="guitar-strumming-details-body">
                            ${renderStrummingStrokeGrid(strummingPattern)}
                        </div>
                    </details>
                </aside>
            </div>
            ${warningMarkup}
            <div class="guitar-lead-layout">
                <div class="guitar-lead-main">
                    <section class="guitar-lead-body">
                        <div class="guitar-lead-body-head">
                            <div>
                                <span class="guitar-sheet-kicker">Lead Sheet Body</span>
                                <h4 class="guitar-lead-body-title">弹唱谱正文</h4>
                            </div>
                            <span class="guitar-meta-subtle">${viewMode === "print" ? "打印模式会收紧边栏并按更稳的版式分页。" : "屏幕模式允许局部横向滚动，优先保证和弦与占位歌词不重叠。"}</span>
                        </div>
                        <div class="guitar-lead-sections">
                            ${songSheet.sections.map((section) => renderGuitarLeadSection(section, { highlightedChordSymbol })).join("") || '<div class="analysis-note">当前还没有可展示的弹唱谱正文。</div>'}
                        </div>
                    </section>
                    ${renderGuitarAuxBlocks(songSheet, result)}
                </div>
                ${renderGuitarChordRail(songSheet.visibleDiagrams, songSheet.diagrams.length, highlightedChordSymbol)}
            </div>
        </div>
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

function buildGrandStaffAttributeSnapshot(partEl) {
    const measureElements = getNamedChildren(partEl, "measure");
    const firstAttributes = getFirstNamedChild(measureElements[0], "attributes");
    return {
        divisions: descendantText(firstAttributes, "divisions", "8"),
        keyEl: getFirstNamedChild(firstAttributes, "key")?.cloneNode(true) || null,
        timeEl: getFirstNamedChild(firstAttributes, "time")?.cloneNode(true) || null,
    };
}

function upsertGrandStaffAttributes(
    measureEl,
    snapshot,
    {
        includeBrace = false,
        includeDivisions = false,
        includeKey = true,
        includeTime = true,
    } = {},
) {
    let attributesEl = getFirstNamedChild(measureEl, "attributes");
    if (!attributesEl) {
        attributesEl = measureEl.ownerDocument.createElement("attributes");
        measureEl.insertBefore(attributesEl, measureEl.firstChild);
    }

    Array.from(attributesEl.children).forEach((child) => child.remove());

    if (includeDivisions && snapshot?.divisions) {
        attributesEl.appendChild(createXmlChild(attributesEl.ownerDocument, "divisions", snapshot.divisions));
    }
    if (includeKey && snapshot?.keyEl) {
        attributesEl.appendChild(snapshot.keyEl.cloneNode(true));
    }
    if (includeTime && snapshot?.timeEl) {
        attributesEl.appendChild(snapshot.timeEl.cloneNode(true));
    }
    setNamedChildText(attributesEl, "staves", "2");

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

function removeRedundantDisplayAttributes(measureEl) {
    const attributesEl = getFirstNamedChild(measureEl, "attributes");
    if (!attributesEl) {
        return;
    }
    attributesEl.remove();
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

function applyGrandStaffDisplayTransform(partEl, pagination) {
    const measureElements = getNamedChildren(partEl, "measure");
    const attributeSnapshot = buildGrandStaffAttributeSnapshot(partEl);
    const systemStarts = new Set((pagination?.systems || []).map((system) => system.measureIndices[0]).filter((value) => value >= 0));
    systemStarts.add(0);
    const noteEntries = [];

    measureElements.forEach((measureEl, measureIndex) => {
        if (systemStarts.has(measureIndex)) {
            upsertGrandStaffAttributes(measureEl, attributeSnapshot, {
                includeBrace: measureIndex === 0,
                includeDivisions: measureIndex === 0,
                includeKey: true,
                includeTime: true,
            });
        } else {
            removeRedundantDisplayAttributes(measureEl);
        }
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
            applyGrandStaffDisplayTransform(primaryPart, layout);
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
    const guitarMode = isGuitarMode();
    const guzhengMode = isGuzhengMode();
    const diziMode = isDiziMode();
    const activeDiziResult = isCurrentDiziResult(state.diziResult) ? state.diziResult : null;
    const score = guitarMode
        ? state.guitarLeadSheetResult
        : guzhengMode
            ? state.guzhengResult
            : diziMode
                ? activeDiziResult
                : state.currentScore;
    els.scoreLinkageStatus.textContent = score ? "已连接" : "未连接";
    els.scoreTitleDisplay.textContent = score
        ? score.title || "未命名乐谱"
        : guitarMode
            ? "尚未生成吉他弹唱谱"
            : guzhengMode
                ? "尚未生成古筝谱"
                : diziMode
                    ? "尚未生成笛子谱"
                : "尚未载入乐谱";
    els.scoreIdBadge.textContent = isPianoMode() && score ? score.score_id : "--";
    els.projectIdBadge.textContent = isPianoMode() && score ? score.project_id : "--";
    els.scoreVersionBadge.textContent = isPianoMode() && score ? score.version : "--";
    els.tempoDisplay.textContent = score ? score.tempo : "--";
    els.timeDisplay.textContent = score ? score.time_signature : "--";
    els.keyDisplay.textContent = score ? score.key || score.key_signature || "--" : "--";
    els.measureCountDisplay.textContent = isPianoMode()
        ? score
            ? resolveMeasureCount(score)
            : "--"
        : (Array.isArray(score?.measures) ? score.measures.length : "--");
    els.selectedNoteSummary.textContent = isPianoMode()
        ? state.selectedNotationElementId
            ? "当前已在谱面中高亮一个音符或休止符。若需修改，请在下方 MusicXML 中编辑后保存。"
            : defaultSelectionHint()
        : guzhengMode
            ? "当前页面显示古筝专属结果页。若需刷新简谱、弦位或技法建议，请重新生成古筝谱。"
            : diziMode
                ? "当前页面显示笛子专属结果页。若需刷新简谱、指法或技法建议，请重新生成笛子谱。"
            : "当前页面显示吉他专属结果页。若需刷新弹唱谱信息，请重新生成吉他弹唱谱。";
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

function localizeKeyMode(mode) {
    const normalized = String(mode || "").toLowerCase();
    if (normalized === "major") {
        return "大调";
    }
    if (normalized === "minor") {
        return "小调";
    }
    return mode || "--";
}

function formatFifthsText(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
        return "--";
    }
    if (numeric === 0) {
        return "无升降";
    }
    return numeric > 0 ? `${numeric} 个升号` : `${Math.abs(numeric)} 个降号`;
}

function localizeChordSource(source) {
    const normalized = String(source || "diatonic").toLowerCase();
    const labels = {
        diatonic: "调内和弦",
        secondary_dominant: "副属和弦",
        borrowed: "借和弦",
    };
    return labels[normalized] || source || "--";
}

function localizePitchSource(source) {
    const normalized = String(source || "").toLowerCase();
    if (normalized === "separated_track") {
        return "分离轨优先";
    }
    if (normalized === "mixed_audio_fallback") {
        return "混音回退";
    }
    return source || "--";
}

function summarizeChordSources(chords) {
    const counts = new Map();
    (Array.isArray(chords) ? chords : []).forEach((chord) => {
        const source = String(chord?.source || "diatonic");
        counts.set(source, (counts.get(source) || 0) + 1);
    });
    return Array.from(counts.entries())
        .map(([source, count]) => ({ source, count }))
        .sort((left, right) => right.count - left.count);
}

function renderAnalysisOutputs() {
    const guitarMode = isGuitarMode();
    const guzhengMode = isGuzhengMode();
    const diziMode = isDiziMode();
    els.pianoAnalysisGrid.hidden = guitarMode || guzhengMode || diziMode;
    els.guzhengDebugPanel.hidden = !guzhengMode;
    els.guitarDebugPanel.hidden = !guitarMode;
    els.diziDebugPanel.hidden = !diziMode;
    if (guitarMode) {
        renderGuitarDebugPanel();
        return;
    }
    if (guzhengMode) {
        renderGuzhengDebugPanel();
        return;
    }
    if (diziMode) {
        renderDiziDebugPanel();
        return;
    }
    renderBeatDetectPanel();
    renderSeparateTracksPanel();
    renderChordGenerationPanel();
    renderRhythmScorePanel();
}

function renderGuzhengDebugPanel() {
    const result = state.guzhengResult;
    if (!result) {
        els.guzhengDebugPanel.innerHTML = `
            <div class="guitar-debug-shell">
                <div class="analysis-note">
                    切换到古筝模式后，上传样例音频并点击“识别并生成古筝谱”，这里会集中展示分离轨、定调结果、五声音阶命中和技法候选。
                </div>
            </div>
        `;
        return;
    }

    const separation = result.separation || state.separateTracksResult || null;
    const tracks = Array.isArray(separation?.tracks) ? separation.tracks : [];
    const selectedTrack = result.melody_track || null;
    const keyDetection = result.key_detection || null;
    const warnings = Array.isArray(result.warnings) ? result.warnings : [];
    const trackCandidates = Array.isArray(result.melody_track_candidates) ? result.melody_track_candidates : [];
    const trackCandidateMap = new Map(trackCandidates.map((candidate) => [String(candidate.name || "").toLowerCase(), candidate]));
    const selectedTrackName = String(selectedTrack?.name || "").toLowerCase();
    const techniqueCounts = result.technique_summary?.counts || {};
    const pentatonicSummary = result.pentatonic_summary || {};
    const keyCandidates = Array.isArray(keyDetection?.candidates) ? keyDetection.candidates : [];

    const trackMarkup = tracks.length
        ? tracks.map((track) => {
            const normalizedName = String(track.name || "").toLowerCase();
            const candidate = trackCandidateMap.get(normalizedName) || null;
            return `
                <div class="analysis-item">
                    <div>
                        <div class="analysis-item-title">${escapeHtmlText(localizeTrackName(track.name || "other"))}</div>
                        <div class="analysis-item-meta">${escapeHtmlText([
                            track.file_name || "",
                            Number.isFinite(Number(track.duration)) ? formatSeconds(track.duration) : "",
                        ].filter(Boolean).join(" / ") || "暂无文件信息")}</div>
                    </div>
                    <div class="analysis-item-value">${escapeHtmlText([
                        normalizedName === selectedTrackName ? "已选主旋律" : "",
                        candidate && Number.isFinite(Number(candidate.selection_score)) ? `评分 ${Number(candidate.selection_score).toFixed(2)}` : "",
                        candidate && Number.isFinite(Number(candidate.average_confidence)) ? `置信 ${Math.round(Number(candidate.average_confidence) * 100)}%` : "",
                    ].filter(Boolean).join(" / ") || "待评估")}</div>
                </div>
            `;
        }).join("")
        : '<div class="analysis-note">当前没有分离轨明细，可能走了混音回退。</div>';

    const candidateMarkup = keyCandidates.length
        ? `
            <div class="analysis-list">
                ${keyCandidates.slice(0, 3).map((candidate) => `
                    <div class="analysis-item">
                        <div>
                            <div class="analysis-item-title">${escapeHtmlText(candidate.key_signature || "--")}</div>
                            <div class="analysis-item-meta">${escapeHtmlText(localizeKeyMode(candidate.mode || "--"))} / ${escapeHtmlText(formatFifthsText(candidate.fifths))}</div>
                        </div>
                        <div class="analysis-item-value">${escapeHtmlText(Number.isFinite(Number(candidate.confidence)) ? `${Math.round(Number(candidate.confidence) * 100)}%` : "--")}</div>
                    </div>
                `).join("")}
            </div>
        `
        : '<div class="analysis-note">当前没有更多候选调号。</div>';

    const techniqueMarkup = Object.entries(techniqueCounts).length
        ? `
            <div class="analysis-list">
                ${Object.entries(techniqueCounts).map(([label, count]) => `
                    <div class="analysis-item">
                        <div class="analysis-item-title">${escapeHtmlText(label)}</div>
                        <div class="analysis-item-value">${escapeHtmlText(String(count))}</div>
                    </div>
                `).join("")}
            </div>
        `
        : '<div class="analysis-note">当前旋律还没有额外的技法候选。</div>';

    const warningMarkup = warnings.length
        ? `<div class="analysis-note">${escapeHtmlText(warnings.join("；"))}</div>`
        : '<div class="analysis-note">当前流程没有额外告警。</div>';

    const summaryMarkup = `
        <div class="guitar-debug-summary">
            <span class="guitar-debug-summary-title">古筝识谱流程摘要</span>
            <p class="helper-text">当前会先做分离、测速、定调，再映射到五声音阶与古筝标注层。正文优先展示，技术过程默认收起，需要时再展开排查。</p>
            <div class="analysis-metric-grid">
                ${metricCard("分离状态", separation ? localizeTaskStatus(separation.status || "--") : "混音回退")}
                ${metricCard("最终旋律", localizeTrackName(selectedTrack?.name || "mix"))}
                ${metricCard("检测调号", result.key || keyDetection?.key_signature || "--")}
                ${metricCard("速度", result.tempo ? `${result.tempo} BPM` : "--")}
                ${metricCard("直弹音", pentatonicSummary.direct_open_notes || 0)}
                ${metricCard("按音候选", pentatonicSummary.press_note_candidates || 0)}
            </div>
            <button class="ghost-button guitar-debug-toggle-btn" data-guzheng-toggle-debug type="button">${state.guzhengDebugExpanded ? "收起识谱过程" : "展开识谱过程"}</button>
        </div>
    `;

    if (!state.guzhengDebugExpanded) {
        els.guzhengDebugPanel.innerHTML = `<div class="guitar-debug-shell">${summaryMarkup}</div>`;
        return;
    }

    els.guzhengDebugPanel.innerHTML = `
        <div class="guitar-debug-shell">
            ${summaryMarkup}
            <div class="analysis-grid">
                <div class="analysis-card">
                    <h3>分离轨与选轨</h3>
                    <div class="analysis-output">
                        ${trackMarkup}
                    </div>
                </div>
                <div class="analysis-card">
                    <h3>测速与定调</h3>
                    <div class="analysis-output">
                        <div class="analysis-metric-grid">
                            ${metricCard("检测 BPM", result.tempo_detection?.detected_tempo || "--")}
                            ${metricCard("采用 BPM", result.tempo_detection?.resolved_tempo || result.tempo || "--")}
                            ${metricCard("测速置信度", Number.isFinite(Number(result.tempo_detection?.confidence)) ? `${Math.round(Number(result.tempo_detection.confidence) * 100)}%` : "--")}
                            ${metricCard("拍点数", result.tempo_detection?.beat_count || 0)}
                            ${metricCard("模式", localizeKeyMode(keyDetection?.mode || "--"))}
                            ${metricCard("固定升降", formatFifthsText(keyDetection?.fifths))}
                        </div>
                        ${candidateMarkup}
                    </div>
                </div>
                <div class="analysis-card">
                    <h3>五声音阶统计</h3>
                    <div class="analysis-output">
                        <div class="analysis-metric-grid">
                            ${metricCard("直弹音", pentatonicSummary.direct_open_notes || 0)}
                            ${metricCard("按音候选", pentatonicSummary.press_note_candidates || 0)}
                            ${metricCard("调内音", pentatonicSummary.scale_tone_notes || 0)}
                            ${metricCard("调外音", pentatonicSummary.non_scale_tone_notes || 0)}
                            ${metricCard("直弹比例", `${Math.round(Number(pentatonicSummary.direct_ratio || 0) * 100)}%`)}
                            ${metricCard("旋律来源", localizePitchSource(selectedTrack?.source || result.pipeline?.pitch_source || "--"))}
                        </div>
                    </div>
                </div>
                <div class="analysis-card">
                    <h3>技法候选与提示</h3>
                    <div class="analysis-output">
                        ${techniqueMarkup}
                        ${warningMarkup}
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderDiziDebugPanel() {
    const result = state.diziResult;
    const isCurrentResult = isCurrentDiziResult(result);
    if (!result || !isCurrentResult) {
        const tip = result && !isCurrentResult
            ? `当前已切到 ${localizeFluteType(state.diziFluteType)}，请重新生成笛子谱，让指法和数字谱按新的笛型关系重算。`
            : "切换到笛子模式后，上传样例音频并点击“识别并生成笛子谱”，这里会集中展示分离轨、定调结果、笛型可吹性统计与指法候选。";
        els.diziDebugPanel.innerHTML = `
            <div class="guitar-debug-shell">
                <div class="analysis-note">${escapeHtmlText(tip)}</div>
            </div>
        `;
        return;
    }

    const separation = result.separation || state.separateTracksResult || null;
    const tracks = Array.isArray(separation?.tracks) ? separation.tracks : [];
    const selectedTrack = result.melody_track || null;
    const keyDetection = result.key_detection || null;
    const warnings = Array.isArray(result.warnings) ? result.warnings : [];
    const trackCandidates = Array.isArray(result.melody_track_candidates) ? result.melody_track_candidates : [];
    const trackCandidateMap = new Map(trackCandidates.map((candidate) => [String(candidate.name || "").toLowerCase(), candidate]));
    const selectedTrackName = String(selectedTrack?.name || "").toLowerCase();
    const techniqueCounts = result.technique_summary?.counts || {};
    const playabilitySummary = result.playability_summary || {};
    const keyCandidates = Array.isArray(keyDetection?.candidates) ? keyDetection.candidates : [];

    const trackMarkup = tracks.length
        ? tracks.map((track) => {
            const normalizedName = String(track.name || "").toLowerCase();
            const candidate = trackCandidateMap.get(normalizedName) || null;
            return `
                <div class="analysis-item">
                    <div>
                        <div class="analysis-item-title">${escapeHtmlText(localizeTrackName(track.name || "other"))}</div>
                        <div class="analysis-item-meta">${escapeHtmlText([
                            track.file_name || "",
                            Number.isFinite(Number(track.duration)) ? formatSeconds(track.duration) : "",
                        ].filter(Boolean).join(" / ") || "暂无文件信息")}</div>
                    </div>
                    <div class="analysis-item-value">${escapeHtmlText([
                        normalizedName === selectedTrackName ? "已选主旋律" : "",
                        candidate && Number.isFinite(Number(candidate.selection_score)) ? `评分 ${Number(candidate.selection_score).toFixed(2)}` : "",
                        candidate && Number.isFinite(Number(candidate.average_confidence)) ? `置信 ${Math.round(Number(candidate.average_confidence) * 100)}%` : "",
                    ].filter(Boolean).join(" / ") || "待评估")}</div>
                </div>
            `;
        }).join("")
        : '<div class="analysis-note">当前没有分离轨明细，可能走了混音回退。</div>';

    const candidateMarkup = keyCandidates.length
        ? `
            <div class="analysis-list">
                ${keyCandidates.slice(0, 3).map((candidate) => `
                    <div class="analysis-item">
                        <div>
                            <div class="analysis-item-title">${escapeHtmlText(candidate.key_signature || "--")}</div>
                            <div class="analysis-item-meta">${escapeHtmlText(localizeKeyMode(candidate.mode || "--"))} / ${escapeHtmlText(formatFifthsText(candidate.fifths))}</div>
                        </div>
                        <div class="analysis-item-value">${escapeHtmlText(Number.isFinite(Number(candidate.confidence)) ? `${Math.round(Number(candidate.confidence) * 100)}%` : "--")}</div>
                    </div>
                `).join("")}
            </div>
        `
        : '<div class="analysis-note">当前没有更多候选调号。</div>';

    const techniqueMarkup = Object.entries(techniqueCounts).length
        ? `
            <div class="analysis-list">
                ${Object.entries(techniqueCounts).map(([label, count]) => `
                    <div class="analysis-item">
                        <div class="analysis-item-title">${escapeHtmlText(label)}</div>
                        <div class="analysis-item-value">${escapeHtmlText(String(count))}</div>
                    </div>
                `).join("")}
            </div>
        `
        : '<div class="analysis-note">当前旋律还没有额外的技法候选。</div>';

    const warningMarkup = warnings.length
        ? `<div class="analysis-note">${escapeHtmlText(warnings.join("；"))}</div>`
        : '<div class="analysis-note">当前流程没有额外告警。</div>';

    const summaryMarkup = `
        <div class="guitar-debug-summary">
            <span class="guitar-debug-summary-title">笛子识谱流程摘要</span>
            <p class="helper-text">当前会先做分离、测速、定调，再按所选笛型映射筒音关系和指法层。正文优先展示，识谱过程默认收起。</p>
            <div class="analysis-metric-grid">
                ${metricCard("分离状态", separation ? localizeTaskStatus(separation.status || "--") : "混音回退")}
                ${metricCard("最终旋律", localizeTrackName(selectedTrack?.name || "mix"))}
                ${metricCard("检测调号", result.key || keyDetection?.key_signature || "--")}
                ${metricCard("笛型", localizeFluteType(result.flute_type || "G"))}
                ${metricCard("速度", result.tempo ? `${result.tempo} BPM` : "--")}
                ${metricCard("可吹音", playabilitySummary.playable_notes || 0)}
            </div>
            <button class="ghost-button guitar-debug-toggle-btn" data-dizi-toggle-debug type="button">${state.diziDebugExpanded ? "收起识谱过程" : "展开识谱过程"}</button>
        </div>
    `;

    if (!state.diziDebugExpanded) {
        els.diziDebugPanel.innerHTML = `<div class="guitar-debug-shell">${summaryMarkup}</div>`;
        return;
    }

    els.diziDebugPanel.innerHTML = `
        <div class="guitar-debug-shell">
            ${summaryMarkup}
            <div class="analysis-grid">
                <div class="analysis-card">
                    <h3>分离轨与选轨</h3>
                    <div class="analysis-output">
                        ${trackMarkup}
                    </div>
                </div>
                <div class="analysis-card">
                    <h3>测速与定调</h3>
                    <div class="analysis-output">
                        <div class="analysis-metric-grid">
                            ${metricCard("检测 BPM", result.tempo_detection?.detected_tempo || "--")}
                            ${metricCard("采用 BPM", result.tempo_detection?.resolved_tempo || result.tempo || "--")}
                            ${metricCard("测速置信度", Number.isFinite(Number(result.tempo_detection?.confidence)) ? `${Math.round(Number(result.tempo_detection.confidence) * 100)}%` : "--")}
                            ${metricCard("拍点数", result.tempo_detection?.beat_count || 0)}
                            ${metricCard("模式", localizeKeyMode(keyDetection?.mode || "--"))}
                            ${metricCard("固定升降", formatFifthsText(keyDetection?.fifths))}
                        </div>
                        ${candidateMarkup}
                    </div>
                </div>
                <div class="analysis-card">
                    <h3>笛型可吹性</h3>
                    <div class="analysis-output">
                        <div class="analysis-metric-grid">
                            ${metricCard("笛型", localizeFluteType(result.flute_type || "G"))}
                            ${metricCard("建议音域", result.instrument_profile?.range || "--")}
                            ${metricCard("可吹音", playabilitySummary.playable_notes || 0)}
                            ${metricCard("超音域", playabilitySummary.out_of_range_notes || 0)}
                            ${metricCard("半孔候选", playabilitySummary.half_hole_candidates || 0)}
                            ${metricCard("特殊指法", playabilitySummary.special_fingering_candidates || 0)}
                        </div>
                    </div>
                </div>
                <div class="analysis-card">
                    <h3>技法候选与提示</h3>
                    <div class="analysis-output">
                        ${techniqueMarkup}
                        ${warningMarkup}
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderGuitarDebugPanel() {
    const result = state.guitarLeadSheetResult;
    if (!result) {
        els.guitarDebugPanel.innerHTML = `
            <div class="guitar-debug-shell">
                <div class="analysis-note">
                    切换到吉他模式后，上传样例音频并点击“识别并生成吉他弹唱谱”，这里会集中展示分离轨、定调结果、和弦来源和流程提示。
                </div>
            </div>
        `;
        return;
    }

    const separation = result.separation || state.separateTracksResult || null;
    const tracks = Array.isArray(separation?.tracks) ? separation.tracks : [];
    const selectedTrack = result.melody_track || null;
    const keyDetection = result.key_detection || null;
    const chords = Array.isArray(result.chords) ? result.chords : [];
    const warnings = Array.isArray(result.warnings) ? result.warnings : [];
    const sourceSummary = summarizeChordSources(chords);
    const trackCandidates = Array.isArray(result.melody_track_candidates) ? result.melody_track_candidates : [];
    const trackCandidateMap = new Map(
        trackCandidates.map((candidate) => [String(candidate.name || "").toLowerCase(), candidate])
    );
    const selectedTrackName = String(selectedTrack?.name || "").toLowerCase();
    const keyCandidates = Array.isArray(keyDetection?.candidates) ? keyDetection.candidates : [];
    const harmonicStrategy = result.harmonic_strategy || {};
    const harmonicSummary = [
        harmonicStrategy.secondary_dominants_enabled ? "副属" : "",
        harmonicStrategy.borrowed_chords_enabled ? "借和弦" : "",
        harmonicStrategy.segment_smoothing_enabled ? "段落平滑" : "",
    ].filter(Boolean);

    const trackMarkup = tracks.length
        ? tracks.map((track) => {
            const normalizedName = String(track.name || "").toLowerCase();
            const candidate = trackCandidateMap.get(normalizedName) || null;
            const itemMeta = [
                track.file_name || "",
                Number.isFinite(Number(track.duration)) ? formatSeconds(track.duration) : "",
            ].filter(Boolean).join(" / ");
            const itemValue = [
                normalizedName === selectedTrackName ? "已选主旋律" : "",
                candidate && Number.isFinite(Number(candidate.selection_score))
                    ? `评分 ${Number(candidate.selection_score).toFixed(2)}`
                    : "",
                candidate && Number.isFinite(Number(candidate.average_confidence))
                    ? `置信 ${Math.round(Number(candidate.average_confidence) * 100)}%`
                    : "",
            ].filter(Boolean).join(" / ");
            return `
                <div class="analysis-item">
                    <div>
                        <div class="analysis-item-title">${escapeHtmlText(localizeTrackName(track.name || "other"))}</div>
                        <div class="analysis-item-meta">${escapeHtmlText(itemMeta || "暂无文件信息")}</div>
                    </div>
                    <div class="analysis-item-value">${escapeHtmlText(itemValue || "待评估")}</div>
                </div>
            `;
        }).join("")
        : '<div class="analysis-note">当前没有可展示的分离轨信息，可能走了混音回退。</div>';

    const sourceMarkup = sourceSummary.length
        ? sourceSummary.map((item) => `
            <div class="analysis-item">
                <div>
                    <div class="analysis-item-title">${escapeHtmlText(localizeChordSource(item.source))}</div>
                    <div class="analysis-item-meta">${escapeHtmlText(String(item.source))}</div>
                </div>
                <div class="analysis-item-value">${escapeHtmlText(String(item.count))} 个</div>
            </div>
        `).join("")
        : '<div class="analysis-note">当前还没有和弦来源可供统计。</div>';

    const candidateMarkup = keyCandidates.length
        ? keyCandidates.map((candidate) => `
            <span class="analysis-chip">
                ${escapeHtmlText(candidate.key_signature || "--")} · ${escapeHtmlText(localizeKeyMode(candidate.mode || ""))} · ${escapeHtmlText(Number(candidate.score || 0).toFixed(2))}
            </span>
        `).join("")
        : '<span class="analysis-chip">暂无候选调号</span>';

    const chordPreviewMarkup = chords.length
        ? chords.slice(0, 10).map((chord) => `
            <span class="analysis-chip">
                ${escapeHtmlText(chord.symbol || "--")} · ${escapeHtmlText(localizeChordSource(chord.source || "diatonic"))}
            </span>
        `).join("")
        : '<span class="analysis-chip">暂无和弦</span>';

    const warningMarkup = warnings.length
        ? `<div class="analysis-note">${escapeHtmlText(warnings.join("；"))}</div>`
        : '<div class="analysis-note">当前没有额外告警，流程已按分离轨 -> 定调 -> 和弦推断完成返回。</div>';

    const summaryMarkup = `
        <div class="guitar-debug-summary">
            <div class="guitar-debug-summary-copy">
                <p class="analysis-subtitle">Sample Audio Debug</p>
                <strong class="guitar-debug-summary-title">吉他识谱过程已下沉到这里</strong>
                <p class="helper-text">第一页优先展示可弹可唱的正文。需要排查识谱链路时，再展开查看分离轨、定调候选、和弦来源和流程提示。</p>
            </div>
            <div class="analysis-chip-row">
                <span class="analysis-chip">旋律来源 ${escapeHtmlText(localizeTrackName(selectedTrack?.name || "mix"))}</span>
                <span class="analysis-chip">识别调号 ${escapeHtmlText(result.key || keyDetection?.key_signature || "--")}</span>
                <span class="analysis-chip">和弦 ${escapeHtmlText(String(chords.length))} 个</span>
                <span class="analysis-chip">小节 ${escapeHtmlText(String((result.measures || []).length || 0))} 个</span>
            </div>
            <button class="ghost-button guitar-debug-toggle-btn" data-guitar-toggle-debug type="button">${state.guitarDebugExpanded ? "收起识谱过程" : "展开识谱过程"}</button>
        </div>
    `;

    if (!state.guitarDebugExpanded) {
        els.guitarDebugPanel.innerHTML = `
            <div class="guitar-debug-shell">
                ${summaryMarkup}
                <div class="analysis-note">当前默认收起详细调试结果，避免和吉他弹唱谱正文同时争抢视线。</div>
            </div>
        `;
        return;
    }

    els.guitarDebugPanel.innerHTML = `
        <div class="guitar-debug-shell">
            ${summaryMarkup}
            <div class="analysis-grid guitar-debug-grid">
                <section class="analysis-card">
                    <h3>分离轨与主旋律</h3>
                    <div class="analysis-stack analysis-tone-orange">
                        <div class="analysis-metrics">
                            ${metricCard("分离状态", separation ? localizeTaskStatus(separation.status || "--") : "混音回退")}
                            ${metricCard("分离模型", separation?.model || result.pipeline?.separation_model || "--")}
                            ${metricCard("候选轨数", tracks.length || trackCandidates.length || 0)}
                            ${metricCard("最终旋律", localizeTrackName(selectedTrack?.name || "mix"))}
                        </div>
                        <div class="analysis-list">
                            ${trackMarkup}
                        </div>
                    </div>
                </section>
                <section class="analysis-card">
                    <h3>定调结果</h3>
                    <div class="analysis-stack analysis-tone-blue">
                        <div class="analysis-metrics">
                            ${metricCard("识别调号", result.key || keyDetection?.key_signature || "--")}
                            ${metricCard("主音", keyDetection?.tonic || "--")}
                            ${metricCard("模式", localizeKeyMode(keyDetection?.mode || "--"))}
                            ${metricCard("固定升降", formatFifthsText(keyDetection?.fifths))}
                            ${metricCard("置信度", Number.isFinite(Number(keyDetection?.confidence)) ? `${Math.round(Number(keyDetection.confidence) * 100)}%` : "--")}
                            ${metricCard("旋律来源", localizePitchSource(selectedTrack?.source || result.pipeline?.pitch_source || "--"))}
                        </div>
                        <p class="analysis-subtitle">候选调号</p>
                        <div class="analysis-chip-row">
                            ${candidateMarkup}
                        </div>
                    </div>
                </section>
                <section class="analysis-card">
                    <h3>和弦来源</h3>
                    <div class="analysis-stack analysis-tone-green">
                        <div class="analysis-metrics">
                            ${metricCard("和弦总数", chords.length || 0)}
                            ${metricCard("来源类型", sourceSummary.length || 0)}
                            ${metricCard("Capo", Number.isFinite(Number(result.capo_suggestion?.capo)) ? result.capo_suggestion.capo : "--")}
                            ${metricCard("扫弦型", resolveStrummingDisplayPattern(result.strumming_pattern))}
                        </div>
                        <div class="analysis-list">
                            ${sourceMarkup}
                        </div>
                        <p class="analysis-subtitle">前几条和弦推断</p>
                        <div class="analysis-chip-row">
                            ${chordPreviewMarkup}
                        </div>
                    </div>
                </section>
                <section class="analysis-card">
                    <h3>流程提示</h3>
                    <div class="analysis-stack">
                        <div class="analysis-metrics">
                            ${metricCard("分析 ID", result.analysis_id || "--")}
                            ${metricCard("音高算法", result.pipeline?.pitch_algorithm || "--")}
                            ${metricCard("分离来源", localizePitchSource(result.pipeline?.pitch_source || "--"))}
                            ${metricCard("增强策略", harmonicSummary.join(" / ") || "基础策略")}
                        </div>
                        ${warningMarkup}
                        <div class="analysis-list">
                            <div class="analysis-item">
                                <div>
                                    <div class="analysis-item-title">调试建议</div>
                                    <div class="analysis-item-meta">如果结果不理想，优先看旋律轨是否选对，再看调号候选和和弦来源。</div>
                                </div>
                                <div class="analysis-item-value">${escapeHtmlText(selectedTrack?.name ? "先查主旋律轨" : "先查混音回退")}</div>
                            </div>
                            <div class="analysis-item">
                                <div>
                                    <div class="analysis-item-title">和声策略</div>
                                    <div class="analysis-item-meta">当前吉他推断已支持副属、借和弦和段落平滑。</div>
                                </div>
                                <div class="analysis-item-value">${escapeHtmlText(harmonicSummary.join(" / ") || "--")}</div>
                            </div>
                        </div>
                    </div>
                </section>
            </div>
        </div>
    `;
}

function renderBeatDetectPanel() {
    if (!state.beatDetectResult) {
        els.beatDetectOutput.innerHTML = '<p class="analysis-placeholder">运行节拍检测后，这里会展示 BPM、拍点分布和节拍时间轴。</p>';
        return;
    }
    const result = state.beatDetectResult;
    const beats = Array.isArray(result.beats)
        ? result.beats
        : Array.isArray(result.beat_times)
            ? result.beat_times
            : [];
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
        els.generateChordsOutput.innerHTML = isGuitarMode()
            ? '<p class="analysis-placeholder">吉他模式下，这里会展示和弦时间轴；更完整的小节和弦、按法、Capo 与扫弦型会显示在上方的吉他弹唱谱预览模块。</p>'
            : '<p class="analysis-placeholder">当前双手钢琴谱会在这里展示和弦时间轴、左手织体和双手分配规则。生成或载入一份双手钢琴谱后即可查看。</p>';
        return;
    }
    const result = state.chordGenerationResult;
    const chords = Array.isArray(result.chords) ? result.chords : [];
    if (result.arrangement_type === "piano_solo") {
        const leftHandPattern = result.left_hand_pattern?.name || "--";
        const splitPoint = result.split_point?.note || "--";
        const accompanimentNoteCount = result.accompaniment_note_count || 0;
        const harmonicSummary = [
            result.harmonic_strategy?.secondary_dominants_enabled ? "副属" : null,
            result.harmonic_strategy?.borrowed_chords_enabled ? "借和弦" : null,
            result.harmonic_strategy?.segment_smoothing_enabled ? "段落平滑" : null,
        ].filter(Boolean).join(" / ") || "基础和声";
        const handRules = Array.isArray(result.hand_assignment?.rule_summary) ? result.hand_assignment.rule_summary : [];
        els.generateChordsOutput.innerHTML = `
            <div class="analysis-stack analysis-tone-green">
                <div class="analysis-metrics">
                    ${metricCard("调号", escapeHtmlText(result.key || "--"))}
                    ${metricCard("速度", result.tempo ? `${result.tempo} BPM` : "--")}
                    ${metricCard("左手型", escapeHtmlText(leftHandPattern))}
                    ${metricCard("分手点", escapeHtmlText(splitPoint))}
                    ${metricCard("和弦数", chords.length)}
                    ${metricCard("伴奏音符", accompanimentNoteCount)}
                </div>
                <p class="analysis-subtitle">和弦时间轴</p>
                ${buildChordTimeline(chords)}
                ${result.left_hand_pattern?.description ? `<div class="analysis-note">${escapeHtmlText(result.left_hand_pattern.description)}</div>` : ""}
                <div class="analysis-list">
                    <div class="analysis-item">
                        <div>
                            <div class="analysis-item-title">双手分配</div>
                            <div class="analysis-item-meta">主旋律固定右手，左手负责低音与和声音壳。</div>
                        </div>
                        <div class="analysis-item-value">${escapeHtmlText(splitPoint)}</div>
                    </div>
                    <div class="analysis-item">
                        <div>
                            <div class="analysis-item-title">和声策略</div>
                            <div class="analysis-item-meta">当前双手钢琴谱会复用调内和弦、副属、借和弦和段落平滑。</div>
                        </div>
                        <div class="analysis-item-value">${escapeHtmlText(harmonicSummary)}</div>
                    </div>
                    ${chords.map((chord) => `
                        <div class="analysis-item">
                            <div>
                                <div class="analysis-item-title">${escapeHtmlText(chord.symbol || "--")}</div>
                                <div class="analysis-item-meta">第 ${escapeHtmlText(String(chord.measure_no || "--"))} 小节 / 第 ${escapeHtmlText(String(chord.beat_in_measure || "--"))} 拍 / ${escapeHtmlText(chord.source || "diatonic")}</div>
                            </div>
                            <div class="analysis-item-value">${escapeHtmlText(chord.roman || "--")}</div>
                        </div>
                    `).join("") || '<div class="analysis-note">暂未返回和弦结果。</div>'}
                </div>
                ${handRules.length ? `
                    <p class="analysis-subtitle">分手规则</p>
                    <div class="analysis-chip-row">
                        ${handRules.map((rule) => `<span class="analysis-chip">${escapeHtmlText(rule)}</span>`).join("")}
                    </div>
                ` : ""}
            </div>
        `;
        return;
    }
    const capoText = Number.isFinite(Number(result.capo_suggestion?.capo))
        ? `Capo ${Number(result.capo_suggestion.capo)}`
        : "--";
    const strummingText = resolveStrummingDisplayPattern(result.strumming_pattern);
    const guitarShapes = result.guitar_shapes && typeof result.guitar_shapes === "object" ? Object.values(result.guitar_shapes) : [];
    els.generateChordsOutput.innerHTML = `
        <div class="analysis-stack analysis-tone-green">
            <div class="analysis-metrics">
                ${metricCard("调号", result.key || "--")}
                ${metricCard("速度", result.tempo ? `${result.tempo} BPM` : "--")}
                ${metricCard("风格", result.style || "--")}
                ${metricCard("旋律音符", result.melody_size || 0)}
                ${metricCard("变调夹", capoText)}
                ${metricCard("扫弦型", strummingText)}
            </div>
            <p class="analysis-subtitle">和弦时间轴</p>
            ${buildChordTimeline(chords)}
            ${result.strumming_pattern?.description ? `<div class="analysis-note">${escapeHtmlText(result.strumming_pattern.description)}</div>` : ""}
            ${guitarShapes.length ? `
                <p class="analysis-subtitle">常用吉他按法</p>
                <div class="analysis-list">
                    ${guitarShapes.map((shape) => `
                        <div class="analysis-item">
                            <div>
                                <div class="analysis-item-title">${escapeHtmlText(shape.symbol || shape.display_name || "--")}</div>
                                <div class="analysis-item-meta">${escapeHtmlText(shape.family || "guitar")} / ${escapeHtmlText(shape.difficulty || "medium")}</div>
                            </div>
                            <div class="analysis-item-value">${escapeHtmlText(shape.fingering || "--")}</div>
                        </div>
                    `).join("")}
                </div>
            ` : ""}
            <div class="analysis-list">
                ${chords.map((chord) => `
                    <div class="analysis-item">
                        <div>
                            <div class="analysis-item-title">${escapeHtmlText(chord.symbol || "--")}</div>
                            <div class="analysis-item-meta">第 ${escapeHtmlText(String(chord.measure_no || "--"))} 小节 / 第 ${escapeHtmlText(String(chord.beat_in_measure || "--"))} 拍</div>
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
        vocals: "人声",
        lead_vocal: "主唱",
        accompaniment: "伴奏",
        drums: "鼓组",
        bass: "低音",
        guitar: "吉他",
        piano: "钢琴",
        mix: "混音",
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
        guitar_lead_sheet_audio: "吉他识谱",
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
    if (["vocal", "vocals", "lead_vocal"].includes(normalized)) {
        return "vocal";
    }
    if (normalized === "mix") {
        return "other";
    }
    if (["accompaniment", "drums", "bass", "guitar", "piano", "other"].includes(normalized)) {
        return normalized;
    }
    return "other";
}

function trackGlyph(name) {
    const normalized = String(name || "").toLowerCase();
    if (["vocal", "vocals", "lead_vocal"].includes(normalized)) {
        return "VO";
    }
    const glyphs = {
        vocal: "VO",
        accompaniment: "AC",
        drums: "DR",
        bass: "BA",
        guitar: "GT",
        piano: "PI",
        mix: "MX",
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
    const hasGuzhengScore = Boolean(state.guzhengResult);
    const hasGuitarLeadSheet = Boolean(state.guitarLeadSheetResult);
    const hasDiziResult = Boolean(isCurrentDiziResult(state.diziResult));
    const hasExport = Boolean(state.selectedExportDetail);
    const hasAnalysisFile = Boolean(els.analysisFileInput.files?.length);
    const hasScoreFile = Boolean(els.scoreMusicxmlFileInput.files?.length);
    const hasPitchSequence = Array.isArray(state.latestPitchSequence) && state.latestPitchSequence.length > 0;
    const hasGuitarSource = hasScore || hasPitchSequence || Boolean((els.analysisIdInput.value || "").trim());
    const hasGuzhengSource = hasScore || hasPitchSequence || Boolean((els.analysisIdInput.value || "").trim());
    const hasDiziSource = hasScore || hasPitchSequence || Boolean((els.analysisIdInput.value || "").trim());
    const guitarMode = isGuitarMode();
    const guzhengMode = isGuzhengMode();
    const diziMode = isDiziMode();
    const customMode = isCustomLeadSheetMode();
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
    els.generateChordsBtn.disabled = !(
        guitarMode
            ? hasGuitarSource || hasGuitarLeadSheet
            : guzhengMode
                ? hasGuzhengSource || hasGuzhengScore
                : diziMode
                    ? hasDiziSource || hasDiziResult
                : hasScore
    ) || isBusy("generate-chords");
    els.rhythmScoreBtn.disabled = isBusy("rhythm-score");
    els.refreshAudioLogsBtn.disabled = isBusy("audio-logs");
    els.applyScoreSettingsBtn.disabled = customMode || !hasScore || isBusy("score-settings");
    els.undoBtn.disabled = customMode || !hasScore || isBusy("undo-action");
    els.redoBtn.disabled = customMode || !hasScore || isBusy("redo-action");
    els.downloadMusicxmlBtn.disabled = customMode || !hasScore;
    els.refreshScoreBtn.disabled = customMode || !hasScore || isBusy(`score-load-${state.currentScore?.score_id || state.selectedScoreId}`);
    els.replaceScoreFromFileBtn.disabled = customMode || !hasScore || !hasScoreFile || isBusy("score-file-replace");
    els.loadScoreFileIntoEditorBtn.disabled = customMode || !hasScoreFile;
    els.exportScorePdfBtn.disabled = customMode || !hasScore || isBusy("piano-export-pdf");
    els.openScoreViewerBtn.disabled = customMode || !hasScore;
    els.closeScoreViewerBtn.disabled = !state.scoreViewerOpen;
    els.scoreViewerPagePrevBtn.disabled = !canGoPrevPage;
    els.scoreViewerPageNextBtn.disabled = !canGoNextPage;
    els.createExportBtn.disabled = customMode || !hasScore || isBusy("create-export");
    els.refreshExportsBtn.disabled = customMode || !hasScore || isBusy("load-exports");
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
