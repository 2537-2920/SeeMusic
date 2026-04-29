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
    diziFluteType: "seemusic.transcription.diziFluteType",
    scoreId: "seemusic.transcription.scoreId",
    tempo: "seemusic.transcription.tempo",
    timeSignature: "seemusic.transcription.timeSignature",
    keySignature: "seemusic.transcription.keySignature",
    pitchSequence: "seemusic.transcription.pitchSequence",
};

const LEGACY_STORAGE_KEYS = [
    "seemusic.transcription.lyricsMode",
    "seemusic.transcription.guitarDebugExpanded",
    "seemusic.transcription.guzhengDebugExpanded",
    "seemusic.transcription.diziDebugExpanded",
];
const TRANSCRIPTION_UI_BUILD = "2026-04-29-lyrics-ui-removed-v1";
const DEFAULT_BACKEND_ORIGIN = "http://127.0.0.1:8000";
const DEFAULT_API_BASE = `${DEFAULT_BACKEND_ORIGIN}/api/v1`;
const VEROVIO_RESOURCE_PATH = "/data";
const VEROVIO_GLYPHNAMES_PATH = `${VEROVIO_RESOURCE_PATH}/glyphnames.json`;
const VEROVIO_TUNING_GLYPHNAMES_PATH = `${VEROVIO_RESOURCE_PATH}/tuning-glyphnames.json`;
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
const DEFAULT_PITCH_DETECT_CONFIG = {
    algorithm: "yin",
    frameMs: 20,
    hopMs: 10,
};
const SUPPORTED_INSTRUMENT_TYPES = new Set(["piano", "guzheng", "guitar", "dizi"]);
const SUPPORTED_PIANO_RESULT_MODES = new Set(["arranged"]);
const SUPPORTED_JIANPU_LAYOUT_MODES = new Set(["preview", "print"]);
const SUPPORTED_JIANPU_ANNOTATION_LAYERS = new Set(["basic", "technique"]);
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
    previewPageIndex: 0,
    previewPageSymbolOffsets: [],
    previewPageSymbolOffsetsKey: "",
    editorIndexMap: null,
    editorIndexMapKey: "",
    viewerPageCount: 0,
    viewerPageRanges: [],
    viewerPreparedKey: "",
    viewerPreparedMusicxml: "",
    viewerPreparedLayout: null,
    viewerPageCache: new Map(),
    viewerPageSymbolOffsets: [],
    viewerPageSymbolOffsetsKey: "",
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
    editorSelectedMxmlIndex: null,
    editorSelectedKind: null,
    editorSelectedSummary: "",
    editorWorkbenchOpen: true,
    editorJianpuLookup: null,
    editorJianpuLookupKey: "",
    editorTechniqueIndex: null,
    editorTechniqueIndexKey: "",
    editorHarmonyIndex: null,
    editorHarmonyIndexKey: "",
    editorChordRoot: "C",
    editorChordAlter: 0,
    editorChordKind: "major",
};

const els = {};

document.addEventListener("DOMContentLoaded", init);

function init() {
    LEGACY_STORAGE_KEYS.forEach((key) => localStorage.removeItem(key));
    cacheElements();
    renderTopbarUser();
    syncFixedTopbarSpacing();
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

function syncFixedTopbarSpacing() {
    const topbar = document.querySelector(".page-shell > .topbar");
    if (!topbar) {
        return;
    }
    const height = Math.ceil(topbar.getBoundingClientRect().height || topbar.offsetHeight || 0);
    if (height <= 0) {
        return;
    }
    document.documentElement.style.setProperty("--topbar-reserved-height", `${height}px`);
}

function renderTopbarUser(user) {
    const appCommon = window.SeeMusicApp;
    if (!appCommon || typeof appCommon.syncPageUsers !== "function") {
        return;
    }
    const options = {
        fallbackName: "游客模式",
        fallbackSeed: "SeeMusic",
    };
    if (arguments.length > 0) {
        options.user = user;
    }
    appCommon.syncPageUsers(options);
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
        "separation-model-input",
        "separation-stems-input",
        "pitch-detect-file-input",
        "pitch-detect-algorithm-input",
        "pitch-detect-frame-ms-input",
        "pitch-detect-hop-ms-input",
        "pitch-detect-btn",
        "pitch-detect-and-score-btn",
        "pitch-detect-status",
        "analysis-tools-panel",
        "separate-tracks-btn",
        "refresh-audio-logs-btn",
        "separate-tracks-output",
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
        "edit-workbench-panel",
        "edit-workbench-body",
        "edit-selection-summary",
        "edit-workbench-non-piano-hint",
        "edit-save-status",
        "edit-save-status-text",
        "preview-page-nav",
        "preview-page-prev-btn",
        "preview-page-next-btn",
        "preview-page-status",
        "refresh-workbench-btn",
        "edit-note-prev-btn",
        "edit-note-next-btn",
        "edit-nav-hint-piano",
        "edit-nav-hint-traditional",
        "edit-nav-hint-guitar",
        "edit-workbench-title",
        "edit-workbench-intro",
        "chord-root-row",
        "chord-alter-row",
        "chord-kind-row",
        "chord-preview",
    ].forEach((id) => {
        const key = id.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
        els[key] = document.getElementById(id);
    });
    els.instrumentToggleButtons = Array.from(document.querySelectorAll("[data-instrument-type]"));
    els.pianoResultModeButtons = Array.from(document.querySelectorAll("[data-piano-result-mode]"));
    els.editPaletteButtons = Array.from(document.querySelectorAll("[data-edit-action]"));
    els.editPaletteSections = Array.from(document.querySelectorAll("[data-palette-for]"));
    els.chordRootButtons = Array.from(document.querySelectorAll("[data-chord-root]"));
    els.chordAlterButtons = Array.from(document.querySelectorAll("[data-chord-alter]"));
    els.chordKindButtons = Array.from(document.querySelectorAll("[data-chord-kind]"));
}

function hydrateInputs() {
    els.apiBaseInput.value = loadPreferredApiBase();
    els.userIdInput.value = String(resolveCachedScoreOwnerUserId() || localStorage.getItem(STORAGE_KEYS.userId) || "");
    els.projectTitleInput.value = localStorage.getItem(STORAGE_KEYS.title) || "我的智能识谱项目";
    els.analysisIdInput.value = localStorage.getItem(STORAGE_KEYS.analysisId) || "";
    state.instrumentType = resolveInstrumentType(localStorage.getItem(STORAGE_KEYS.instrumentType) || "piano");
    if (document.body) {
        document.body.dataset.instrumentType = state.instrumentType;
    }
    state.pianoResultMode = resolvePianoResultMode(localStorage.getItem(STORAGE_KEYS.pianoResultMode) || "arranged");
    state.jianpuLayoutMode = resolveJianpuLayoutMode(localStorage.getItem(STORAGE_KEYS.jianpuLayoutMode) || "preview");
    state.jianpuAnnotationLayer = resolveJianpuAnnotationLayer(localStorage.getItem(STORAGE_KEYS.jianpuAnnotationLayer) || "basic");
    state.guitarViewMode = resolveGuitarViewMode(localStorage.getItem(STORAGE_KEYS.guitarViewMode) || "screen");
    state.diziFluteType = resolveDiziFluteType(localStorage.getItem(STORAGE_KEYS.diziFluteType) || "G");
    state.preferredTempo = parseStoredTempo(localStorage.getItem(STORAGE_KEYS.tempo));
    state.preferredTimeSignature = normalizeTimeSignature(localStorage.getItem(STORAGE_KEYS.timeSignature));
    state.preferredKeySignature = normalizeKeySignature(localStorage.getItem(STORAGE_KEYS.keySignature));
    state.latestPitchSequence = loadStoredPitchSequence();
    if (els.diziFluteTypeInput) {
        els.diziFluteTypeInput.value = state.diziFluteType;
    }
    els.pitchDetectAlgorithmInput.value = DEFAULT_PITCH_DETECT_CONFIG.algorithm;
    els.pitchDetectFrameMsInput.value = String(DEFAULT_PITCH_DETECT_CONFIG.frameMs);
    els.pitchDetectHopMsInput.value = String(DEFAULT_PITCH_DETECT_CONFIG.hopMs);
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

function currentInstrumentType() {
    return resolveInstrumentType(document.body?.dataset?.instrumentType || state.instrumentType);
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
    if (normalized === "fingering" || normalized === "all") {
        return "technique";
    }
    return SUPPORTED_JIANPU_ANNOTATION_LAYERS.has(normalized) ? normalized : "basic";
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
    return currentInstrumentType() === "guitar";
}

function isGuzhengMode() {
    return currentInstrumentType() === "guzheng";
}

function isDiziMode() {
    return currentInstrumentType() === "dizi";
}

function isPianoMode() {
    return currentInstrumentType() === "piano";
}

function supportsManualEdit(instrumentType = resolveActiveInstrumentForEditor()) {
    return instrumentType === "piano" || instrumentType === "guitar";
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
    if (document.body) {
        document.body.dataset.instrumentType = resolved;
    }
    if (persist) {
        localStorage.setItem(STORAGE_KEYS.instrumentType, resolved);
    }
    if (!supportsManualEdit(resolved)) {
        resetEditorSelectionState();
        syncSelectionHighlightToCurrentSelection();
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
            technique: "技法提示层",
        };
        setAppStatus(`已切换到${labelMap[resolved] || "基础正文层"}。`);
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
    const appCommon = window.SeeMusicApp;
    const cachedUser = appCommon && typeof appCommon.getCurrentUser === "function" ? appCommon.getCurrentUser() : null;
    if (cachedUser) {
        renderTopbarUser(cachedUser);
    }

    const cachedUserId = resolveCachedScoreOwnerUserId();
    if (cachedUserId) {
        persistScoreOwnerUserId(cachedUserId);
        return cachedUserId;
    }

    if (!appCommon || typeof appCommon.getAuthToken !== "function" || !appCommon.getAuthToken()) {
        return resolveNumericUserId(els.userIdInput.value);
    }
    if (typeof appCommon.requestJson !== "function") {
        return resolveNumericUserId(els.userIdInput.value);
    }

    try {
        const currentUser = await appCommon.requestJson("/users/me");
        renderTopbarUser(currentUser);
        return persistScoreOwnerUserId(currentUser?.user_id);
    } catch {
        renderTopbarUser(cachedUser || null);
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
    event.preventDefault();
    event.stopPropagation();
    const nextType = event.currentTarget?.dataset?.instrumentType;
    if (!nextType) {
        return;
    }
    setInstrumentType(nextType, { announce: true });
    renderAll();
}

function handlePianoResultModeChange(event) {
    event.preventDefault();
    event.stopPropagation();
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
        return;
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

    const chordPair = event.target.closest(".guitar-inline-chord-token[data-mxml-index]");
    if (chordPair) {
        const idx = Number(chordPair.getAttribute("data-mxml-index"));
        if (Number.isFinite(idx)) {
            state.editorSelectedMxmlIndex = idx;
            state.editorSelectedKind = "chord-anchor";
            const host = event.currentTarget;
            host.querySelectorAll(".is-edit-selected").forEach((el) => el.classList.remove("is-edit-selected"));
            chordPair.classList.add("is-edit-selected");
            renderEditWorkbench();
            return;
        }
    }

    const chordButton = event.target.closest("[data-guitar-chord-symbol]");
    if (!chordButton) {
        return;
    }
    const chordSymbol = String(chordButton.dataset.guitarChordSymbol || "").trim();
    setGuitarHighlightedChordSymbol(state.guitarHighlightedChordSymbol === chordSymbol ? "" : chordSymbol);
    renderGuitarLeadSheetPanel();
}

function bindEvents() {
    els.saveApiBaseBtn.addEventListener("click", handleSaveApiBase);
    els.pingBackendBtn.addEventListener("click", checkBackendConnection);
    els.createScoreBtn.addEventListener("click", handleCreateScore);
    els.pitchDetectBtn?.addEventListener("click", handlePitchDetect);
    els.pitchDetectAndScoreBtn?.addEventListener("click", handlePitchDetectAndScore);
    els.separateTracksBtn?.addEventListener("click", handleSeparateTracks);
    els.instrumentToggleButtons.forEach((button) => button.addEventListener("click", handleInstrumentTypeChange));
    els.pianoResultModeButtons.forEach((button) => button.addEventListener("click", handlePianoResultModeChange));
    els.diziFluteTypeInput?.addEventListener("change", handleDiziFluteTypeChange);
    els.guzhengScoreView?.addEventListener("click", handleTraditionalScoreInteraction);
    els.guitarLeadSheetView?.addEventListener("click", handleGuitarLeadSheetInteraction);
    els.diziScoreView?.addEventListener("change", handleTraditionalScoreInputChange);
    els.diziScoreView?.addEventListener("click", handleTraditionalScoreInteraction);
    els.refreshAudioLogsBtn?.addEventListener("click", () => loadAudioLogs());
    els.applyScoreSettingsBtn?.addEventListener("click", handleApplyScoreSettings);
    els.undoBtn?.addEventListener("click", handleUndo);
    els.redoBtn?.addEventListener("click", handleRedo);
    els.downloadMusicxmlBtn?.addEventListener("click", handleDownloadMusicxml);
    els.refreshScoreBtn?.addEventListener("click", handleRefreshScore);
    els.replaceScoreFromFileBtn?.addEventListener("click", handleReplaceScoreFromFile);
    els.loadScoreFileIntoEditorBtn?.addEventListener("click", handleLoadScoreFileIntoEditor);
    els.exportScorePdfBtn.addEventListener("click", handleExportScorePdf);
    els.openScoreViewerBtn?.addEventListener("click", openScoreViewer);
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
    els.editPaletteButtons?.forEach((button) => button.addEventListener("click", handleEditPaletteClick));
    els.previewPagePrevBtn?.addEventListener("click", () => changePreviewPage(-1));
    els.previewPageNextBtn?.addEventListener("click", () => changePreviewPage(1));
    els.refreshWorkbenchBtn?.addEventListener("click", handleRefreshWorkbench);
    els.editNotePrevBtn?.addEventListener("click", () => stepEditorSelection(-1));
    els.editNoteNextBtn?.addEventListener("click", () => stepEditorSelection(1));
    els.chordRootButtons?.forEach((btn) =>
        btn.addEventListener("click", () => {
            state.editorChordRoot = btn.dataset.chordRoot || "C";
            renderEditWorkbench();
        }),
    );
    els.chordAlterButtons?.forEach((btn) =>
        btn.addEventListener("click", () => {
            state.editorChordAlter = Number(btn.dataset.chordAlter || 0);
            renderEditWorkbench();
        }),
    );
    els.chordKindButtons?.forEach((btn) =>
        btn.addEventListener("click", () => {
            state.editorChordKind = btn.dataset.chordKind || "major";
            renderEditWorkbench();
        }),
    );
    els.analysisToolsPanel?.addEventListener("toggle", () => {
        state.analysisToolsOpen = els.analysisToolsPanel.open;
    });
    window.addEventListener("resize", () => {
        syncFixedTopbarSpacing();
        if (state.currentScore) {
            scheduleNotationRender();
            if (state.scoreViewerOpen) {
                scheduleNotationRender({ viewerOnly: true });
            }
        }
    });
    window.addEventListener("load", syncFixedTopbarSpacing);
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
        const error = new Error(detail || "请求失败");
        error.status = response.status;
        error.payload = payload;
        throw error;
    }
    if (payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "code")) {
        if (payload.code !== 0) {
            throw new Error(payload.message || "请求失败");
        }
        return payload.data;
    }
    return payload;
}

function clearStaleSelectedScore(scoreId) {
    if (state.selectedScoreId === scoreId) {
        state.selectedScoreId = "";
    }
    if (state.currentScore?.score_id === scoreId) {
        state.currentScore = null;
        renderAll();
    }
    localStorage.removeItem(STORAGE_KEYS.scoreId);
}

async function saveUserHistory(payload) {
    const appCommon = window.SeeMusicApp;
    if (!appCommon || typeof appCommon.getAuthToken !== "function" || !appCommon.getAuthToken()) {
        return;
    }
    const source = String(payload.metadata?.source || "");
    if (payload.type === "transcription" && source !== "pitch_detect") {
        return;
    }
    const body = {
        ...payload,
        resource_id: String(payload.resource_id || `history_${Date.now()}`).slice(0, 64),
    };
    try {
        await requestJson("/users/me/history", {
            method: "POST",
            body,
        });
    } catch (error) {
        console.warn("[SeeMusic] save history failed:", error);
    }
}

function activeHistoryTitle(fallback) {
    return (els.projectTitleInput?.value || "").trim() || state.currentScore?.title || fallback;
}

function activeHistoryResourceId(fallback) {
    return (
        state.currentScore?.score_id ||
        (els.analysisIdInput?.value || "").trim() ||
        fallback ||
        `history_${Date.now()}`
    );
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

function clearFileInputValue(input) {
    if (!input || !("value" in input)) {
        return;
    }
    input.value = "";
}

function clearWorkbenchState({ preserveProjectTitle = true } = {}) {
    const preservedTitle = preserveProjectTitle
        ? String(els.projectTitleInput?.value ?? localStorage.getItem(STORAGE_KEYS.title) ?? "")
        : "";

    state.currentScore = null;
    state.guzhengResult = null;
    state.guzhengEngravedPreview = null;
    state.guitarLeadSheetResult = null;
    state.diziResult = null;
    state.diziEngravedPreview = null;
    state.guitarHighlightedChordSymbol = "";
    state.preferredTempo = DEFAULT_TRANSCRIPTION_SETTINGS.tempo;
    state.preferredTimeSignature = DEFAULT_TRANSCRIPTION_SETTINGS.timeSignature;
    state.preferredKeySignature = DEFAULT_TRANSCRIPTION_SETTINGS.keySignature;
    setLatestPitchSequence([]);
    state.selectedScoreId = "";
    state.selectedNotationElementId = null;
    state.exportList = [];
    state.selectedExportRecordId = null;
    state.selectedExportDetail = null;
    state.beatDetectResult = null;
    state.separateTracksResult = null;
    state.chordGenerationResult = null;
    state.rhythmScoreResult = null;
    state.audioLogs = [];
    state.scorePageIndex = 0;
    state.scoreViewerOpen = false;
    state.previewPageCount = 0;
    state.previewPageIndex = 0;
    state.previewPageSymbolOffsets = [];
    state.previewPageSymbolOffsetsKey = "";
    state.editorIndexMap = null;
    state.editorIndexMapKey = "";
    state.viewerPageCount = 0;
    state.viewerPageRanges = [];
    state.viewerPreparedKey = "";
    state.viewerPreparedMusicxml = "";
    state.viewerPreparedLayout = null;
    state.viewerPageCache = new Map();
    state.viewerPageSymbolOffsets = [];
    state.viewerPageSymbolOffsetsKey = "";
    state.viewerGesture = null;
    state.viewerWheelAccumX = 0;
    state.viewerSuppressClickUntil = 0;
    state.editorSelectedMxmlIndex = null;
    state.editorSelectedKind = null;
    state.editorSelectedSummary = "";
    state.editorJianpuLookup = null;
    state.editorJianpuLookupKey = "";
    state.editorTechniqueIndex = null;
    state.editorTechniqueIndexKey = "";
    state.editorHarmonyIndex = null;
    state.editorHarmonyIndexKey = "";
    invalidateViewerRenderState();
    resetEditorSelectionState();

    if (els.analysisIdInput) {
        els.analysisIdInput.value = "";
    }
    if (els.scoreMusicxmlInput) {
        els.scoreMusicxmlInput.value = "";
    }
    clearFileInputValue(els.pitchDetectFileInput);
    clearFileInputValue(els.analysisFileInput);
    clearFileInputValue(els.scoreMusicxmlFileInput);
    setPitchDetectStatus("");

    if (els.scoreViewerEntry) {
        els.scoreViewerEntry.innerHTML = "";
    }
    if (els.scoreViewerCanvas) {
        els.scoreViewerCanvas.innerHTML = "";
    }
    if (els.guzhengScoreView) {
        els.guzhengScoreView.innerHTML = "";
    }
    if (els.guitarLeadSheetView) {
        els.guitarLeadSheetView.innerHTML = "";
    }
    if (els.diziScoreView) {
        els.diziScoreView.innerHTML = "";
    }
    if (els.guzhengDebugPanel) {
        els.guzhengDebugPanel.innerHTML = "";
    }
    if (els.guitarDebugPanel) {
        els.guitarDebugPanel.innerHTML = "";
    }
    if (els.diziDebugPanel) {
        els.diziDebugPanel.innerHTML = "";
    }
    if (els.separateTracksOutput) {
        els.separateTracksOutput.innerHTML = "";
    }
    if (els.audioLogList) {
        els.audioLogList.innerHTML = "";
    }
    if (els.exportList) {
        els.exportList.innerHTML = "";
    }

    localStorage.removeItem(STORAGE_KEYS.analysisId);
    localStorage.removeItem(STORAGE_KEYS.scoreId);
    localStorage.removeItem(STORAGE_KEYS.tempo);
    localStorage.removeItem(STORAGE_KEYS.timeSignature);
    localStorage.removeItem(STORAGE_KEYS.keySignature);

    if (preserveProjectTitle && els.projectTitleInput) {
        els.projectTitleInput.value = preservedTitle;
        setLocalStorageSafely(STORAGE_KEYS.title, preservedTitle, { silent: true });
    }
}

function handleRefreshWorkbench() {
    if (state.busyKeys.size > 0) {
        setAppStatus("当前仍有任务在执行，请等待完成后再刷新并清空工作台。", true);
        return;
    }
    clearWorkbenchState({ preserveProjectTitle: true });
    renderAll();
    setAppStatus("已刷新并清空当前工作台，项目标题已保留。");
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
        throw new Error("请先上传音频并生成乐谱，或保留一份已有的音高序列");
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
    state.previewPageIndex = 0;
    renderPreviewPageNav();
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
    const instrumentType = currentInstrumentType();
    if (instrumentType === "guitar") {
        return "吉他弹唱谱";
    }
    if (instrumentType === "guzheng") {
        return "古筝谱";
    }
    if (instrumentType === "dizi") {
        return "笛子谱";
    }
    return "乐谱";
}

function resolveActivePdfExportContext() {
    const instrumentType = currentInstrumentType();
    if (instrumentType === "guzheng") {
        return {
            instrumentType,
            busyKey: "traditional-export-guzheng",
            hasExportable: Boolean(state.guzhengResult),
            missingMessage: "请先生成古筝谱。",
        };
    }
    if (instrumentType === "dizi") {
        return {
            instrumentType,
            busyKey: "traditional-export-dizi",
            hasExportable: Boolean(isCurrentDiziResult(state.diziResult)),
            missingMessage: "请先生成当前笛型对应的笛子谱。",
        };
    }
    if (instrumentType === "guitar") {
        return {
            instrumentType,
            busyKey: "guitar-export-pdf",
            hasExportable: Boolean(state.guitarLeadSheetResult),
            missingMessage: "请先生成吉他弹唱谱。",
        };
    }
    return {
        instrumentType: "piano",
        busyKey: "piano-export-pdf",
        hasExportable: Boolean(state.currentScore?.score_id),
        missingMessage: "请先生成或载入一份钢琴乐谱。",
    };
}

function setAnalysisToolsOpen(isOpen) {
    state.analysisToolsOpen = Boolean(isOpen);
    if (els.analysisToolsPanel) {
        els.analysisToolsPanel.open = state.analysisToolsOpen;
    }
}

function getPitchDetectConfig() {
    return { ...DEFAULT_PITCH_DETECT_CONFIG };
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
    formData.append("beat_sensitivity", "0.5");
    formData.append("separation_model", (els.separationModelInput?.value || "").trim() || "demucs");
    formData.append("separation_stems", els.separationStemsInput?.value || "2");
    formData.append("arrangement_mode", arrangementMode);

    const result = await requestJson("/score/from-audio", {
        method: "POST",
        body: formData,
    });
    if (result.analysis_id) {
        els.analysisIdInput.value = result.analysis_id || "";
        setLocalStorageSafely(STORAGE_KEYS.analysisId, els.analysisIdInput.value, { silent: true });
    }
    state.beatDetectResult = result.beat_result
        ? { ...result.beat_result, analysis_id: result.analysis_id, audio_log: result.audio_log }
        : null;
    state.separateTracksResult = result.separation || null;
    state.chordGenerationResult = result.piano_arrangement || null;
    setLatestPitchSequence(result.pitch_sequence || []);
    applyDetectedTempo(result.tempo_detection?.resolved_tempo || result.tempo);
    applyDetectedKeySignature(result.detected_key_signature || result.key_signature);
    state.exportList = [];
    state.selectedExportRecordId = null;
    state.selectedExportDetail = null;
    applyScoreResult(result);
    await loadAudioLogs();
    queueExportRefresh();
    await saveUserHistory({
        type: "transcription",
        resource_id: result.score_id || result.analysis_id || activeHistoryResourceId("piano_score"),
        title: `生成钢琴谱：${activeHistoryTitle(file.name)}`,
        metadata: {
            source: "score_from_audio",
            filename: file.name,
            analysis_id: result.analysis_id || "",
            score_id: result.score_id || "",
            instrument: "piano",
            tempo: result.tempo || "",
            key_signature: result.key_signature || result.detected_key_signature || "",
        },
    });
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
    await saveUserHistory({
        type: "transcription",
        resource_id: result.score_id || activeHistoryResourceId("guzheng_score"),
        title: `生成古筝谱：${payload.title}`,
        metadata: {
            source: "guzheng_score",
            instrument: "guzheng",
            score_id: result.score_id || scoreId || "",
            analysis_id: analysisId || "",
            measure_count: result.measures?.length || 0,
        },
    });
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
        await saveUserHistory({
            type: "transcription",
            resource_id: result.export_id || result.file_name || activeHistoryResourceId(`${normalizedInstrument}_export`),
            title: `导出${targetName}谱：${result.file_name || payload.title}`,
            metadata: {
                source: `${normalizedInstrument}_score_export`,
                instrument: normalizedInstrument,
                format,
                file_name: result.file_name || "",
                download_url: result.download_url || "",
            },
        });
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
        style: "pop",
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
        await saveUserHistory({
            type: "transcription",
            resource_id: result.export_id || result.file_name || activeHistoryResourceId("guitar_export"),
            title: `导出吉他弹唱谱：${result.file_name || payload.title}`,
            metadata: {
                source: "guitar_lead_sheet_export",
                instrument: "guitar",
                format,
                file_name: result.file_name || "",
                download_url: result.download_url || "",
            },
        });
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
    await saveUserHistory({
        type: "transcription",
        resource_id: result.score_id || activeHistoryResourceId("dizi_score"),
        title: `生成笛子谱：${payload.title}`,
        metadata: {
            source: "dizi_score",
            instrument: "dizi",
            score_id: result.score_id || scoreId || "",
            analysis_id: analysisId || "",
            flute_type: result.flute_type || payload.flute_type || "",
            measure_count: result.measures?.length || 0,
        },
    });
    return result;
}

async function requestGuitarLeadSheet({ pitchSequence = null, analysisId = null, scoreId = null } = {}) {
    const base = resolveCustomLeadSheetBase(scoreId);
    const payload = {
        title: base.title,
        key: base.key,
        tempo: base.tempo,
        time_signature: base.timeSignature,
        style: "pop",
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
    await ensureEditableScoreForGuitarResult({ result, base, scoreId, analysisId });
    renderAll();
    await saveUserHistory({
        type: "transcription",
        resource_id: result.score_id || activeHistoryResourceId("guitar_lead_sheet"),
        title: `生成吉他弹唱谱：${payload.title}`,
        metadata: {
            source: "guitar_lead_sheet",
            instrument: "guitar",
            score_id: result.score_id || scoreId || "",
            analysis_id: analysisId || "",
            measure_count: result.measures?.length || 0,
        },
    });
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
    formData.append("beat_sensitivity", "0.5");
    formData.append("separation_model", (els.separationModelInput?.value || "").trim() || "demucs");
    formData.append("separation_stems", els.separationStemsInput?.value || "2");

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
    await saveUserHistory({
        type: "transcription",
        resource_id: result.analysis_id || activeHistoryResourceId("guzheng_audio"),
        title: `生成古筝谱：${file.name}`,
        metadata: {
            source: "guzheng_score_from_audio",
            filename: file.name,
            analysis_id: result.analysis_id || "",
            instrument: "guzheng",
            measure_count: result.measures?.length || 0,
        },
    });
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
    formData.append("beat_sensitivity", "0.5");
    formData.append("separation_model", (els.separationModelInput?.value || "").trim() || "demucs");
    formData.append("separation_stems", els.separationStemsInput?.value || "2");

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
    await saveUserHistory({
        type: "transcription",
        resource_id: result.analysis_id || activeHistoryResourceId("dizi_audio"),
        title: `生成笛子谱：${file.name}`,
        metadata: {
            source: "dizi_score_from_audio",
            filename: file.name,
            analysis_id: result.analysis_id || "",
            instrument: "dizi",
            flute_type: result.flute_type || fluteType || "",
            measure_count: result.measures?.length || 0,
        },
    });
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
    formData.append("style", "pop");
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
    await ensureEditableScoreForGuitarResult({
        result,
        base,
        scoreId: null,
        analysisId: result.analysis_id || null,
    });
    renderAll();
    await saveUserHistory({
        type: "transcription",
        resource_id: result.analysis_id || activeHistoryResourceId("guitar_audio"),
        title: `生成吉他弹唱谱：${file.name}`,
        metadata: {
            source: "guitar_lead_sheet_from_audio",
            filename: file.name,
            analysis_id: result.analysis_id || "",
            instrument: "guitar",
            measure_count: result.measures?.length || 0,
        },
    });
    return result;
}

async function ensureEditableScoreForGuitarResult({ result, base, scoreId = null, analysisId = null } = {}) {
    if (scoreId) {
        if (state.currentScore?.score_id !== scoreId || !state.currentScore?.musicxml) {
            try {
                await loadCurrentScore(scoreId, { silent: true });
            } catch (error) {
                console.warn("[SeeMusic] failed to load guitar source score:", error);
            }
        }
        return;
    }

    const pitchSequence = Array.isArray(result?.pitch_sequence) && result.pitch_sequence.length
        ? result.pitch_sequence
        : parsePitchSequenceOrEmpty();
    if (!pitchSequence.length) {
        return;
    }

    try {
        const created = await requestJson("/score/from-pitch-sequence", {
            method: "POST",
            body: {
                user_id: await ensureScoreOwnerUserId(),
                title: base?.title || result?.title || "Untitled Guitar Lead Sheet",
                analysis_id: result?.analysis_id || analysisId || null,
                tempo: parsePositiveInteger(String(result?.tempo || base?.tempo || DEFAULT_TRANSCRIPTION_SETTINGS.tempo), "速度"),
                time_signature: normalizeTimeSignature(result?.time_signature || base?.timeSignature || DEFAULT_TRANSCRIPTION_SETTINGS.timeSignature),
                key_signature: normalizeKeySignature(result?.detected_key_signature || result?.key || base?.key || DEFAULT_TRANSCRIPTION_SETTINGS.keySignature),
                auto_detect_key: false,
                arrangement_mode: "melody",
                pitch_sequence: pitchSequence,
            },
        });
        state.exportList = [];
        state.selectedExportRecordId = null;
        state.selectedExportDetail = null;
        applyScoreResult(created);
    } catch (error) {
        console.warn("[SeeMusic] failed to create editable guitar base score:", error);
    }
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
        await saveUserHistory({
            type: "transcription",
            resource_id: result.analysis_id || activeHistoryResourceId("pitch_detect"),
            title: `音高识别：${file.name}`,
            metadata: {
                source: "pitch_detect",
                filename: file.name,
                pitch_count: sequence.length,
                key_signature: detectedKeySignature || "",
            },
        });
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
        const instrumentType = currentInstrumentType();
        if (instrumentType === "guitar") {
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
        if (instrumentType === "guzheng") {
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
        if (instrumentType === "dizi") {
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
        if (els.pitchDetectFileInput?.files?.[0]) {
            await handlePitchDetectAndScore();
            return;
        }
        const instrumentType = currentInstrumentType();
        if (instrumentType === "guzheng") {
            const source = resolveCustomLeadSheetSource();
            const generatedScore = await requestGuzhengScore({
                scoreId: source.scoreId,
                pitchSequence: source.pitchSequence,
                analysisId: source.analysisId,
            });
            setAppStatus(`古筝谱已生成，共 ${generatedScore.measures?.length || 0} 小节。`);
            return;
        }
        if (instrumentType === "dizi") {
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
        if (instrumentType === "guitar") {
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
        await saveUserHistory({
            type: "transcription",
            resource_id: created.score_id || payload.analysis_id || activeHistoryResourceId("score_from_pitch"),
            title: `生成钢琴谱：${created.title || payload.title || "未命名乐谱"}`,
            metadata: {
                source: "score_from_pitch_sequence",
                score_id: created.score_id || "",
                analysis_id: payload.analysis_id || "",
                instrument: "piano",
                tempo: created.tempo || payload.tempo,
                key_signature: created.key_signature || payload.key_signature || "",
            },
        });
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
        await saveUserHistory({
            type: "audio",
            resource_id: result.analysis_id || activeHistoryResourceId("beat_detect"),
            title: `节拍检测：${file.name}`,
            metadata: {
                source: "beat_detect",
                filename: file.name,
                analysis_id: result.analysis_id || "",
                bpm: result.bpm || result.primary_bpm || detectedTempo || "",
                beat_count: result.num_beats || result.beat_times?.length || 0,
            },
        });
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
        formData.append("model", (els.separationModelInput?.value || "").trim() || "demucs");
        formData.append("stems", els.separationStemsInput?.value || "2");
        const result = await requestJson("/audio/separate-tracks", { method: "POST", body: formData });
        state.separateTracksResult = result;
        els.analysisIdInput.value = result.analysis_id || els.analysisIdInput.value;
        setLocalStorageSafely(STORAGE_KEYS.analysisId, els.analysisIdInput.value, { silent: true });
        renderAll();
        await loadAudioLogs();
        setAppStatus("音轨分离完成。");
        await saveUserHistory({
            type: "audio",
            resource_id: result.analysis_id || activeHistoryResourceId("separate_tracks"),
            title: `音轨分离：${file.name}`,
            metadata: {
                source: "audio_separate_tracks",
                filename: file.name,
                analysis_id: result.analysis_id || "",
                track_count: result.tracks?.length || 0,
            },
        });
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
        await saveUserHistory({
            type: "transcription",
            resource_id: activeHistoryResourceId("chord_generation"),
            title: `生成和弦：${activeHistoryTitle("未命名乐谱")}`,
            metadata: {
                source: "chord_generation",
                score_id: state.currentScore?.score_id || "",
                chord_count: result.chords?.length || 0,
                key_signature: key,
            },
        });
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
                scoring_model: "balanced",
                threshold_ms: Number(els.rhythmThresholdInput.value || 50),
            },
        });
        state.rhythmScoreResult = result;
        renderAll();
        setAppStatus(`节奏评分完成：${Math.round(Number(result.score || 0))}/100`);
        await saveUserHistory({
            type: "evaluation",
            resource_id: activeHistoryResourceId("rhythm_score"),
            title: `节奏评分：${activeHistoryTitle("节奏练习")}`,
            metadata: {
                source: "rhythm_score",
                score: Math.round(Number(result.score || 0)),
                timing_accuracy: result.timing_accuracy || "",
            },
        });
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
    if (!els.scoreMusicxmlInput) {
        setAppStatus("当前页面未提供 MusicXML 编辑区。", true);
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
        if (!els.scoreMusicxmlFileInput || !els.scoreMusicxmlInput) {
            throw new Error("当前页面未提供 MusicXML 编辑区。");
        }
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
        if (!els.scoreMusicxmlFileInput || !els.scoreMusicxmlInput) {
            throw new Error("当前页面未提供 MusicXML 编辑区。");
        }
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
    const exportContext = resolveActivePdfExportContext();
    if (!exportContext.hasExportable) {
        setAppStatus(exportContext.missingMessage, true);
        return;
    }
    if (isBusy(exportContext.busyKey)) {
        return;
    }
    if (exportContext.instrumentType === "guzheng") {
        await requestTraditionalExport("guzheng", "pdf");
        return;
    }
    if (exportContext.instrumentType === "dizi") {
        await requestTraditionalExport("dizi", "pdf");
        return;
    }
    if (exportContext.instrumentType === "guitar") {
        await requestGuitarLeadSheetExport("pdf");
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
        await saveUserHistory({
            type: "transcription",
            resource_id: String(created.export_record_id || state.currentScore.score_id || activeHistoryResourceId("piano_export")),
            title: `导出钢琴谱：${created.file_name || state.currentScore.title || state.currentScore.score_id}`,
            metadata: {
                source: "piano_score_export",
                score_id: state.currentScore.score_id,
                export_record_id: created.export_record_id || "",
                format: created.format || "pdf",
                file_name: created.file_name || "",
                download_url: created.download_api_url || created.download_url || "",
            },
        });
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
    if (path === "undo" || path === "redo") {
        setEditorSaveStatus("saving", path === "undo" ? "正在向后端请求撤销…" : "正在向后端请求重做…");
        renderEditWorkbench();
    }
    try {
        const updated = await requestJson(`/scores/${state.currentScore.score_id}/${path}`, { method: "POST" });
        applyScoreResult(updated);
        setAppStatus(message);
        if (path === "undo" || path === "redo") {
            const versionLabel = updated?.version != null ? `（v${updated.version}）` : "";
            setEditorSaveStatus(
                "saved",
                `${path === "undo" ? "已撤销" : "已重做"}，已同步到后端${versionLabel}`,
            );
        }
    } catch (error) {
        setAppStatus(`${message} 失败：${error.message}`, true);
        if (path === "undo" || path === "redo") {
            setEditorSaveStatus("error", `${path === "undo" ? "撤销" : "重做"}失败：${error.message}`);
        }
    } finally {
        setBusy(busyKey, false);
        renderEditWorkbench();
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
        if (Number(error?.status) === 404) {
            clearStaleSelectedScore(scoreId);
        }
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
    state.editorIndexMap = null;
    state.editorIndexMapKey = "";
    state.editorJianpuLookup = null;
    state.editorJianpuLookupKey = "";
    state.editorHarmonyIndex = null;
    state.editorHarmonyIndexKey = "";
    state.previewPageSymbolOffsets = [];
    state.previewPageSymbolOffsetsKey = "";
    state.viewerPageSymbolOffsets = [];
    state.viewerPageSymbolOffsetsKey = "";
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
    if (els.scoreMusicxmlInput) {
        els.scoreMusicxmlInput.value = score.musicxml || "";
    }

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
    state.viewerPageSymbolOffsets = [];
    state.viewerPageSymbolOffsetsKey = "";
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
    return "点击谱面中的音符或休止符可高亮查看当前选中位置；如果点不中，可用上一个/下一个切换。";
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
    if (els.pianoResultSwitch) {
        els.pianoResultSwitch.hidden = !pianoMode;
        els.pianoResultSwitch.style.display = pianoMode ? "" : "none";
        els.pianoResultSwitch.setAttribute("aria-hidden", pianoMode ? "false" : "true");
    }
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
        ? "上传样例音频并生成吉他弹唱谱后，这里可展开查看分离轨、定调结果、和弦来源和流程提示。"
        : guzhengMode
            ? "上传样例音频并生成古筝谱后，这里可展开查看分离轨、定调结果、五声音阶统计与技法候选。"
            : diziMode
                ? "上传样例音频并生成笛子谱后，这里会直接展示定调结果、可吹性统计与指法候选。"
                : "双手钢琴模式下会展示节拍、分轨、和弦时间轴、左手织体和双手分配规则。";
    if (els.pitchDetectAndScoreBtn) {
        els.pitchDetectAndScoreBtn.textContent = guitarMode
            ? "识别并生成吉他弹唱谱"
            : guzhengMode
                ? "识别并生成古筝谱"
                : diziMode
                    ? "识别并生成笛子谱"
                    : "识别并生成双手钢琴谱";
    }
    els.createScoreBtn.textContent = guitarMode
        ? "生成吉他弹唱谱"
        : guzhengMode
            ? "生成古筝谱"
            : diziMode
                ? "生成笛子谱"
                : "生成双手钢琴谱";
    els.exportScorePdfBtn.hidden = false;
    if (els.openScoreViewerBtn) {
        els.openScoreViewerBtn.hidden = customMode;
    }
    if (els.scoreSummaryPanel) {
        els.scoreSummaryPanel.hidden = false;
    }
    els.scoreEditorGrid.hidden = false;
    if (els.exportWorkbenchPanel) {
        els.exportWorkbenchPanel.hidden = true;
    }
    document.body?.classList.add("export-workbench-hidden");
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
    renderEditWorkbench();
    renderPreviewPageNav();
    syncSelectionHighlightToCurrentSelection();
    if (isPianoMode()) {
        scheduleNotationRender();
    } else {
        hidePianoPreviewSurfaces();
    }
    syncFixedTopbarSpacing();
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
        return configureVerovioToolkit(new verovioApi.toolkit(moduleRef), moduleRef);
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

function ensureVerovioResourceAliases(moduleRef = window.verovio?.module) {
    const fs = moduleRef?.FS;
    if (!fs || typeof fs.readFile !== "function" || typeof fs.writeFile !== "function") {
        return;
    }
    const pathExists = (targetPath) => {
        try {
            return Boolean(fs.analyzePath?.(targetPath)?.exists);
        } catch (_) {
            return false;
        }
    };
    if (pathExists(VEROVIO_GLYPHNAMES_PATH) || !pathExists(VEROVIO_TUNING_GLYPHNAMES_PATH)) {
        return;
    }
    try {
        const glyphJson = fs.readFile(VEROVIO_TUNING_GLYPHNAMES_PATH, { encoding: "utf8" });
        if (glyphJson) {
            fs.writeFile(VEROVIO_GLYPHNAMES_PATH, glyphJson);
        }
    } catch (error) {
        console.warn(`Failed to alias Verovio glyphnames.json: ${error?.message || error}`);
    }
}

function configureVerovioToolkit(toolkit, moduleRef = window.verovio?.module) {
    if (!toolkit) {
        return null;
    }
    ensureVerovioResourceAliases(moduleRef);
    if (typeof toolkit.setResourcePath === "function") {
        try {
            toolkit.setResourcePath(VEROVIO_RESOURCE_PATH);
        } catch (error) {
            console.warn(`Failed to set Verovio resource path: ${error?.message || error}`);
        }
    }
    return toolkit;
}

function createVerovioToolkit() {
    if (!state.verovioReady || !window.verovio || typeof window.verovio.toolkit !== "function") {
        return null;
    }
    return configureVerovioToolkit(new window.verovio.toolkit(window.verovio.module), window.verovio.module);
}

function buildVerovioOptions(mode = "preview") {
    const measureCount = Math.max(resolveMeasureCount(state.currentScore), 1);
    if (mode === "viewer") {
        return {
            resourcePath: VEROVIO_RESOURCE_PATH,
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
        resourcePath: VEROVIO_RESOURCE_PATH,
        breaks: "auto",
        pageWidth: 2100,
        pageHeight: 1500,
        scale: 50,
        svgViewBox: true,
        adjustPageWidth: false,
        adjustPageHeight: false,
        spacingSystem: 18,
        spacingStaff: 10,
        header: "none",
        footer: "none",
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
        state.previewPageIndex = 0;
        renderPreviewPageNav();
        return;
    }

    const requestedPage = Math.max(0, Math.min(state.previewPageIndex || 0, Math.max(state.previewPageCount - 1, 0)));
    const rendered = await renderNotationTarget(els.scoreViewerEntry, { mode: "preview", pageIndex: requestedPage });
    state.previewPageCount = rendered.pageCount;
    state.previewPageIndex = Math.max(0, Math.min(requestedPage, Math.max(rendered.pageCount - 1, 0)));
    renderPreviewPageNav();
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
    tagRenderedSymbolsWithMxmlIndex(els.scoreViewerEntry);
    reapplyEditorSelectionHighlight(els.scoreViewerEntry);
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

function buildGuitarDisplayTokens(measures) {
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
    const fallbackLines = measures.length
        ? [{
            line_no: 1,
            line_label: "第 1 行",
            measure_start: measures[0].measure_no || 1,
            measure_end: measures[measures.length - 1].measure_no || measures.length,
            measure_count: measures.length,
            cadence: measures.length ? "open" : "resolved",
            measures,
        }]
        : [];
    const fallbackSections = measures.length
        ? [{
            section_no: 1,
            section_label: "A",
            section_title: "主歌",
            measure_start: fallbackLines[0]?.measure_start || 1,
            measure_end: fallbackLines[0]?.measure_end || 1,
            measure_count: measures.length,
            cadence: fallbackLines[fallbackLines.length - 1]?.cadence || "open",
            lines: fallbackLines,
        }]
        : [];
    const sourceSections = Array.isArray(result?.display_sections) && result.display_sections.length
        ? result.display_sections
        : Array.isArray(result?.sections) && result.sections.length
            ? result.sections
            : fallbackSections;
    const normalizeGuitarLineTokens = (tokens, lineMeasures) => {
        if (!Array.isArray(tokens) || !tokens.length) {
            return buildGuitarDisplayTokens(lineMeasures);
        }
        return tokens
            .filter((token) => token?.type !== "lyric")
            .map((token) => ({
                type: token?.type || "spacer",
                measureNo: Number(token?.measureNo || token?.measure_no || 0) || null,
                width: token?.width || "beat",
                symbol: token?.symbol || "",
                source: token?.source || "diatonic",
                beatInMeasure: Number(token?.beatInMeasure || token?.beat_in_measure || 1) || 1,
            }));
    };
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
                : fallbackLines;
        const lines = sourceLines.map((line, lineIndex) => {
            const lineMeasures = Array.isArray(line?.measures) ? line.measures : [];
            const measureSegments = lineMeasures.map((measure, measureIndex) => ({
                measureNo: Number(measure?.measure_no || measureIndex + 1),
                widthRem: resolveGuitarMeasureWidthRem(measure),
                chords: Array.isArray(measure?.chords) ? measure.chords : [],
            }));
            return {
                lineNo: Number(line?.line_no || lineIndex + 1),
                label: line?.line_label || `第 ${line?.measure_start || measureSegments[0]?.measureNo || 1}-${line?.measure_end || measureSegments[measureSegments.length - 1]?.measureNo || 1} 小节`,
                measureStart: Number(line?.measure_start || measureSegments[0]?.measureNo || 1),
                measureEnd: Number(line?.measure_end || measureSegments[measureSegments.length - 1]?.measureNo || 1),
                measureCount: Number(line?.measure_count || measureSegments.length || 0),
                cadence: line?.cadence || "open",
                measureSegments,
                tokens: normalizeGuitarLineTokens(line?.tokens, lineMeasures),
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
            class="secondary-button guitar-export-button instrument-pdf-export-button"
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
function splitGuitarLyricSegments(lyricText) {
    const normalized = String(lyricText || "").trim();
    if (!normalized) {
        return [];
    }
    if (/\s/.test(normalized)) {
        return normalized.split(/\s+/).filter((segment) => segment.length > 0);
    }
    if (/[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]/.test(normalized)) {
        const tokens = [];
        Array.from(normalized).forEach((char) => {
            if (!char.trim()) {
                return;
            }
            if (/[\p{P}\p{S}]/u.test(char) && tokens.length) {
                tokens[tokens.length - 1] += char;
                return;
            }
            tokens.push(char);
        });
        return tokens;
    }
    return [normalized];
}

function buildChordLyricPairs(allChords, lyricText) {
    const segments = splitGuitarLyricSegments(lyricText);
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
        return {
            chord: String(chord?.symbol || ""),
            lyric,
            source: chord?.source || "diatonic",
            measure_no: chord?.measure_no || null,
            beat_in_measure: chord?.beat_in_measure || null,
        };
    });
}

/**
 * Inline chord-over-lyric layout matching popular guitar sheet apps.
 * Each chord name floats above its corresponding lyric segment in a flex row
 * that wraps naturally – no horizontal scroll, no separate measure boxes.
 */
function renderGuitarLeadLineInline(line, { highlightedChordSymbol = "" } = {}) {
    const measureSegments = Array.isArray(line?.measureSegments) ? line.measureSegments : [];
    const tokens = Array.isArray(line?.tokens) && line.tokens.length
        ? line.tokens
        : buildGuitarDisplayTokens(
            measureSegments.map((measure, measureIndex) => ({
                measure_no: measure?.measureNo || measureIndex + 1,
                chords: Array.isArray(measure?.chords) ? measure.chords : [],
            }))
        );
    if (!tokens.length) {
        return '<div class="analysis-note">当前这一行还没有可展示的弹唱内容。</div>';
    }
    return `
        <div class="guitar-inline-chord-line">
            ${tokens.map((token) => {
                if (token?.type === "bar") {
                    return `
                        <span class="guitar-inline-bar">
                            <span class="guitar-inline-bar-mark">|</span>
                            <span class="guitar-inline-bar-number">${escapeHtmlText(String(token.measureNo || "--"))}</span>
                        </span>
                    `;
                }
                if (token?.type === "spacer") {
                    return `<span class="guitar-inline-spacer ${token.width === "measure" ? "measure" : "beat"}" aria-hidden="true"></span>`;
                }
                if (token?.type !== "chord") {
                    return "";
                }
                const anchorIdx = lookupAnchorMxmlIndexForChord(token.measureNo, token.beatInMeasure);
                const override = anchorIdx != null ? lookupChordOverrideForAnchor(anchorIdx) : null;
                const displaySymbol = override || token.symbol || "";
                const dataAttrs = anchorIdx != null ? `data-mxml-index="${anchorIdx}"` : "";
                return `
                    <span class="guitar-inline-chord-token${displaySymbol && highlightedChordSymbol === displaySymbol ? " is-highlighted" : ""}" ${dataAttrs}>
                        <span class="guitar-inline-chord ${escapeHtmlText(token.source || "diatonic")}${override ? " has-override" : ""}"
                              data-guitar-chord-symbol="${escapeHtmlAttribute(displaySymbol || "--")}"
                              role="button"
                              tabindex="0"
                              ${override ? `title="\u8986\u76d6\uff1a${escapeHtmlAttribute(override)}\uff08\u539f\u63a8\u5bfc\uff1a${escapeHtmlAttribute(token.symbol || "--")}\uff09"` : ""}>
                            ${escapeHtmlText(displaySymbol || "--")}
                        </span>
                    </span>
                `;
            }).join("")}
            <span class="guitar-inline-bar closing">
                <span class="guitar-inline-bar-mark">|</span>
            </span>
        </div>
    `;
}

function renderGuitarChordFlowLine(line, options = {}) {
    const measureCount = Number(line?.measureCount || line?.measureSegments?.length || 0);
    const cadence = localizeGuitarCadence(line?.cadence || "open");
    const summaryParts = [];
    if (measureCount > 0) {
        summaryParts.push(`${measureCount} 小节`);
    }
    if (cadence) {
        summaryParts.push(cadence);
    }
    return `
        <div class="guitar-lead-line-shell">
            <div class="guitar-lead-line-meta">
                <span class="guitar-lead-line-label">${escapeHtmlText(line?.label || "当前行")}</span>
                <span class="guitar-lead-line-summary">${escapeHtmlText(summaryParts.join(" · ") || "等待正文生成")}</span>
            </div>
            <div class="guitar-lead-line-scroll">
                <div class="guitar-lead-line">
                    ${renderGuitarLeadLineInline(line, options)}
                </div>
            </div>
        </div>
    `;
}

function lookupChordOverrideForAnchor(mxmlIndex) {
    const map = ensureHarmonyOverrideMap();
    if (!map) return null;
    for (const list of map.values()) {
        for (const entry of list) {
            if (entry.anchorIdx === mxmlIndex) return entry.symbol;
        }
    }
    return null;
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
                ${lines.map((line) => renderGuitarChordFlowLine(line, options)).join("")}
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

function renderGuitarAuxBlocks(songSheet) {
    const measures = Array.isArray(songSheet?.measures) ? songSheet.measures : [];
    const chords = Array.isArray(songSheet?.chords) ? songSheet.chords : [];
    const measureMarkup = measures.slice(0, 12).map((measure) => `
        <span class="guitar-measure-chip">
            <strong>${escapeHtmlText(String(measure.measure_no || "--"))}</strong>
            <span>${escapeHtmlText((measure.chords || []).map((chord) => chord.symbol || "--").join(" · ") || "--")}</span>
        </span>
    `).join("");
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
        </section>
    `;
}

function renderDebugToggleControl(instrumentType, expanded) {
    return `
        <div class="button-row">
            <button class="ghost-button guitar-debug-toggle-btn" data-${instrumentType}-toggle-debug type="button">${expanded ? "收起识谱过程" : "展开识谱过程"}</button>
        </div>
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
        return "∽";
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
        items.push('<span class="guzheng-jianpu-bend-mark">∽</span>');
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
        return "∽";
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
                    ? "↑"
                    : note?.special_fingering_candidate
                        ? "✱"
                        : note?.half_hole_candidate
                            ? "◐"
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

function renderTraditionalAnnotationLayerToggle(current) {
    const options = [
        { value: "basic", label: "基础正文" },
        { value: "technique", label: "技法层" },
    ];
    return `
        <div class="instrument-toggle traditional-annotation-toggle" role="tablist" aria-label="简谱标注层">
            ${options.map((option) => `
                <button class="instrument-toggle-button ${current === option.value ? "active" : ""}" data-jianpu-annotation-layer="${option.value}" role="tab" type="button" aria-selected="${current === option.value ? "true" : "false"}">${escapeHtmlText(option.label)}</button>
            `).join("")}
        </div>
    `;
}

function renderTraditionalPdfExportButton(instrumentType) {
    const normalizedInstrument = instrumentType === "dizi" ? "dizi" : "guzheng";
    const busy = isBusy(`traditional-export-${normalizedInstrument}`);
    return `
        <button
            class="secondary-button traditional-export-button instrument-pdf-export-button"
            data-traditional-export-format="pdf"
            type="button"
            ${busy ? "disabled" : ""}
        >${busy ? "导出中..." : "导出 PDF"}</button>
    `;
}

function renderTraditionalExportButtons(instrumentType) {
    const busy = isBusy(`traditional-export-${instrumentType}`);
    const buttons = [
        { format: "jianpu", label: "导出 jianpu-ly 源" },
        { format: "ly", label: "导出 LilyPond 源" },
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
    const layerLabels = {
        basic: "基础正文",
        technique: "技法层",
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
    // 颤音 / Trill — 用斜体 tr，符合通用记谱
    if (tags.includes("颤音/长音保持候选")) {
        items.push('<span class="traditional-jianpu-trill" title="颤音">tr</span>');
    }
    // 摇指 / Tremolo — 三斜线（与 LilyPond 三连斜杠一致）
    if (tags.includes("摇指候选") && instrumentType === "guzheng") {
        items.push('<span class="guzheng-jianpu-yao-mark" title="摇指">⫻</span>');
    }
    // 上下滑音 — 箭头线
    if (tags.includes("上滑音候选")) {
        items.push('<span class="guzheng-jianpu-slide-arc slide-up" title="上滑音">↗</span>');
    } else if (tags.includes("下滑音候选")) {
        items.push('<span class="guzheng-jianpu-slide-arc slide-down" title="下滑音">↘</span>');
    } else if (tags.includes("滑音候选")) {
        items.push('<span class="guzheng-jianpu-slide-arc traditional-slide-arc-plain" title="滑音">↗</span>');
    }
    // 换气点 — V 形换气符
    if (tags.includes("换气点")) {
        items.push('<span class="traditional-jianpu-breath-mark" title="换气">,</span>');
    }
    // 倚音 — dizi 专属
    if (tags.includes("倚音候选") && instrumentType === "dizi") {
        items.push('<span class="dizi-jianpu-grace-mark" title="倚音">𝆔</span>');
    }
    // 按音 — 古筝按弦用波浪线，和当前页面技法按钮保持一致
    if ((tags.includes("按音候选") || note?.press_note_candidate) && instrumentType === "guzheng") {
        items.push('<span class="guzheng-jianpu-bend-mark" title="按音">∽</span>');
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
    const explicitMxmlIndex = options?.mxmlIndex;
    const mxmlIndex = isRest
        ? null
        : (typeof explicitMxmlIndex === "number" ? explicitMxmlIndex : lookupJianpuMxmlIndex(note?.measure_no, note?.start_beat, note?.pitch));
    const techniqueBadges = mxmlIndex != null ? buildTechniqueBadgesForIndex(mxmlIndex) : "";
    const dataIndexAttr = mxmlIndex != null ? `data-mxml-index="${mxmlIndex}"` : "";
    const noteTitle = isRest
        ? "休止"
        : [
            note?.pitch || "--",
            `${formatBeat(note?.beats || 0)} 拍`,
            note?.annotation_hint || note?.fingering_hint || "",
        ].filter(Boolean).join(" · ");
    return `
        <span ${dataIndexAttr} class="guzheng-jianpu-note-group ${options.slurStart ? "slur-start" : ""} ${options.slurEnd ? "slur-end" : ""}">
            ${options.slurStart ? '<span class="guzheng-jianpu-slur-part slur-start"></span>' : ""}
            ${options.slurEnd ? '<span class="guzheng-jianpu-slur-part slur-end"></span>' : ""}
            ${techniqueBadges}
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
                                            ${measures.map((measure, measureIndex) => {
                                                const measureNo = Number(measure?.measure_no || 0);
                                                const items = buildGuzhengVisualNoteItems(measure);
                                                let pitchedPos = 0;
                                                const itemsMarkup = items.map((item) => {
                                                    const isRest = Boolean(item.note?.is_rest);
                                                    const enrichedItem = isRest
                                                        ? item
                                                        : Object.assign({}, item, { mxmlIndex: lookupJianpuMxmlIndexByPosition(measureNo, pitchedPos++) });
                                                    return renderTraditionalPaperNote(item.note, enrichedItem, model.instrumentType, model.annotationLayer);
                                                }).join("");
                                                return `
                                                <div class="guzheng-jianpu-measure ${measureIndex === measures.length - 1 ? "is-line-end" : ""}" data-edit-measure-no="${measureNo}">
                                                    <div class="guzheng-jianpu-measure-notes">
                                                        ${measureRepeatLookup.get(measureNo)
                                                            ? '<span class="guzheng-jianpu-repeat-sign" title="同前小节">〃</span>'
                                                            : (itemsMarkup || '<span class="guzheng-jianpu-note-group"><span class="guzheng-jianpu-note is-rest"><span class="guzheng-jianpu-ornaments"><span class="guzheng-jianpu-ornament-placeholder"></span></span><span class="guzheng-jianpu-octave-top">&nbsp;</span><span class="guzheng-jianpu-glyph"><span class="guzheng-jianpu-digit">0</span></span><span class="guzheng-jianpu-underlines"><span class="guzheng-jianpu-underline guzheng-jianpu-underline-empty"></span></span><span class="guzheng-jianpu-octave-bottom">&nbsp;</span><span class="guzheng-jianpu-press-text">&nbsp;</span></span></span>')}
                                                    </div>
                                                    <span class="guzheng-jianpu-bar"></span>
                                                </div>
                                            `;
                                            }).join("")}
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
                    ${renderTraditionalAnnotationLayerToggle(model.annotationLayer)}
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
                    ${renderTraditionalAnnotationLayerToggle(model.annotationLayer)}
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
                        </div>
                    </div>
                    <div class="guitar-sheet-metrics">
                        ${metricCard("Capo", escapeHtmlText(songSheet.meta.capoText))}
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
                            <span class="guitar-meta-subtle">${viewMode === "print" ? "打印模式会收紧边栏并按更稳的版式分页。" : "屏幕模式允许局部横向滚动，优先保证和弦与小节分隔保持清晰。"}</span>
                        </div>
                        <div class="guitar-lead-sections">
                            ${songSheet.sections.map((section) => renderGuitarLeadSection(section, { highlightedChordSymbol })).join("") || '<div class="analysis-note">当前还没有可展示的弹唱谱正文。</div>'}
                        </div>
                    </section>
                    ${renderGuitarAuxBlocks(songSheet)}
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
        if (mode === "preview") {
            ensureEditorIndexMap(toolkit);
        }
        const pageCount = Math.max(Number(toolkit.getPageCount() || 0), 1);
        const clampedPage = Math.min(Math.max(Number(pageIndex || 0), 0), pageCount - 1);
        ensureRenderedPageSymbolOffsets({ mode, toolkit, pageCount });
        if (mode === "viewer") {
            state.scorePageIndex = clampedPage;
        }
        const svgMarkup = toolkit.renderToSVG(clampedPage + 1);
        const markup = `<div class="verovio-stage ${mode === "viewer" ? "viewer" : "preview"}" data-page-index="${clampedPage}" data-render-mode="${escapeHtmlAttribute(mode)}"><div class="verovio-pane">${svgMarkup}</div></div>`;
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
    ensureRenderedPageSymbolOffsets({ mode: "viewer", toolkit, pageCount: actualPageCount });
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
        <section class="score-paper-sheet ${role}${interactive ? " is-live" : ""}" data-page-index="${pagePayload.pageIndex}" data-render-mode="viewer">
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
    tagRenderedSymbolsWithMxmlIndex(els.scoreViewerCanvas);
    syncSelectionHighlightToCurrentSelection();
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
        tagRenderedSymbolsWithMxmlIndex(els.scoreViewerCanvas);
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
    if (els.scoreTitleDisplay) {
        els.scoreTitleDisplay.textContent = score
            ? score.title || "未命名乐谱"
            : guitarMode
                ? "尚未生成吉他弹唱谱"
                : guzhengMode
                    ? "尚未生成古筝谱"
                    : diziMode
                        ? "尚未生成笛子谱"
                        : "尚未载入乐谱";
    }
    if (els.scoreIdBadge) {
        els.scoreIdBadge.textContent = isPianoMode() && score ? score.score_id : "--";
    }
    if (els.projectIdBadge) {
        els.projectIdBadge.textContent = isPianoMode() && score ? score.project_id : "--";
    }
    if (els.scoreVersionBadge) {
        els.scoreVersionBadge.textContent = isPianoMode() && score ? score.version : "--";
    }
    els.tempoDisplay.textContent = score ? score.tempo : "--";
    els.timeDisplay.textContent = score ? score.time_signature : "--";
    els.keyDisplay.textContent = score ? score.key || score.key_signature || "--" : "--";
    els.measureCountDisplay.textContent = isPianoMode()
        ? score
            ? resolveMeasureCount(score)
            : "--"
        : (Array.isArray(score?.measures) ? score.measures.length : "--");
    if (els.selectedNoteSummary) {
        els.selectedNoteSummary.textContent = isPianoMode()
            ? state.editorSelectedMxmlIndex != null
                ? "当前已在谱面中高亮一个音符或休止符。"
                : defaultSelectionHint()
            : guzhengMode
                ? "当前页面显示古筝专属结果页。若需刷新简谱、弦位或技法建议，请重新生成古筝谱。"
                : diziMode
                    ? "当前页面显示笛子专属结果页。若需刷新简谱、指法或技法建议，请重新生成笛子谱。"
                    : "当前页面显示吉他专属结果页。若需刷新弹唱谱信息，请重新生成吉他弹唱谱。";
    }
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
    const host = event.currentTarget;
    const isFromViewer = host === els.scoreViewerCanvas;
    if (
        isFromViewer && (
            state.viewerGesture?.dragging ||
            state.viewerTransition.phase === "dragging" ||
            Date.now() < (state.viewerSuppressClickUntil || 0)
        )
    ) {
        return;
    }
    const clickedSymbol = event.target.closest(".note, .rest");
    if (clickedSymbol) {
        const selection = updateEditorSelectionFromSymbol(clickedSymbol, host);
        if (!selection?.ok) {
            state.selectedNotationElementId = null;
            syncSelectionHighlightToCurrentSelection();
            if (els.selectedNoteSummary) {
                els.selectedNoteSummary.textContent = "当前音符无法定位到 MusicXML，请尝试点击相邻音符，或使用上一个/下一个按钮。";
            }
            setAppStatus("当前音符无法定位到 MusicXML，请尝试点击相邻音符，或使用上一个/下一个按钮。", true);
            return;
        }
        state.selectedNotationElementId = clickedSymbol.id || null;
        syncSelectionHighlightToCurrentSelection();
        if (els.selectedNoteSummary) {
            els.selectedNoteSummary.textContent = "当前已在谱面中高亮一个音符或休止符。";
        }
    } else {
        state.selectedNotationElementId = null;
        clearEditorSelection();
        syncSelectionHighlightToCurrentSelection();
        if (els.selectedNoteSummary) {
            els.selectedNoteSummary.textContent = defaultSelectionHint();
        }
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
    if (els.pianoAnalysisGrid) {
        if (els.pianoAnalysisGrid.style && typeof els.pianoAnalysisGrid.style === "object") {
            els.pianoAnalysisGrid.style.display = guitarMode || guzhengMode || diziMode ? "none" : "";
        } else {
            els.pianoAnalysisGrid.style = { display: guitarMode || guzhengMode || diziMode ? "none" : "" };
        }
    }
    els.guzhengDebugPanel.hidden = !guzhengMode;
    els.guitarDebugPanel.hidden = !guitarMode;
    els.diziDebugPanel.hidden = !diziMode;
    if (!guzhengMode && els.guzhengDebugPanel) {
        els.guzhengDebugPanel.innerHTML = "";
    }
    if (!guitarMode && els.guitarDebugPanel) {
        els.guitarDebugPanel.innerHTML = "";
    }
    if (!diziMode && els.diziDebugPanel) {
        els.diziDebugPanel.innerHTML = "";
    }
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
    renderSeparateTracksPanel();
}

function renderGuzhengDebugPanel() {
    const result = state.guzhengResult;
    if (!result) {
        els.guzhengDebugPanel.innerHTML = "";
        return;
    }

    const selectedTrack = result.melody_track || null;
    const keyDetection = result.key_detection || null;
    const warnings = Array.isArray(result.warnings) ? result.warnings : [];
    const techniqueCounts = result.technique_summary?.counts || {};
    const pentatonicSummary = result.pentatonic_summary || {};
    const keyCandidates = Array.isArray(keyDetection?.candidates) ? keyDetection.candidates : [];

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

    els.guzhengDebugPanel.innerHTML = `
        <div class="guitar-debug-shell">
            <div class="analysis-grid">
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
    if (!result) {
        els.diziDebugPanel.innerHTML = "";
        return;
    }
    if (!isCurrentResult) {
        const tip = `当前已切到 ${localizeFluteType(state.diziFluteType)}，请重新生成笛子谱，让指法和数字谱按新的笛型关系重算。`;
        els.diziDebugPanel.innerHTML = `
            <div class="guitar-debug-shell">
                <div class="analysis-note">${escapeHtmlText(tip)}</div>
            </div>
        `;
        return;
    }

    const selectedTrack = result.melody_track || null;
    const keyDetection = result.key_detection || null;
    const warnings = Array.isArray(result.warnings) ? result.warnings : [];
    const techniqueCounts = result.technique_summary?.counts || {};
    const playabilitySummary = result.playability_summary || {};
    const keyCandidates = Array.isArray(keyDetection?.candidates) ? keyDetection.candidates : [];

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

    els.diziDebugPanel.innerHTML = `
        <div class="guitar-debug-shell">
            <div class="analysis-grid">
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
        els.guitarDebugPanel.innerHTML = "";
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
        : "";

    els.guitarDebugPanel.innerHTML = `
        <div class="guitar-debug-shell">
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
    return `
        <div class="analysis-track-card">
            <div class="analysis-track-icon ${slug}">${escapeHtmlText(trackGlyph(name))}</div>
            <div>
                <div class="analysis-track-name">${escapeHtmlText(localizeTrackName(name))}</div>
                <div class="analysis-track-file">${escapeHtmlText(track.file_name || "")}</div>
            </div>
            <div class="analysis-track-meta">${formatSeconds(track.duration)}</div>
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
        score_build: "乐谱生成",
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
        await saveUserHistory({
            type: "transcription",
            resource_id: String(created.export_record_id || state.currentScore.score_id || activeHistoryResourceId("score_export")),
            title: `导出乐谱：${created.file_name || state.currentScore.title || state.currentScore.score_id}`,
            metadata: {
                source: "score_export",
                score_id: state.currentScore.score_id,
                export_record_id: created.export_record_id || "",
                format: created.format || els.exportFormatSelect.value,
                file_name: created.file_name || "",
                download_url: created.download_api_url || created.download_url || "",
            },
        });
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
    const hasScoreFile = Boolean(els.scoreMusicxmlFileInput?.files?.length);
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
    if (els.separateTracksBtn) {
        els.separateTracksBtn.disabled = !hasAnalysisFile || isBusy("separate-tracks");
    }
    if (els.refreshAudioLogsBtn) {
        els.refreshAudioLogsBtn.disabled = isBusy("audio-logs");
    }
    if (els.applyScoreSettingsBtn) {
        els.applyScoreSettingsBtn.disabled = customMode || !hasScore || isBusy("score-settings");
    }
    if (els.undoBtn) {
        els.undoBtn.disabled = customMode || !hasScore || isBusy("undo-action");
    }
    if (els.redoBtn) {
        els.redoBtn.disabled = customMode || !hasScore || isBusy("redo-action");
    }
    if (els.downloadMusicxmlBtn) {
        els.downloadMusicxmlBtn.disabled = customMode || !hasScore;
    }
    if (els.refreshScoreBtn) {
        els.refreshScoreBtn.disabled =
            customMode || !hasScore || isBusy(`score-load-${state.currentScore?.score_id || state.selectedScoreId}`);
    }
    if (els.replaceScoreFromFileBtn) {
        els.replaceScoreFromFileBtn.disabled = customMode || !hasScore || !hasScoreFile || isBusy("score-file-replace");
    }
    if (els.loadScoreFileIntoEditorBtn) {
        els.loadScoreFileIntoEditorBtn.disabled = customMode || !hasScoreFile;
    }
    const exportContext = resolveActivePdfExportContext();
    els.exportScorePdfBtn.disabled = !exportContext.hasExportable || isBusy(exportContext.busyKey);
    els.exportScorePdfBtn.textContent = isBusy(exportContext.busyKey) ? "导出中..." : "导出 PDF";
    if (els.openScoreViewerBtn) {
        els.openScoreViewerBtn.disabled = customMode || !hasScore;
    }
    els.closeScoreViewerBtn.disabled = !state.scoreViewerOpen;
    els.scoreViewerPagePrevBtn.disabled = !canGoPrevPage;
    els.scoreViewerPageNextBtn.disabled = !canGoNextPage;
    els.createExportBtn.disabled = customMode || !hasScore || isBusy("create-export");
    els.refreshExportsBtn.disabled = customMode || !hasScore || isBusy("load-exports");
    els.regenerateSelectedExportBtn.disabled = !hasExport || isBusy("regenerate-export");
    els.downloadSelectedExportBtn.disabled = !hasExport || !state.selectedExportDetail?.exists;
    els.deleteSelectedExportBtn.disabled = !hasExport || isBusy("delete-export");
    if (els.pitchDetectBtn) {
        els.pitchDetectBtn.disabled = isBusy("pitch-detect") || isBusy("pitch-detect-score");
    }
    if (els.pitchDetectAndScoreBtn) {
        els.pitchDetectAndScoreBtn.disabled = isBusy("pitch-detect") || isBusy("pitch-detect-score");
    }
    if (els.refreshWorkbenchBtn) {
        els.refreshWorkbenchBtn.disabled = state.busyKeys.size > 0;
    }
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

/* ================================================================
 * Manual edit workbench (MVP — piano only)
 * Operates on state.currentScore.musicxml. Each mutation produces a
 * new MusicXML string and goes through patchScoreMusicxml so the
 * backend snapshot/undo/redo machinery works unchanged.
 * ============================================================== */

const EDIT_DURATION_TYPES = {
    whole: { quartersPerNote: 4 },
    half: { quartersPerNote: 2 },
    quarter: { quartersPerNote: 1 },
    eighth: { quartersPerNote: 0.5 },
    "16th": { quartersPerNote: 0.25 },
};

const EDIT_TYPE_LABELS_ZH = {
    whole: "全音符",
    half: "二分音符",
    quarter: "四分音符",
    eighth: "八分音符",
    "16th": "十六分音符",
    "32nd": "三十二分音符",
};

const EDIT_STEP_PC = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const EDIT_PC_TO_STEP_ALTER = [
    ["C", 0], ["C", 1], ["D", 0], ["D", 1], ["E", 0], ["F", 0],
    ["F", 1], ["G", 0], ["G", 1], ["A", 0], ["A", 1], ["B", 0],
];

function parseMusicXmlDocument(xmlString) {
    const doc = new DOMParser().parseFromString(String(xmlString || ""), "application/xml");
    if (doc.querySelector("parsererror")) {
        return null;
    }
    return doc;
}

function listMxmlNoteElements(doc) {
    return doc ? Array.from(doc.getElementsByTagName("note")) : [];
}

function locateMxmlNoteByIndex(doc, index) {
    const notes = listMxmlNoteElements(doc);
    if (index == null || index < 0 || index >= notes.length) {
        return null;
    }
    return notes[index];
}

function buildEditorIndexMapKey(score) {
    return `${score?.score_id || "score"}:${score?.version || 0}:${score?.musicxml?.length || 0}`;
}

function ensureEditorIndexMap(toolkit) {
    /* Build a meiId → mxmlIndex map by walking BOTH structures per-measure.
       The previous flat parallel walk drifted off whenever Verovio inserted
       layer-alignment rests or chord/grace differences shifted counts; once
       drift starts every subsequent click maps to the wrong note. By zipping
       per measure, alignment errors are local and don't propagate. */
    if (!state.currentScore?.musicxml || !toolkit?.getMEI) {
        state.editorIndexMap = null;
        state.editorIndexMapKey = "";
        return null;
    }
    const key = buildEditorIndexMapKey(state.currentScore);
    if (state.editorIndexMap && state.editorIndexMapKey === key) {
        return state.editorIndexMap;
    }
    let meiXml = "";
    try {
        meiXml = toolkit.getMEI({ scoreBased: true }) || "";
    } catch (_) {
        try {
            meiXml = toolkit.getMEI() || "";
        } catch (_) {
            meiXml = "";
        }
    }
    if (!meiXml) {
        state.editorIndexMap = null;
        state.editorIndexMapKey = "";
        return null;
    }
    const meiDoc = new DOMParser().parseFromString(meiXml, "application/xml");
    if (meiDoc.querySelector("parsererror")) {
        state.editorIndexMap = null;
        state.editorIndexMapKey = "";
        return null;
    }
    const mxmlDoc = parseMusicXmlDocument(state.currentScore.musicxml);
    if (!mxmlDoc) {
        state.editorIndexMap = null;
        state.editorIndexMapKey = "";
        return null;
    }

    // 1) MusicXML side: indices grouped by measure number, in document order.
    const mxmlNotes = listMxmlNoteElements(mxmlDoc);
    const mxmlByMeasure = new Map();
    let unnumberedCounter = 0;
    mxmlNotes.forEach((noteEl, idx) => {
        const measureEl = noteEl.parentNode;
        let measureNo = Number(measureEl?.getAttribute("number") || 0);
        if (!measureNo) {
            measureNo = ++unnumberedCounter;
        }
        if (!mxmlByMeasure.has(measureNo)) mxmlByMeasure.set(measureNo, []);
        mxmlByMeasure.get(measureNo).push(idx);
    });
    const mxmlMeasureNumbers = Array.from(mxmlByMeasure.keys());

    // 2) MEI side: walk <measure> elements in document order.
    const meiMeasures = Array.from(meiDoc.getElementsByTagName("*")).filter(
        (el) => el.localName === "measure",
    );

    const map = new Map();
    meiMeasures.forEach((meiMeasure, measurePos) => {
        // Try MEI's @n first (matches MusicXML measure number); fall back to position.
        const meiNAttr = meiMeasure.getAttribute("n") || meiMeasure.getAttribute("label") || "";
        const candidateNum = Number(meiNAttr);
        let mxmlIndices;
        if (Number.isFinite(candidateNum) && candidateNum > 0 && mxmlByMeasure.has(candidateNum)) {
            mxmlIndices = mxmlByMeasure.get(candidateNum);
        } else if (measurePos < mxmlMeasureNumbers.length) {
            mxmlIndices = mxmlByMeasure.get(mxmlMeasureNumbers[measurePos]);
        }
        if (!mxmlIndices) return;

        // Walk MEI note/rest descendants of this measure in document order.
        const meiSymbols = Array.from(meiMeasure.getElementsByTagName("*")).filter(
            (el) => el.localName === "note" || el.localName === "rest",
        );
        const limit = Math.min(meiSymbols.length, mxmlIndices.length);
        for (let i = 0; i < limit; i += 1) {
            const meiId = meiSymbols[i].getAttribute("xml:id")
                || meiSymbols[i].getAttributeNS("http://www.w3.org/XML/1998/namespace", "id");
            if (meiId) {
                map.set(meiId, mxmlIndices[i]);
            }
        }
    });

    state.editorIndexMap = map;
    state.editorIndexMapKey = key;
    return map;
}

function tagRenderedSymbolsWithMxmlIndex(host) {
    if (!host || !state.currentScore?.musicxml) {
        return;
    }
    const map = state.editorIndexMap;
    const symbolNodes = host.querySelectorAll(".verovio-pane .note, .verovio-pane .rest");
    const renderMode = host === els.scoreViewerCanvas ? "viewer" : "preview";
    const renderedPageCount = renderMode === "viewer" ? state.viewerPageCount : state.previewPageCount;
    if (!symbolNodes.length) return;

    // 1) Primary: id-based lookup via the MEI-anchored map (works across pages).
    let coveredCount = 0;
    if (map && map.size) {
        symbolNodes.forEach((node) => {
            const id = node.getAttribute("id");
            if (id && map.has(id)) {
                node.setAttribute("data-mxml-index", String(map.get(id)));
                coveredCount += 1;
            } else {
                node.removeAttribute("data-mxml-index");
            }
        });
        if (coveredCount === symbolNodes.length) return;
    }

    // 2) Per-measure fallback by SVG `data-n` attribute. Verovio emits
    //    <g class="measure" data-n="N"> on each measure; pair its note/rest
    //    descendants positionally with that MusicXML measure's notes. This
    //    keeps multi-page clicks working even when the MEI map is partial.
    const doc = parseMusicXmlDocument(state.currentScore.musicxml);
    if (!doc) return;
    const mxmlByMeasure = new Map();
    let unnumberedCounter = 0;
    listMxmlNoteElements(doc).forEach((noteEl, idx) => {
        const measureEl = noteEl.parentNode;
        let measureNo = Number(measureEl?.getAttribute?.("number") || 0);
        if (!measureNo) measureNo = ++unnumberedCounter;
        if (!mxmlByMeasure.has(measureNo)) mxmlByMeasure.set(measureNo, []);
        mxmlByMeasure.get(measureNo).push(idx);
    });
    const svgMeasures = host.querySelectorAll(".verovio-pane .measure");
    let perMeasureCovered = 0;
    svgMeasures.forEach((svgMeasure) => {
        const candidate = svgMeasure.getAttribute("data-n") || svgMeasure.getAttribute("n") || "";
        const measureNo = Number(candidate);
        const indices = Number.isFinite(measureNo) && measureNo > 0
            ? mxmlByMeasure.get(measureNo)
            : null;
        if (!indices) return;
        const inMeasure = svgMeasure.querySelectorAll(".note, .rest");
        const limit = Math.min(inMeasure.length, indices.length);
        for (let i = 0; i < limit; i += 1) {
            if (!inMeasure[i].getAttribute("data-mxml-index")) {
                inMeasure[i].setAttribute("data-mxml-index", String(indices[i]));
                perMeasureCovered += 1;
            }
        }
    });
    if (perMeasureCovered + coveredCount >= symbolNodes.length) return;

    // 3) Last-resort flat fallback (single-page only — drifts on page breaks).
    if (renderedPageCount && renderedPageCount > 1) return;
    const noteElements = listMxmlNoteElements(doc);
    const limit = Math.min(noteElements.length, symbolNodes.length);
    for (let i = 0; i < limit; i += 1) {
        if (!symbolNodes[i].getAttribute("data-mxml-index")) {
            symbolNodes[i].setAttribute("data-mxml-index", String(i));
        }
    }
}

function readSymbolMxmlIndex(symbol) {
    if (!symbol) {
        return null;
    }
    const raw = symbol.getAttribute("data-mxml-index");
    if (raw == null) {
        return null;
    }
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
}

function buildRenderedPageSymbolOffsetCacheKey(mode, pageCount) {
    const normalizedMode = mode === "viewer" ? "viewer" : "preview";
    const baseKey = normalizedMode === "viewer"
        ? state.viewerPreparedKey || buildViewerPreparedKey(state.currentScore)
        : buildEditorIndexMapKey(state.currentScore);
    return `${normalizedMode}:${baseKey}:${Math.max(Number(pageCount || 0), 0)}`;
}

function countRenderedSymbolMarkup(svgMarkup) {
    if (!svgMarkup) {
        return 0;
    }
    const matches = String(svgMarkup).match(/<[^>]+class="[^"]*\b(?:note|rest)\b[^"]*"/g);
    return Array.isArray(matches) ? matches.length : 0;
}

function ensureRenderedPageSymbolOffsets({ mode = "preview", toolkit, pageCount = 0 } = {}) {
    if (!toolkit || pageCount <= 0) {
        return [];
    }
    const normalizedMode = mode === "viewer" ? "viewer" : "preview";
    const cacheKey = buildRenderedPageSymbolOffsetCacheKey(normalizedMode, pageCount);
    const cachedOffsets = normalizedMode === "viewer" ? state.viewerPageSymbolOffsets : state.previewPageSymbolOffsets;
    const cachedKey = normalizedMode === "viewer" ? state.viewerPageSymbolOffsetsKey : state.previewPageSymbolOffsetsKey;
    if (Array.isArray(cachedOffsets) && cachedOffsets.length === pageCount && cachedKey === cacheKey) {
        return cachedOffsets;
    }

    const offsets = [];
    let runningOffset = 0;
    for (let pageIndex = 0; pageIndex < pageCount; pageIndex += 1) {
        offsets.push(runningOffset);
        runningOffset += countRenderedSymbolMarkup(toolkit.renderToSVG(pageIndex + 1));
    }

    if (normalizedMode === "viewer") {
        state.viewerPageSymbolOffsets = offsets;
        state.viewerPageSymbolOffsetsKey = cacheKey;
    } else {
        state.previewPageSymbolOffsets = offsets;
        state.previewPageSymbolOffsetsKey = cacheKey;
    }
    return offsets;
}

function resolveRenderedSymbolPageContext(symbol, host) {
    if (!symbol) {
        return null;
    }
    const pageScope = symbol.closest?.("[data-page-index]") || null;
    const rawPageIndex = pageScope?.getAttribute?.("data-page-index")
        ?? host?.dataset?.verovioPageIndex
        ?? (host === els.scoreViewerCanvas ? state.scorePageIndex : state.previewPageIndex);
    const pageIndex = Number(rawPageIndex);
    if (!Number.isFinite(pageIndex) || pageIndex < 0) {
        return null;
    }
    const renderMode = pageScope?.getAttribute?.("data-render-mode")
        || host?.dataset?.verovioRenderMode
        || (host === els.scoreViewerCanvas ? "viewer" : "preview");
    return {
        pageIndex,
        renderMode: renderMode === "viewer" ? "viewer" : "preview",
        pageScope: pageScope || host || null,
    };
}

function resolveRenderedSymbolPageBaseOffset(symbol, host) {
    const context = resolveRenderedSymbolPageContext(symbol, host);
    if (!context) {
        return null;
    }
    const pageCount = context.renderMode === "viewer" ? state.viewerPageCount : state.previewPageCount;
    const cacheKey = buildRenderedPageSymbolOffsetCacheKey(context.renderMode, pageCount);
    const offsets = context.renderMode === "viewer" ? state.viewerPageSymbolOffsets : state.previewPageSymbolOffsets;
    const currentKey = context.renderMode === "viewer" ? state.viewerPageSymbolOffsetsKey : state.previewPageSymbolOffsetsKey;
    if (!Array.isArray(offsets) || context.pageIndex >= offsets.length) {
        return null;
    }
    if (currentKey && currentKey !== cacheKey) {
        return null;
    }
    return {
        baseOffset: Number(offsets[context.pageIndex] || 0),
        pageScope: context.pageScope,
    };
}

function changePreviewPage(direction) {
    const total = Math.max(state.previewPageCount || 0, 1);
    if (total <= 1) {
        return;
    }
    const next = Math.max(0, Math.min((state.previewPageIndex || 0) + direction, total - 1));
    if (next === state.previewPageIndex) {
        return;
    }
    state.previewPageIndex = next;
    renderPreviewPageNav();
    scheduleNotationRender();
    renderEditWorkbench();
}

function renderPreviewPageNav() {
    if (!els.previewPageNav) {
        return;
    }
    const total = Math.max(state.previewPageCount || 0, 0);
    const showNav = isPianoMode() && Boolean(state.currentScore) && total > 1;
    els.previewPageNav.hidden = !showNav;
    if (!showNav) {
        return;
    }
    const current = Math.max(0, Math.min(state.previewPageIndex || 0, total - 1));
    if (els.previewPageStatus) {
        els.previewPageStatus.textContent = `第 ${current + 1} / ${total} 页`;
    }
    if (els.previewPagePrevBtn) {
        els.previewPagePrevBtn.disabled = current === 0;
    }
    if (els.previewPageNextBtn) {
        els.previewPageNextBtn.disabled = current >= total - 1;
    }
}

function reapplyEditorSelectionHighlight(host) {
    if (!host) {
        return;
    }
    const index = state.editorSelectedMxmlIndex;
    if (index == null) {
        return;
    }
    const selector = `.verovio-pane [data-mxml-index="${index}"]`;
    const target = host.querySelector(selector);
    if (target) {
        target.classList.add("is-selected");
    }
}

function resolveSymbolMxmlIndexByPosition(symbol, host) {
    /* Strict positional fallback for symbols that are missing MEI tags.

       Single-page renders can still rely on flat document order. On
       multi-page renders we only trust measure-local ordering when the
       rendered measure carries a stable number; otherwise we give up
       instead of guessing across page breaks. */
    if (!symbol || !state.currentScore?.musicxml) return null;
    const stage = host
        || symbol.closest(".verovio-stage")
        || symbol.closest(".verovio-pane")?.parentNode
        || symbol.ownerSVGElement?.parentNode
        || els.scoreViewerEntry;
    if (!stage) return null;

    const allSymbols = Array.from(stage.querySelectorAll(".note, .rest"));
    const symbolPos = allSymbols.indexOf(symbol);
    if (symbolPos < 0) return null;

    const doc = parseMusicXmlDocument(state.currentScore.musicxml);
    if (!doc) return null;
    const mxmlNotes = listMxmlNoteElements(doc);
    if (!mxmlNotes.length) return null;
    const renderedPageContext = resolveRenderedSymbolPageContext(symbol, stage);
    const renderedPageCount = renderedPageContext?.renderMode === "viewer"
        ? state.viewerPageCount
        : state.previewPageCount;

    // Single-page renders: SVG document order tracks MusicXML 1:1.
    if ((renderedPageCount || 1) <= 1) {
        return symbolPos < mxmlNotes.length ? symbolPos : null;
    }

    // Multi-page: prefer measure-anchored mapping when Verovio gave us @n.
    const measure = symbol.closest(".measure");
    const measureLabel = Number(
        measure?.getAttribute?.("data-n") || measure?.getAttribute?.("n") || 0,
    );
    if (measure && Number.isFinite(measureLabel) && measureLabel > 0) {
        const inMeasure = Array.from(measure.querySelectorAll(".note, .rest"));
        const localPos = inMeasure.indexOf(symbol);
        if (localPos >= 0) {
            const indices = [];
            let unnumbered = 0;
            mxmlNotes.forEach((noteEl, idx) => {
                const m = Number(noteEl.parentNode?.getAttribute?.("number") || 0) || ++unnumbered;
                if (m === measureLabel) indices.push(idx);
            });
            if (localPos < indices.length) return indices[localPos];
        }
    }

    const pageContext = resolveRenderedSymbolPageBaseOffset(symbol, stage);
    if (pageContext?.pageScope) {
        const pageSymbols = Array.from(pageContext.pageScope.querySelectorAll(".note, .rest"));
        const localPos = pageSymbols.indexOf(symbol);
        const resolvedIndex = localPos >= 0 ? pageContext.baseOffset + localPos : null;
        if (resolvedIndex != null && resolvedIndex < mxmlNotes.length) {
            return resolvedIndex;
        }
    }

    return null;
}

function updateEditorSelectionFromSymbol(symbol, host) {
    if (!symbol) {
        clearEditorSelection();
        return { ok: false, reason: "missing-symbol" };
    }
    // Primary: use the rendered symbol's explicit MusicXML tag when present.
    let resolvedIndex = readSymbolMxmlIndex(symbol);
    if (resolvedIndex == null && host) {
        // Secondary: rebuild tags once and retry before any positional guess.
        tagRenderedSymbolsWithMxmlIndex(host);
        resolvedIndex = readSymbolMxmlIndex(symbol);
    }
    if (resolvedIndex == null) {
        // Tertiary: strict positional fallback.
        resolvedIndex = resolveSymbolMxmlIndexByPosition(symbol, host);
    }
    if (resolvedIndex == null || !Number.isFinite(resolvedIndex)) {
        clearEditorSelection();
        return { ok: false, reason: "unmapped" };
    }
    state.editorSelectedMxmlIndex = resolvedIndex;
    symbol.setAttribute("data-mxml-index", String(resolvedIndex));
    state.editorSelectedKind = symbol.classList.contains("rest") ? "rest" : "note";
    renderEditWorkbench();
    return { ok: true, index: resolvedIndex, kind: state.editorSelectedKind };
}

function clearEditorSelection() {
    resetEditorSelectionState();
    syncSelectionHighlightToCurrentSelection();
    renderEditWorkbench();
}

function resetEditorSelectionState() {
    state.editorSelectedMxmlIndex = null;
    state.editorSelectedKind = null;
    state.editorSelectedSummary = "";
    state.selectedNotationElementId = null;
}

function describeMxmlNote(noteEl) {
    if (!noteEl) {
        return "";
    }
    const measureEl = noteEl.closest("measure");
    const measureNumber = measureEl?.getAttribute("number") || "?";
    const isRest = !!noteEl.querySelector("rest");
    let pitchText = "休止符";
    if (!isRest) {
        const pitch = noteEl.querySelector("pitch");
        if (pitch) {
            const step = pitch.querySelector("step")?.textContent?.trim() || "?";
            const alter = Number(pitch.querySelector("alter")?.textContent || 0);
            const octave = pitch.querySelector("octave")?.textContent?.trim() || "?";
            const acc = alter === 1 ? "♯" : alter === 2 ? "𝄪" : alter === -1 ? "♭" : alter === -2 ? "𝄫" : "";
            pitchText = `${step}${acc}${octave}`;
        }
    }
    const type = noteEl.querySelector("type")?.textContent?.trim() || "";
    const dotCount = noteEl.querySelectorAll("dot").length;
    const typeLabel = EDIT_TYPE_LABELS_ZH[type] || type || "";
    const dotLabel = dotCount ? "·".repeat(dotCount) + "（附点）" : "";
    return `第 ${measureNumber} 小节 · ${pitchText}${typeLabel ? " · " + typeLabel : ""}${dotLabel ? " " + dotLabel : ""}`;
}

function getEditorTotalNotes() {
    const xml = state.currentScore?.musicxml;
    if (!xml) return 0;
    const doc = parseMusicXmlDocument(xml);
    return doc ? listMxmlNoteElements(doc).length : 0;
}

function stepEditorSelection(direction) {
    const total = getEditorTotalNotes();
    if (total <= 0) {
        return;
    }
    const current = state.editorSelectedMxmlIndex;
    let nextIndex;
    if (current == null) {
        nextIndex = direction >= 0 ? 0 : total - 1;
    } else {
        nextIndex = Math.max(0, Math.min(current + direction, total - 1));
    }
    if (nextIndex === current) {
        return;
    }
    state.editorSelectedMxmlIndex = nextIndex;
    state.selectedNotationElementId = null;
    const doc = parseMusicXmlDocument(state.currentScore?.musicxml || "");
    const noteEl = locateMxmlNoteByIndex(doc, nextIndex);
    state.editorSelectedKind = noteEl?.querySelector("rest") ? "rest" : "note";
    syncSelectionHighlightToCurrentSelection();
    if (els.selectedNoteSummary) {
        els.selectedNoteSummary.textContent = "当前已在谱面中高亮一个音符或休止符。";
    }
    renderEditWorkbench();
}

function syncSelectionHighlightToCurrentSelection() {
    const idx = state.editorSelectedMxmlIndex;
    [els.scoreViewerEntry, els.scoreViewerCanvas].forEach((host) => {
        if (!host) {
            return;
        }
        host.querySelectorAll(".note.is-selected, .rest.is-selected").forEach((el) => {
            el.classList.remove("is-selected");
        });
        if (idx == null) {
            return;
        }
        const target = host.querySelector(`.verovio-pane [data-mxml-index="${idx}"]`);
        if (target) {
            target.classList.add("is-selected");
            return;
        }
        if (host === els.scoreViewerCanvas && state.selectedNotationElementId) {
            const safeId = window.CSS?.escape
                ? window.CSS.escape(state.selectedNotationElementId)
                : String(state.selectedNotationElementId).replace(/"/g, '\\"');
            const fallback = host.querySelector(`#${safeId}, [id="${safeId}"]`);
            fallback?.classList?.add("is-selected");
        }
    });
    [els.guzhengScoreView, els.diziScoreView, els.guitarLeadSheetView].forEach((host) => {
        if (!host) return;
        host.querySelectorAll(".is-edit-selected").forEach((el) => el.classList.remove("is-edit-selected"));
        if (idx == null) return;
        const target = host.querySelector(`[data-mxml-index="${idx}"]`);
        if (target) target.classList.add("is-edit-selected");
    });
}

function resolveActiveInstrumentForEditor() {
    return isPianoMode() ? "piano" : isGuzhengMode() ? "guzheng" : isDiziMode() ? "dizi" : isGuitarMode() ? "guitar" : "piano";
}

function renderEditWorkbench() {
    if (!els.editWorkbenchPanel) {
        return;
    }
    const instrument = resolveActiveInstrumentForEditor();
    const hasScore = Boolean(state.currentScore?.musicxml);
    const manualEditEnabled = supportsManualEdit(instrument);
    els.editWorkbenchPanel.hidden = !hasScore || !manualEditEnabled;
    if (!hasScore || !manualEditEnabled) {
        return;
    }
    if (els.editWorkbenchBody) {
        els.editWorkbenchBody.hidden = false;
    }
    if (els.editNavHintPiano) els.editNavHintPiano.hidden = instrument !== "piano";
    if (els.editNavHintTraditional) els.editNavHintTraditional.hidden = !(instrument === "guzheng" || instrument === "dizi");
    if (els.editNavHintGuitar) els.editNavHintGuitar.hidden = instrument !== "guitar";
    if (els.editWorkbenchTitle) {
        els.editWorkbenchTitle.textContent =
            instrument === "guzheng" ? "古筝技法标记" : instrument === "dizi" ? "笛子技法标记" : instrument === "guitar" ? "吉他和弦标记" : "钢琴音符修改";
    }
    els.editPaletteSections?.forEach((section) => {
        section.hidden = section.dataset.paletteFor !== instrument;
    });

    let summary = instrument === "guitar" ? "尚未选中和弦位置" : "尚未选中音符";
    let selectionValid = false;
    let selectedNoteEl = null;
    if (state.editorSelectedMxmlIndex != null) {
        const doc = parseMusicXmlDocument(state.currentScore.musicxml);
        const noteEl = locateMxmlNoteByIndex(doc, state.editorSelectedMxmlIndex);
        if (noteEl) {
            summary = `第 ${state.editorSelectedMxmlIndex + 1} 个 · ${describeMxmlNote(noteEl)}`;
            selectionValid = true;
            selectedNoteEl = noteEl;
        } else {
            state.editorSelectedMxmlIndex = null;
            state.editorSelectedKind = null;
        }
    }
    if (els.editSelectionSummary) {
        els.editSelectionSummary.textContent = summary;
    }

    const editing = isBusy("edit-workbench");
    const undoBusy = isBusy("undo-action");
    const redoBusy = isBusy("redo-action");

    const techniques = selectedNoteEl ? collectNoteTechniques(selectedNoteEl) : new Set();

    els.editPaletteButtons?.forEach((button) => {
        const action = button.dataset.editAction;
        const value = button.dataset.editValue || "";
        if (action === "undo") {
            button.disabled = !hasScore || undoBusy || editing;
            return;
        }
        if (action === "redo") {
            button.disabled = !hasScore || redoBusy || editing;
            return;
        }
        if (action === "harmony-apply" || action === "harmony-remove") {
            button.disabled = !selectionValid || editing;
            return;
        }
        button.disabled = !selectionValid || editing;

        button.classList.toggle(
            "is-active",
            Boolean(
                selectionValid &&
                    ((action === "ornament-toggle" && techniques.has(`ornament:${value}`)) ||
                        (action === "technical-toggle" && techniques.has(`technical:${value}`)) ||
                        (action === "articulation-toggle" && techniques.has(`articulation:${value}`)) ||
                        (action === "glissando-toggle" && techniques.has("glissando:start"))),
            ),
        );
    });
    const total = getEditorTotalNotes();
    if (els.editNotePrevBtn) {
        els.editNotePrevBtn.disabled =
            total <= 0 || editing || (state.editorSelectedMxmlIndex != null && state.editorSelectedMxmlIndex <= 0);
    }
    if (els.editNoteNextBtn) {
        els.editNoteNextBtn.disabled =
            total <= 0 ||
            editing ||
            (state.editorSelectedMxmlIndex != null && state.editorSelectedMxmlIndex >= total - 1);
    }
    els.chordRootButtons?.forEach((b) => b.classList.toggle("selected", b.dataset.chordRoot === state.editorChordRoot));
    els.chordAlterButtons?.forEach((b) => b.classList.toggle("selected", Number(b.dataset.chordAlter) === state.editorChordAlter));
    els.chordKindButtons?.forEach((b) => b.classList.toggle("selected", b.dataset.chordKind === state.editorChordKind));
    if (els.chordPreview) {
        const preview = formatChordSymbol(state.editorChordRoot, state.editorChordAlter, state.editorChordKind);
        els.chordPreview.innerHTML = `将写入：<strong>${escapeHtmlText(preview)}</strong>`;
    }
}

async function handleEditPaletteClick(event) {
    const button = event.currentTarget;
    const action = button.dataset.editAction;
    if (!action) {
        return;
    }
    if (action === "undo") {
        await handleUndo();
        return;
    }
    if (action === "redo") {
        await handleRedo();
        return;
    }
    if (state.editorSelectedMxmlIndex == null || !state.currentScore?.musicxml) {
        setAppStatus("请先点击谱面里的音符以选中。", true);
        return;
    }
    const value = button.dataset.editValue || "";
    await applyEditorMutation(action, value);
}

const EDIT_ZH_LABEL = {
    trill: "颤音",
    mordent: "波音",
    tremolo: "摇指",
    glissando: "滑奏",
    harmonic: "泛音",
    staccato: "打音",
    accent: "叠音",
};

function formatChordSymbol(root, alter, kind) {
    const accidental = alter === 1 ? "♯" : alter === -1 ? "♭" : "";
    const suffix =
        kind === "minor"
            ? "m"
            : kind === "dominant"
                ? "7"
                : kind === "minor-seventh"
                    ? "m7"
                    : kind === "major-seventh"
                        ? "maj7"
                        : kind === "suspended-fourth"
                            ? "sus4"
                            : kind === "diminished"
                                ? "dim"
                                : "";
    return `${String(root || "C").toUpperCase()}${accidental}${suffix}`;
}

function setEditorSaveStatus(status, text) {
    if (!els.editSaveStatus) {
        return;
    }
    els.editSaveStatus.dataset.status = status;
    if (els.editSaveStatusText && text) {
        els.editSaveStatusText.textContent = text;
    }
}

async function applyEditorMutation(action, value) {
    if (isBusy("edit-workbench")) {
        return;
    }
    const original = state.currentScore.musicxml;
    const doc = parseMusicXmlDocument(original);
    if (!doc) {
        setAppStatus("当前 MusicXML 解析失败，无法编辑。", true);
        setEditorSaveStatus("error", "本地 MusicXML 解析失败");
        return;
    }
    const noteEl = locateMxmlNoteByIndex(doc, state.editorSelectedMxmlIndex);
    if (!noteEl) {
        setAppStatus("选中的音符已不存在，请重新点击谱面选中。", true);
        setEditorSaveStatus("error", "选中音符丢失");
        clearEditorSelection();
        return;
    }
    let successMessage = "";
    try {
        switch (action) {
            case "duration":
                mutateNoteDuration(noteEl, value);
                successMessage = `已把选中音符改为${EDIT_TYPE_LABELS_ZH[value] || value}。`;
                break;
            case "dot-toggle":
                mutateNoteDotToggle(noteEl);
                successMessage = "已切换附点。";
                break;
            case "accidental":
                mutateNoteAccidental(noteEl, value);
                successMessage = `已应用升降记号：${value}。`;
                break;
            case "transpose":
                mutateNoteTranspose(noteEl, Number(value));
                successMessage = `音高已调整 ${Number(value) > 0 ? "+" : ""}${value} 个半音。`;
                break;
            case "to-rest":
                mutateNoteToRest(noteEl);
                successMessage = "已将选中音符替换为休止符。";
                break;
            case "ornament-toggle": {
                const added = toggleNoteOrnament(noteEl, value);
                successMessage = `${added ? "已添加" : "已移除"}${EDIT_ZH_LABEL[value] || value}标记。`;
                break;
            }
            case "technical-toggle": {
                const added = toggleNoteTechnical(noteEl, value);
                successMessage = `${added ? "已添加" : "已移除"}${EDIT_ZH_LABEL[value] || value}标记。`;
                break;
            }
            case "articulation-toggle": {
                const added = toggleNoteArticulation(noteEl, value);
                successMessage = `${added ? "已添加" : "已移除"}${EDIT_ZH_LABEL[value] || value}标记。`;
                break;
            }
            case "glissando-toggle": {
                const added = toggleNoteGlissando(noteEl);
                successMessage = `${added ? "已添加" : "已移除"}滑奏/刮奏标记。`;
                break;
            }
            case "harmony-apply": {
                applyHarmonyBeforeNote(noteEl, {
                    root: state.editorChordRoot,
                    alter: state.editorChordAlter,
                    kind: state.editorChordKind,
                });
                successMessage = `已写入和弦 ${formatChordSymbol(state.editorChordRoot, state.editorChordAlter, state.editorChordKind)}。`;
                break;
            }
            case "harmony-remove": {
                const removed = removeHarmonyBeforeNote(noteEl);
                successMessage = removed ? "已移除该位置的和弦。" : "该位置没有可移除的和弦。";
                break;
            }
            default:
                return;
        }
    } catch (error) {
        setAppStatus(`修改失败：${error.message}`, true);
        setEditorSaveStatus("error", `修改失败：${error.message}`);
        return;
    }

    const serialized = new XMLSerializer().serializeToString(doc);
    setEditorSaveStatus("saving", "正在保存到后端…");
    setBusy("edit-workbench", true);
    renderEditWorkbench();
    try {
        const updated = await requestJson(`/scores/${state.currentScore.score_id}`, {
            method: "PATCH",
            body: { musicxml: serialized },
        });
        applyScoreResult(updated);
        setAppStatus(successMessage);
        const versionLabel = updated?.version != null ? `（v${updated.version}）` : "";
        setEditorSaveStatus("saved", `${successMessage} 已保存到后端${versionLabel}`);
        // Round-trip: when the active mode is guzheng/dizi/guitar, the upper
        // LilyPond/lead-sheet view is derived server-side from the score data.
        // After a successful PATCH we must regenerate that derived view so
        // both panels (engraved + edit) reflect the new MusicXML.
        await regenerateActiveTraditionalView();
    } catch (error) {
        const detail = error?.message || "未知错误";
        setAppStatus(`保存失败：${detail}`, true);
        setEditorSaveStatus("error", `保存失败：${detail}`);
    } finally {
        setBusy("edit-workbench", false);
        renderEditWorkbench();
    }
}

async function regenerateActiveTraditionalView() {
    const scoreId = state.currentScore?.score_id;
    if (!scoreId) return;
    const instrument = resolveActiveInstrumentForEditor();
    try {
        if (instrument === "guzheng") {
            await requestGuzhengScore({ scoreId });
        } else if (instrument === "dizi") {
            await requestDiziScore({ scoreId });
        } else if (instrument === "guitar") {
            await requestGuitarLeadSheet({ scoreId });
        }
    } catch (error) {
        // Don't fail the whole edit on regen — the MusicXML still saved correctly.
        const detail = error?.message || "未知错误";
        console.warn(`Traditional view regen failed: ${detail}`);
        setAppStatus(`保存成功，但 ${instrument} 视图重渲失败：${detail}`, true);
    }
}

function findChild(parent, tagName) {
    return Array.from(parent.children).find((child) => child.tagName === tagName) || null;
}

function findChildren(parent, tagName) {
    return Array.from(parent.children).filter((child) => child.tagName === tagName);
}

function setOrCreateChildText(parent, tagName, text, beforeTag = null) {
    let child = findChild(parent, tagName);
    if (!child) {
        child = parent.ownerDocument.createElement(tagName);
        const before = beforeTag ? findChild(parent, beforeTag) : null;
        if (before) {
            parent.insertBefore(child, before);
        } else {
            parent.appendChild(child);
        }
    }
    child.textContent = String(text);
    return child;
}

function readDivisionsForNote(noteEl) {
    const part = noteEl.closest("part");
    if (!part) {
        return 4;
    }
    const measures = Array.from(part.getElementsByTagName("measure"));
    for (const measure of measures) {
        const div = measure.querySelector("attributes > divisions");
        if (div?.textContent) {
            const value = Number(div.textContent);
            if (Number.isFinite(value) && value > 0) {
                return value;
            }
        }
    }
    return 4;
}

function computeDuration(divisions, durationName, dots) {
    const config = EDIT_DURATION_TYPES[durationName];
    if (!config) {
        throw new Error(`不支持的时值：${durationName}`);
    }
    let raw = divisions * config.quartersPerNote;
    let bonus = raw / 2;
    for (let i = 0; i < dots; i += 1) {
        raw += bonus;
        bonus /= 2;
    }
    return Math.max(1, Math.round(raw));
}

function mutateNoteDuration(noteEl, durationName) {
    if (!EDIT_DURATION_TYPES[durationName]) {
        throw new Error(`不支持的时值：${durationName}`);
    }
    const divisions = readDivisionsForNote(noteEl);
    const dotCount = findChildren(noteEl, "dot").length;
    const dur = computeDuration(divisions, durationName, dotCount);
    setOrCreateChildText(noteEl, "duration", String(dur), "voice");
    setOrCreateChildText(noteEl, "type", durationName, "dot");
    findChildren(noteEl, "beam").forEach((node) => node.remove());
}

function mutateNoteDotToggle(noteEl) {
    const typeEl = findChild(noteEl, "type");
    const durationName = typeEl?.textContent?.trim() || "quarter";
    if (!EDIT_DURATION_TYPES[durationName]) {
        throw new Error("当前音符的时值不在可编辑列表中（仅支持全/二分/四分/八分/十六分）。");
    }
    const existingDots = findChildren(noteEl, "dot");
    let nextDotCount;
    if (existingDots.length > 0) {
        existingDots.forEach((node) => node.remove());
        nextDotCount = 0;
    } else {
        const dotEl = noteEl.ownerDocument.createElement("dot");
        const accidental = findChild(noteEl, "accidental") || findChild(noteEl, "time-modification") || findChild(noteEl, "stem");
        if (accidental) {
            noteEl.insertBefore(dotEl, accidental);
        } else {
            noteEl.appendChild(dotEl);
        }
        nextDotCount = 1;
    }
    const divisions = readDivisionsForNote(noteEl);
    const dur = computeDuration(divisions, durationName, nextDotCount);
    setOrCreateChildText(noteEl, "duration", String(dur), "voice");
}

function mutateNoteAccidental(noteEl, kind) {
    if (noteEl.querySelector("rest")) {
        throw new Error("休止符不能加升降记号。");
    }
    const pitch = noteEl.querySelector("pitch");
    if (!pitch) {
        throw new Error("当前音符没有可修改的音高。");
    }
    let alterValue = 0;
    let accidentalText = "";
    if (kind === "sharp") {
        alterValue = 1;
        accidentalText = "sharp";
    } else if (kind === "flat") {
        alterValue = -1;
        accidentalText = "flat";
    } else if (kind === "natural") {
        alterValue = 0;
        accidentalText = "natural";
    } else if (kind === "clear") {
        alterValue = 0;
        accidentalText = "";
    } else {
        throw new Error(`未知的升降记号：${kind}`);
    }
    let alterEl = pitch.querySelector("alter");
    if (alterValue === 0 && kind === "clear") {
        alterEl?.remove();
    } else {
        if (!alterEl) {
            alterEl = noteEl.ownerDocument.createElement("alter");
            const octave = pitch.querySelector("octave");
            if (octave) {
                pitch.insertBefore(alterEl, octave);
            } else {
                pitch.appendChild(alterEl);
            }
        }
        alterEl.textContent = String(alterValue);
    }
    const accidentalEl = findChild(noteEl, "accidental");
    if (!accidentalText) {
        accidentalEl?.remove();
    } else if (accidentalEl) {
        accidentalEl.textContent = accidentalText;
    } else {
        const newEl = noteEl.ownerDocument.createElement("accidental");
        newEl.textContent = accidentalText;
        const stem = findChild(noteEl, "stem") || findChild(noteEl, "notehead") || findChild(noteEl, "staff") || findChild(noteEl, "beam") || findChild(noteEl, "notations");
        if (stem) {
            noteEl.insertBefore(newEl, stem);
        } else {
            noteEl.appendChild(newEl);
        }
    }
}

function mutateNoteTranspose(noteEl, semitones) {
    if (noteEl.querySelector("rest")) {
        throw new Error("休止符不能调整音高。");
    }
    const pitch = noteEl.querySelector("pitch");
    if (!pitch) {
        throw new Error("当前音符没有可修改的音高。");
    }
    const step = pitch.querySelector("step")?.textContent?.trim().toUpperCase() || "C";
    const octave = Number(pitch.querySelector("octave")?.textContent || 4);
    const alter = Number(pitch.querySelector("alter")?.textContent || 0);
    const pcRaw = (EDIT_STEP_PC[step] || 0) + alter;
    const midi = (octave + 1) * 12 + pcRaw + Number(semitones || 0);
    const newOctave = Math.floor(midi / 12) - 1;
    const newPc = ((midi % 12) + 12) % 12;
    const [newStep, newAlter] = EDIT_PC_TO_STEP_ALTER[newPc];

    setOrCreateChildText(pitch, "step", newStep);
    let alterEl = pitch.querySelector("alter");
    if (newAlter === 0) {
        alterEl?.remove();
    } else {
        if (!alterEl) {
            alterEl = noteEl.ownerDocument.createElement("alter");
            const octaveEl = pitch.querySelector("octave");
            pitch.insertBefore(alterEl, octaveEl);
        }
        alterEl.textContent = String(newAlter);
    }
    setOrCreateChildText(pitch, "octave", String(newOctave));

    const accidentalEl = findChild(noteEl, "accidental");
    if (newAlter === 1) {
        if (accidentalEl) accidentalEl.textContent = "sharp";
        else {
            const el = noteEl.ownerDocument.createElement("accidental");
            el.textContent = "sharp";
            const stem = findChild(noteEl, "stem") || findChild(noteEl, "notations");
            stem ? noteEl.insertBefore(el, stem) : noteEl.appendChild(el);
        }
    } else if (newAlter === -1) {
        if (accidentalEl) accidentalEl.textContent = "flat";
        else {
            const el = noteEl.ownerDocument.createElement("accidental");
            el.textContent = "flat";
            const stem = findChild(noteEl, "stem") || findChild(noteEl, "notations");
            stem ? noteEl.insertBefore(el, stem) : noteEl.appendChild(el);
        }
    } else {
        accidentalEl?.remove();
    }
}

function mutateNoteToRest(noteEl) {
    const pitchEl = noteEl.querySelector("pitch");
    const unpitchedEl = noteEl.querySelector("unpitched");
    pitchEl?.remove();
    unpitchedEl?.remove();
    findChild(noteEl, "accidental")?.remove();
    findChild(noteEl, "stem")?.remove();
    findChild(noteEl, "notehead")?.remove();
    findChildren(noteEl, "tie").forEach((node) => node.remove());
    const notations = findChild(noteEl, "notations");
    if (notations) {
        notations.querySelectorAll("tied, slur, articulations").forEach((node) => node.remove());
    }
    if (!noteEl.querySelector("rest")) {
        const rest = noteEl.ownerDocument.createElement("rest");
        const firstChild = noteEl.firstElementChild;
        firstChild ? noteEl.insertBefore(rest, firstChild) : noteEl.appendChild(rest);
    }
    findChildren(noteEl, "chord").forEach((node) => node.remove());
}

/* ---------- Technique helpers (古筝/笛子) ---------- */

function ensureNotationsContainer(noteEl) {
    let notations = findChild(noteEl, "notations");
    if (!notations) {
        notations = noteEl.ownerDocument.createElement("notations");
        const after = findChild(noteEl, "lyric") || findChild(noteEl, "stem") || findChild(noteEl, "beam");
        if (after && after.nextSibling) {
            noteEl.insertBefore(notations, after.nextSibling);
        } else {
            noteEl.appendChild(notations);
        }
    }
    return notations;
}

function ensureChildContainer(parent, tagName) {
    let child = findChild(parent, tagName);
    if (!child) {
        child = parent.ownerDocument.createElement(tagName);
        parent.appendChild(child);
    }
    return child;
}

function toggleNoteOrnament(noteEl, kind) {
    if (noteEl.querySelector("rest")) {
        throw new Error("休止符不能加技法标记。");
    }
    const tagMap = { trill: "trill-mark", mordent: "mordent", tremolo: "tremolo" };
    const tagName = tagMap[kind];
    if (!tagName) {
        throw new Error(`未知技法：${kind}`);
    }
    const notations = ensureNotationsContainer(noteEl);
    const ornaments = ensureChildContainer(notations, "ornaments");
    const existing = findChild(ornaments, tagName);
    if (existing) {
        existing.remove();
        if (!ornaments.children.length) ornaments.remove();
        if (!notations.children.length) notations.remove();
        return false;
    }
    const node = noteEl.ownerDocument.createElement(tagName);
    if (kind === "tremolo") {
        node.setAttribute("type", "single");
        node.textContent = "3";
    }
    ornaments.appendChild(node);
    return true;
}

function toggleNoteTechnical(noteEl, kind) {
    if (noteEl.querySelector("rest")) {
        throw new Error("休止符不能加技法标记。");
    }
    const tagMap = { harmonic: "harmonic" };
    const tagName = tagMap[kind];
    if (!tagName) {
        throw new Error(`未知技法：${kind}`);
    }
    const notations = ensureNotationsContainer(noteEl);
    const technical = ensureChildContainer(notations, "technical");
    const existing = findChild(technical, tagName);
    if (existing) {
        existing.remove();
        if (!technical.children.length) technical.remove();
        if (!notations.children.length) notations.remove();
        return false;
    }
    const node = noteEl.ownerDocument.createElement(tagName);
    technical.appendChild(node);
    return true;
}

function toggleNoteArticulation(noteEl, kind) {
    if (noteEl.querySelector("rest")) {
        throw new Error("休止符不能加技法标记。");
    }
    const tagMap = { staccato: "staccato", accent: "accent" };
    const tagName = tagMap[kind];
    if (!tagName) {
        throw new Error(`未知技法：${kind}`);
    }
    const notations = ensureNotationsContainer(noteEl);
    const articulations = ensureChildContainer(notations, "articulations");
    const existing = findChild(articulations, tagName);
    if (existing) {
        existing.remove();
        if (!articulations.children.length) articulations.remove();
        if (!notations.children.length) notations.remove();
        return false;
    }
    const node = noteEl.ownerDocument.createElement(tagName);
    articulations.appendChild(node);
    return true;
}

function toggleNoteGlissando(noteEl) {
    if (noteEl.querySelector("rest")) {
        throw new Error("休止符不能加技法标记。");
    }
    const notations = ensureNotationsContainer(noteEl);
    const existing = Array.from(notations.children).find((c) => c.tagName === "glissando" || c.tagName === "slide");
    if (existing) {
        existing.remove();
        if (!notations.children.length) notations.remove();
        return false;
    }
    const node = noteEl.ownerDocument.createElement("glissando");
    node.setAttribute("type", "start");
    node.setAttribute("line-type", "solid");
    notations.appendChild(node);
    return true;
}

function collectNoteTechniques(noteEl) {
    const set = new Set();
    if (!noteEl) return set;
    const notations = findChild(noteEl, "notations");
    if (!notations) return set;
    const ornaments = findChild(notations, "ornaments");
    if (ornaments) {
        Array.from(ornaments.children).forEach((c) => {
            if (c.tagName === "trill-mark") set.add("ornament:trill");
            else if (c.tagName === "mordent" || c.tagName === "inverted-mordent") set.add("ornament:mordent");
            else if (c.tagName === "tremolo") set.add("ornament:tremolo");
        });
    }
    const technical = findChild(notations, "technical");
    if (technical) {
        Array.from(technical.children).forEach((c) => {
            if (c.tagName === "harmonic") set.add("technical:harmonic");
        });
    }
    const articulations = findChild(notations, "articulations");
    if (articulations) {
        Array.from(articulations.children).forEach((c) => {
            if (c.tagName === "staccato") set.add("articulation:staccato");
            else if (c.tagName === "accent") set.add("articulation:accent");
        });
    }
    Array.from(notations.children).forEach((c) => {
        if (c.tagName === "glissando" || c.tagName === "slide") set.add("glissando:start");
    });
    return set;
}

function describeTechniqueBadges(noteEl) {
    const badges = [];
    const set = collectNoteTechniques(noteEl);
    if (set.has("ornament:trill")) badges.push("tr");
    if (set.has("ornament:mordent")) badges.push("∽");
    if (set.has("ornament:tremolo")) badges.push("⫽");
    if (set.has("technical:harmonic")) badges.push("○");
    if (set.has("glissando:start")) badges.push("↗");
    if (set.has("articulation:staccato")) badges.push(".");
    if (set.has("articulation:accent")) badges.push(">");
    return badges;
}

/* ---------- Harmony helpers (吉他) ---------- */

function findHarmonyAnchoredAt(noteEl) {
    let prev = noteEl.previousElementSibling;
    while (prev && prev.tagName === "backup") prev = prev.previousElementSibling;
    if (prev && prev.tagName === "harmony") {
        return prev;
    }
    return null;
}

function applyHarmonyBeforeNote(noteEl, { root, alter, kind }) {
    const doc = noteEl.ownerDocument;
    const measure = noteEl.parentNode;
    if (!measure) {
        throw new Error("找不到选中音符所在的小节。");
    }
    const existing = findHarmonyAnchoredAt(noteEl);
    if (existing) {
        existing.remove();
    }
    const harmony = doc.createElement("harmony");
    const rootEl = doc.createElement("root");
    const rootStep = doc.createElement("root-step");
    rootStep.textContent = String(root || "C").toUpperCase();
    rootEl.appendChild(rootStep);
    if (alter) {
        const rootAlter = doc.createElement("root-alter");
        rootAlter.textContent = String(alter);
        rootEl.appendChild(rootAlter);
    }
    harmony.appendChild(rootEl);
    const kindEl = doc.createElement("kind");
    kindEl.textContent = String(kind || "major");
    harmony.appendChild(kindEl);
    measure.insertBefore(harmony, noteEl);
}

function removeHarmonyBeforeNote(noteEl) {
    const existing = findHarmonyAnchoredAt(noteEl);
    if (!existing) return false;
    existing.remove();
    return true;
}

function describeChordSymbolFromHarmony(harmonyEl) {
    if (!harmonyEl) return "";
    const root = findChild(harmonyEl, "root");
    const step = root ? findChild(root, "root-step")?.textContent : "";
    const alter = root ? Number(findChild(root, "root-alter")?.textContent || 0) : 0;
    const kindEl = findChild(harmonyEl, "kind");
    const kind = kindEl ? kindEl.textContent.trim() : "major";
    return formatChordSymbol(step || "C", alter, kind);
}

/* ---------- jianpu / lead-sheet click-to-select lookup ---------- */
/* Build a map: "measure_no|beat|pitch" → mxml note index.
   Used when the jianpu / lead-sheet click target carries pitch+beat info. */

function ensureJianpuLookup() {
    /* Position-based per-measure map: measure_no → [mxml_index_of_pitched_note_0, ...]
       For each measure, collects MusicXML <note> indices in document order,
       skipping rests and chord-extension notes. The Nth pitched jianpu note
       in a measure maps to the Nth entry here. Far more robust than matching
       by (beat, pitch) because it tolerates quantization differences. */
    const xml = state.currentScore?.musicxml;
    if (!xml) {
        state.editorJianpuLookup = null;
        state.editorJianpuLookupKey = "";
        return null;
    }
    const key = buildEditorIndexMapKey(state.currentScore);
    if (state.editorJianpuLookup && state.editorJianpuLookupKey === key) {
        return state.editorJianpuLookup;
    }
    const doc = parseMusicXmlDocument(xml);
    if (!doc) {
        state.editorJianpuLookup = null;
        state.editorJianpuLookupKey = "";
        return null;
    }
    const allNotes = listMxmlNoteElements(doc);
    const lookup = new Map();
    allNotes.forEach((noteEl, idx) => {
        const measureEl = noteEl.parentNode;
        const measureNo = Number(measureEl?.getAttribute("number") || 0);
        const isChord = !!findChild(noteEl, "chord");
        const isRest = !!findChild(noteEl, "rest");
        if (isChord || isRest) return;
        if (!lookup.has(measureNo)) lookup.set(measureNo, []);
        lookup.get(measureNo).push(idx);
    });
    state.editorJianpuLookup = lookup;
    state.editorJianpuLookupKey = key;
    return lookup;
}

function lookupJianpuMxmlIndexByPosition(measureNo, positionInMeasure) {
    const lookup = ensureJianpuLookup();
    if (!lookup) return null;
    const list = lookup.get(Number(measureNo));
    if (!Array.isArray(list)) return null;
    if (positionInMeasure < 0 || positionInMeasure >= list.length) return null;
    return list[positionInMeasure];
}

function lookupJianpuMxmlIndex(measureNo, _startBeat, _pitch) {
    /* Legacy adapter: returns first pitched note in the measure. The active
       renderer now passes explicit per-measure positions, so this is only a
       fallback when caller didn't compute the position. */
    return lookupJianpuMxmlIndexByPosition(measureNo, 0);
}

/* Build harmony lookup: measure_no → list of chord positions (measure-level, since harmony anchors before notes).
   For guitar we also map "anchor mxml index → chord symbol" from harmony elements that exist in MusicXML. */
function lookupAnchorMxmlIndexForChord(measureNo, beatInMeasure) {
    const xml = state.currentScore?.musicxml;
    if (!xml || !measureNo) return null;
    const doc = parseMusicXmlDocument(xml);
    if (!doc) return null;
    const allNotes = listMxmlNoteElements(doc);
    let cursor = 0;
    let lastDur = 0;
    let divisions = 8;
    let lastMeasureNo = 0;
    let bestIdx = null;
    let bestDelta = Infinity;
    for (let i = 0; i < allNotes.length; i += 1) {
        const noteEl = allNotes[i];
        const measureEl = noteEl.parentNode;
        const mNo = Number(measureEl?.getAttribute("number") || 0);
        if (mNo !== lastMeasureNo) {
            lastMeasureNo = mNo;
            cursor = 0;
            lastDur = 0;
            const div = measureEl?.querySelector("attributes > divisions")?.textContent;
            if (div) divisions = Math.max(Number(div) || 8, 1);
        }
        if (mNo !== Number(measureNo)) {
            const isChord = !!findChild(noteEl, "chord");
            const dur = Number(findChild(noteEl, "duration")?.textContent || 0);
            if (!isChord) {
                cursor += dur;
                lastDur = dur;
            }
            continue;
        }
        const isChord = !!findChild(noteEl, "chord");
        const dur = Number(findChild(noteEl, "duration")?.textContent || 0);
        const noteStartTime = isChord ? Math.max(cursor - lastDur, 0) : cursor;
        const startBeat = noteStartTime / divisions + 1;
        const delta = Math.abs(startBeat - Number(beatInMeasure || 1));
        if (delta < bestDelta) {
            bestDelta = delta;
            bestIdx = i;
        }
        if (!isChord) {
            cursor += dur;
            lastDur = dur;
        }
    }
    return bestIdx;
}

function buildTechniqueBadgesForIndex(mxmlIndex) {
    const xml = state.currentScore?.musicxml;
    if (!xml || mxmlIndex == null) return "";
    const doc = parseMusicXmlDocument(xml);
    if (!doc) return "";
    const noteEl = locateMxmlNoteByIndex(doc, mxmlIndex);
    if (!noteEl) return "";
    const badges = describeTechniqueBadges(noteEl);
    if (!badges.length) return "";
    return `<span class="guzheng-jianpu-technique-badges">${badges.map((b) => escapeHtmlText(b)).join("")}</span>`;
}

function ensureHarmonyOverrideMap() {
    const xml = state.currentScore?.musicxml;
    if (!xml) {
        state.editorHarmonyIndex = null;
        state.editorHarmonyIndexKey = "";
        return null;
    }
    const key = buildEditorIndexMapKey(state.currentScore);
    if (state.editorHarmonyIndex && state.editorHarmonyIndexKey === key) {
        return state.editorHarmonyIndex;
    }
    const doc = parseMusicXmlDocument(xml);
    if (!doc) {
        state.editorHarmonyIndex = null;
        state.editorHarmonyIndexKey = "";
        return null;
    }
    const allNotes = listMxmlNoteElements(doc);
    const noteToIndex = new Map();
    allNotes.forEach((n, i) => noteToIndex.set(n, i));
    const map = new Map(); // measureNo → array of {symbol, anchorIdx}
    const harmonies = Array.from(doc.getElementsByTagName("harmony"));
    harmonies.forEach((h) => {
        const measureEl = h.parentNode;
        const measureNo = Number(measureEl?.getAttribute("number") || 0);
        let anchor = h.nextElementSibling;
        while (anchor && anchor.tagName !== "note") anchor = anchor.nextElementSibling;
        const anchorIdx = anchor ? noteToIndex.get(anchor) : null;
        const symbol = describeChordSymbolFromHarmony(h);
        if (!map.has(measureNo)) map.set(measureNo, []);
        map.get(measureNo).push({ symbol, anchorIdx });
    });
    state.editorHarmonyIndex = map;
    state.editorHarmonyIndexKey = key;
    return map;
}
