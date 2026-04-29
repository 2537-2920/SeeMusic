const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function loadTranscriptionHarness() {
    const source = fs.readFileSync(path.join(__dirname, "../frontend/transcription.js"), "utf8");
    const context = {
        console,
        URL,
        DOMException: class DOMException extends Error {},
        localStorage: {
            getItem() { return ""; },
            setItem() {},
            removeItem() {},
        },
        window: {
            SeeMusicScoreViewerLayout: {},
            addEventListener() {},
            matchMedia() {
                return { matches: false };
            },
            CSS: {
                escape(value) {
                    return String(value);
                },
            },
            innerWidth: 1280,
            setTimeout,
            clearTimeout,
            location: { origin: "http://127.0.0.1:8000" },
        },
        document: {
            addEventListener() {},
            getElementById() { return null; },
            querySelectorAll() { return []; },
            querySelector() { return null; },
            createElement() {
                return {
                    style: {},
                    classList: { add() {}, remove() {}, toggle() {} },
                    appendChild() {},
                    click() {},
                    remove() {},
                    setAttribute() {},
                };
            },
            body: {
                appendChild() {},
                classList: { toggle() {} },
                dataset: {},
            },
            documentElement: {
                style: { setProperty() {} },
            },
        },
        navigator: {},
        FormData: class {},
        Blob: class {},
        DOMParser: class {},
        XMLSerializer: class {},
        setTimeout,
        clearTimeout,
        fetch: async () => {
            throw new Error("fetch not mocked");
        },
    };
    vm.createContext(context);
    vm.runInContext(source, context, { filename: "frontend/transcription.js" });
    vm.runInContext(`
        this.__test = {
            state,
            els,
            resolveJianpuAnnotationLayer,
            renderTraditionalAnnotationLayerToggle,
            readSymbolMxmlIndex,
            updateEditorSelectionFromSymbol,
            resolveSymbolMxmlIndexByPosition,
            resolveGuzhengPressText,
            renderTraditionalPaperOrnaments,
            ensureVerovioResourceAliases,
            configureVerovioToolkit,
            syncSelectionHighlightToCurrentSelection,
            handleScoreCanvasInteraction,
            clearEditorSelection,
            clearWorkbenchState,
            handleRefreshWorkbench,
            renderEditWorkbench,
            renderAnalysisOutputs,
            renderGuzhengDebugPanel,
            renderDiziDebugPanel,
            defaultSelectionHint,
            stepEditorSelection
        };
    `, context);
    context.__test.els.appStatus = { textContent: "", style: {} };
    context.__test.els.selectedNoteSummary = { textContent: "" };
    return { context, api: context.__test };
}

function assignOverride(context, name, fn) {
    context.__override = fn;
    vm.runInContext(`${name} = __override;`, context);
    delete context.__override;
}

function makeClassList(initial = []) {
    const values = new Set(initial);
    return {
        add(name) {
            values.add(name);
        },
        remove(name) {
            values.delete(name);
        },
        contains(name) {
            return values.has(name);
        },
        has(name) {
            return values.has(name);
        },
    };
}

function makeSymbol({ id = null, kind = "note", attrs = {} } = {}) {
    const attributes = new Map(Object.entries(attrs).map(([key, value]) => [key, String(value)]));
    if (id != null) {
        attributes.set("id", String(id));
    }
    return {
        classList: makeClassList([kind]),
        getAttribute(name) {
            return attributes.has(name) ? attributes.get(name) : null;
        },
        setAttribute(name, value) {
            attributes.set(name, String(value));
        },
        removeAttribute(name) {
            attributes.delete(name);
        },
        closest(selector) {
            if (selector === ".measure") {
                return this.measure || null;
            }
            if (selector === "[data-page-index]" || selector === ".score-paper-sheet") {
                return this.pageScope || null;
            }
            if (selector === ".verovio-stage") {
                return this.stage || null;
            }
            if (selector === ".verovio-pane") {
                return { parentNode: this.stage || null };
            }
            return null;
        },
    };
}

function buildVerovioHost(measureSpecs, options = {}) {
    const measures = [];
    const symbols = [];
    const attributes = new Map();
    if (options.pageIndex != null) {
        attributes.set("data-page-index", String(options.pageIndex));
    }
    if (options.renderMode) {
        attributes.set("data-render-mode", String(options.renderMode));
    }
    const host = {
        measures,
        symbols,
        dataset: {
            ...(options.pageIndex != null ? { verovioPageIndex: String(options.pageIndex) } : {}),
            ...(options.renderMode ? { verovioRenderMode: String(options.renderMode) } : {}),
        },
        getAttribute(name) {
            return attributes.has(name) ? attributes.get(name) : null;
        },
        querySelectorAll(selector) {
            if (selector === ".verovio-pane .measure") {
                return measures;
            }
            if (selector === ".note, .rest") {
                return symbols;
            }
            if (selector === ".verovio-pane .note, .verovio-pane .rest") {
                return symbols;
            }
            if (selector === ".note.is-selected, .rest.is-selected") {
                return symbols.filter((symbol) => symbol.classList.has("is-selected"));
            }
            return [];
        },
        querySelector(selector) {
            const dataIndexMatch = selector.match(/\[data-mxml-index="(\d+)"\]/);
            if (dataIndexMatch) {
                return symbols.find((symbol) => symbol.getAttribute("data-mxml-index") === dataIndexMatch[1]) || null;
            }
            const idMatch = selector.match(/#([^,\]]+)|\[id="([^"]+)"\]/);
            if (idMatch) {
                const id = idMatch[1] || idMatch[2];
                return symbols.find((symbol) => symbol.getAttribute("id") === id) || null;
            }
            return null;
        },
    };

    measureSpecs.forEach((spec) => {
        const measure = {
            getAttribute(name) {
                if (name === "data-n" || name === "n") {
                    return spec.measureNo != null ? String(spec.measureNo) : null;
                }
                return null;
            },
            querySelectorAll(selector) {
                if (selector === ".note, .rest") {
                    return this.symbols;
                }
                return [];
            },
            symbols: [],
        };
        (spec.symbols || []).forEach((symbolSpec) => {
            const symbol = makeSymbol(symbolSpec);
            symbol.measure = measure;
            symbol.stage = host;
            symbol.pageScope = host;
            measure.symbols.push(symbol);
            symbols.push(symbol);
        });
        measures.push(measure);
    });

    return host;
}

function makeMxmlNote({ measureNo, isRest = false } = {}) {
    const measure = {
        getAttribute(name) {
            return name === "number" ? String(measureNo) : null;
        },
    };
    return {
        parentNode: measure,
        querySelector(selector) {
            if (selector === "rest") {
                return isRest ? {} : null;
            }
            return null;
        },
    };
}

test("click selection prefers the existing data-mxml-index on single-page renders", () => {
    const { api } = loadTranscriptionHarness();
    api.state.currentScore = { musicxml: "<score-partwise />" };
    api.state.previewPageCount = 1;
    const host = buildVerovioHost([
        {
            measureNo: 1,
            symbols: [{ kind: "note", attrs: { "data-mxml-index": 5 } }, { kind: "note" }],
        },
    ]);
    const result = api.updateEditorSelectionFromSymbol(host.symbols[0], host);

    assert.equal(result.ok, true);
    assert.equal(result.index, 5);
    assert.equal(api.state.editorSelectedMxmlIndex, 5);
  });

test("click selection retags before falling back to position on multi-page renders", () => {
    const { context, api } = loadTranscriptionHarness();
    api.state.currentScore = { musicxml: "<score-partwise />" };
    api.state.previewPageCount = 3;
    const host = buildVerovioHost([
        {
            measureNo: 1,
            symbols: [{ kind: "note" }, { kind: "note" }],
        },
    ]);
    assignOverride(context, "tagRenderedSymbolsWithMxmlIndex", (targetHost) => {
        targetHost.symbols[1].setAttribute("data-mxml-index", 7);
    });
    assignOverride(context, "parseMusicXmlDocument", () => ({ ok: true }));
    assignOverride(context, "listMxmlNoteElements", () => [
        makeMxmlNote({ measureNo: 1 }),
        makeMxmlNote({ measureNo: 1 }),
    ]);

    const result = api.updateEditorSelectionFromSymbol(host.symbols[1], host);

    assert.equal(result.ok, true);
    assert.equal(result.index, 7);
    assert.equal(api.state.editorSelectedMxmlIndex, 7);
});

test("position fallback keeps measure-local ordering with rests and chord tones", () => {
    const { context, api } = loadTranscriptionHarness();
    api.state.currentScore = { musicxml: "<score-partwise />" };
    api.state.previewPageCount = 4;
    const host = buildVerovioHost([
        {
            measureNo: 3,
            symbols: [{ kind: "note" }, { kind: "rest" }, { kind: "note" }, { kind: "note" }],
        },
    ]);
    assignOverride(context, "tagRenderedSymbolsWithMxmlIndex", () => {});
    assignOverride(context, "parseMusicXmlDocument", () => ({ ok: true }));
    assignOverride(context, "listMxmlNoteElements", () => [
        makeMxmlNote({ measureNo: 3 }),
        makeMxmlNote({ measureNo: 3, isRest: true }),
        makeMxmlNote({ measureNo: 3 }),
        makeMxmlNote({ measureNo: 3 }),
    ]);

    const resolved = api.resolveSymbolMxmlIndexByPosition(host.symbols[2], host);

    assert.equal(resolved, 2);
});

test("multi-page preview fallback uses cached page offsets when the rendered measure is unlabeled", () => {
    const { context, api } = loadTranscriptionHarness();
    api.state.currentScore = { musicxml: "<score-partwise />" };
    api.state.previewPageCount = 4;
    api.state.previewPageSymbolOffsets = [0, 4, 8, 12];
    const host = buildVerovioHost([
        {
            measureNo: null,
            symbols: [{ kind: "note" }, { kind: "note" }, { kind: "rest" }],
        },
    ], { pageIndex: 1, renderMode: "preview" });
    assignOverride(context, "parseMusicXmlDocument", () => ({ ok: true }));
    assignOverride(context, "listMxmlNoteElements", () => [
        makeMxmlNote({ measureNo: 1 }),
        makeMxmlNote({ measureNo: 1 }),
        makeMxmlNote({ measureNo: 1, isRest: true }),
        makeMxmlNote({ measureNo: 1 }),
        makeMxmlNote({ measureNo: 2 }),
        makeMxmlNote({ measureNo: 2 }),
        makeMxmlNote({ measureNo: 2, isRest: true }),
        makeMxmlNote({ measureNo: 2 }),
    ]);

    const resolved = api.resolveSymbolMxmlIndexByPosition(host.symbols[2], host);

    assert.equal(resolved, 6);
});

test("multi-page viewer fallback uses the viewer page offset cache", () => {
    const { context, api } = loadTranscriptionHarness();
    api.state.currentScore = { musicxml: "<score-partwise />" };
    api.state.viewerPageCount = 3;
    api.state.viewerPageSymbolOffsets = [0, 5, 11];
    const host = buildVerovioHost([
        {
            measureNo: null,
            symbols: [{ kind: "note" }, { kind: "rest" }, { kind: "note" }],
        },
    ], { pageIndex: 1, renderMode: "viewer" });
    assignOverride(context, "parseMusicXmlDocument", () => ({ ok: true }));
    assignOverride(context, "listMxmlNoteElements", () => [
        makeMxmlNote({ measureNo: 1 }),
        makeMxmlNote({ measureNo: 1 }),
        makeMxmlNote({ measureNo: 1 }),
        makeMxmlNote({ measureNo: 1 }),
        makeMxmlNote({ measureNo: 1 }),
        makeMxmlNote({ measureNo: 2 }),
        makeMxmlNote({ measureNo: 2, isRest: true }),
        makeMxmlNote({ measureNo: 2 }),
        makeMxmlNote({ measureNo: 2 }),
    ]);

    const resolved = api.resolveSymbolMxmlIndexByPosition(host.symbols[2], host);

    assert.equal(resolved, 7);
});

test("multi-page fallback still refuses flat guesses when no page offset cache is available", () => {
    const { context, api } = loadTranscriptionHarness();
    api.state.currentScore = { musicxml: "<score-partwise />" };
    api.state.previewPageCount = 4;
    const host = buildVerovioHost([
        {
            measureNo: null,
            symbols: [{ kind: "note" }, { kind: "note" }],
        },
    ], { pageIndex: 1, renderMode: "preview" });
    assignOverride(context, "parseMusicXmlDocument", () => ({ ok: true }));
    assignOverride(context, "listMxmlNoteElements", () => [
        makeMxmlNote({ measureNo: 1 }),
        makeMxmlNote({ measureNo: 1 }),
    ]);

    const resolved = api.resolveSymbolMxmlIndexByPosition(host.symbols[1], host);

    assert.equal(resolved, null);
});

test("verovio resource aliases expose glyphnames.json from tuning-glyphnames.json", () => {
    const { api } = loadTranscriptionHarness();
    const writes = [];
    const moduleRef = {
        FS: {
            analyzePath(targetPath) {
                return { exists: targetPath === "/data/tuning-glyphnames.json" };
            },
            readFile(targetPath, options) {
                assert.equal(targetPath, "/data/tuning-glyphnames.json");
                assert.equal(options?.encoding, "utf8");
                return '{"accidentalNatural":"U+E261"}';
            },
            writeFile(targetPath, content) {
                writes.push({ targetPath, content });
            },
        },
    };

    api.ensureVerovioResourceAliases(moduleRef);

    assert.deepEqual(writes, [
        {
            targetPath: "/data/glyphnames.json",
            content: '{"accidentalNatural":"U+E261"}',
        },
    ]);
});

test("verovio toolkit configuration pins the in-memory resource path", () => {
    const { api } = loadTranscriptionHarness();
    const calls = [];
    const toolkit = {
        setResourcePath(resourcePath) {
            calls.push(resourcePath);
        },
    };

    const configured = api.configureVerovioToolkit(toolkit, { FS: null });

    assert.equal(configured, toolkit);
    assert.deepEqual(calls, ["/data"]);
});

test("traditional annotation layer normalizes legacy values to technique", () => {
    const { api } = loadTranscriptionHarness();

    assert.equal(api.resolveJianpuAnnotationLayer("fingering"), "technique");
    assert.equal(api.resolveJianpuAnnotationLayer("all"), "technique");
    assert.equal(api.resolveJianpuAnnotationLayer("technique"), "technique");
});

test("traditional annotation toggle only exposes basic body and technique layer", () => {
    const { api } = loadTranscriptionHarness();
    const markup = api.renderTraditionalAnnotationLayerToggle("technique");

    assert.match(markup, /基础正文/);
    assert.match(markup, /技法层/);
    assert.doesNotMatch(markup, /弦位层|指法层|完整标注/);
});

test("edit workbench stays hidden for guzheng and dizi modes", () => {
    const { api } = loadTranscriptionHarness();
    api.state.currentScore = { musicxml: "<score-partwise />" };
    api.els.editWorkbenchPanel = { hidden: false };

    api.state.instrumentType = "guzheng";
    api.renderEditWorkbench();
    assert.equal(api.els.editWorkbenchPanel.hidden, true);

    api.els.editWorkbenchPanel.hidden = false;
    api.state.instrumentType = "dizi";
    api.renderEditWorkbench();
    assert.equal(api.els.editWorkbenchPanel.hidden, true);
});

test("piano analysis clears hidden non-piano debug panels", () => {
    const { api } = loadTranscriptionHarness();
    api.state.instrumentType = "piano";
    api.state.separateTracksResult = null;
    api.els.pianoAnalysisGrid = { hidden: true };
    api.els.separateTracksOutput = { innerHTML: "" };
    api.els.guzhengDebugPanel = { hidden: false, innerHTML: "<button>展开识谱过程</button>" };
    api.els.guitarDebugPanel = { hidden: false, innerHTML: "<button>展开识谱过程</button>" };
    api.els.diziDebugPanel = { hidden: false, innerHTML: "<button>展开识谱过程</button>" };

    api.renderAnalysisOutputs();

    assert.equal(api.els.pianoAnalysisGrid.hidden, false);
    assert.equal(api.els.guzhengDebugPanel.hidden, true);
    assert.equal(api.els.guitarDebugPanel.hidden, true);
    assert.equal(api.els.diziDebugPanel.hidden, true);
    assert.equal(api.els.guzhengDebugPanel.innerHTML, "");
    assert.equal(api.els.guitarDebugPanel.innerHTML, "");
    assert.equal(api.els.diziDebugPanel.innerHTML, "");
});

test("guzheng analysis renders details directly without track-separation card or toggle", () => {
    const { api } = loadTranscriptionHarness();
    api.els.guzhengDebugPanel = { innerHTML: "" };
    api.state.guzhengResult = {
        melody_track: null,
        key_detection: null,
        warnings: [],
        technique_summary: { counts: {} },
        pentatonic_summary: {},
        tempo_detection: {},
        pipeline: {},
    };

    api.renderGuzhengDebugPanel();

    assert.match(api.els.guzhengDebugPanel.innerHTML, /测速与定调/);
    assert.doesNotMatch(api.els.guzhengDebugPanel.innerHTML, /展开识谱过程|收起识谱过程/);
    assert.doesNotMatch(api.els.guzhengDebugPanel.innerHTML, /分离轨与选轨/);
});

test("dizi analysis renders details directly without track-separation card or toggle", () => {
    const { api } = loadTranscriptionHarness();
    api.els.diziDebugPanel = { innerHTML: "" };
    api.state.diziFluteType = "G";
    api.state.diziResult = {
        flute_type: "G",
        melody_track: null,
        key_detection: null,
        warnings: [],
        technique_summary: { counts: {} },
        playability_summary: {},
        tempo_detection: {},
        pipeline: {},
        instrument_profile: {},
    };

    api.renderDiziDebugPanel();

    assert.match(api.els.diziDebugPanel.innerHTML, /测速与定调/);
    assert.doesNotMatch(api.els.diziDebugPanel.innerHTML, /展开识谱过程|收起识谱过程/);
    assert.doesNotMatch(api.els.diziDebugPanel.innerHTML, /分离轨与选轨/);
});

test("dizi analysis mode force-hides the piano track-separation grid", () => {
    const { api } = loadTranscriptionHarness();
    api.state.instrumentType = "dizi";
    api.state.diziFluteType = "G";
    api.state.diziResult = {
        flute_type: "G",
        melody_track: null,
        key_detection: null,
        warnings: [],
        technique_summary: { counts: {} },
        playability_summary: {},
        tempo_detection: {},
        pipeline: {},
        instrument_profile: {},
    };
    api.els.pianoAnalysisGrid = { hidden: false, style: { display: "" } };
    api.els.guzhengDebugPanel = { hidden: false, innerHTML: "" };
    api.els.guitarDebugPanel = { hidden: false, innerHTML: "" };
    api.els.diziDebugPanel = { hidden: true, innerHTML: "" };

    api.renderAnalysisOutputs();

    assert.equal(api.els.pianoAnalysisGrid.hidden, true);
    assert.equal(api.els.pianoAnalysisGrid.style.display, "none");
    assert.equal(api.els.diziDebugPanel.hidden, false);
});

test("refresh workbench clears stale score state but preserves the project title", () => {
    const { context, api } = loadTranscriptionHarness();
    const storage = new Map();
    context.localStorage.getItem = (key) => (storage.has(key) ? storage.get(key) : "");
    context.localStorage.setItem = (key, value) => storage.set(key, String(value));
    context.localStorage.removeItem = (key) => storage.delete(key);

    storage.set("seemusic.transcription.title", "保留的项目名");
    storage.set("seemusic.transcription.scoreId", "score-42");
    storage.set("seemusic.transcription.analysisId", "analysis-42");
    storage.set("seemusic.transcription.tempo", "96");
    storage.set("seemusic.transcription.timeSignature", "3/4");
    storage.set("seemusic.transcription.keySignature", "D");

    api.state.currentScore = { score_id: "score-42", musicxml: "<score-partwise />" };
    api.state.guzhengResult = { measures: [{}] };
    api.state.guzhengEngravedPreview = { signature: "guzheng-preview" };
    api.state.guitarLeadSheetResult = { measures: [{}] };
    api.state.diziResult = { flute_type: "G", measures: [{}] };
    api.state.diziEngravedPreview = { signature: "dizi-preview" };
    api.state.guitarHighlightedChordSymbol = "Am";
    api.state.preferredTempo = 96;
    api.state.preferredTimeSignature = "3/4";
    api.state.preferredKeySignature = "D";
    api.state.latestPitchSequence = [{ time: 0, frequency: 440, duration: 0.5 }];
    api.state.selectedScoreId = "score-42";
    api.state.selectedNotationElementId = "note-42";
    api.state.exportList = [{ export_record_id: "export-1" }];
    api.state.selectedExportRecordId = "export-1";
    api.state.selectedExportDetail = { export_record_id: "export-1", exists: true };
    api.state.beatDetectResult = { bpm: 96 };
    api.state.separateTracksResult = { tracks: [{ name: "vocal" }] };
    api.state.chordGenerationResult = { chords: [{ symbol: "Am" }] };
    api.state.rhythmScoreResult = { score: 88 };
    api.state.audioLogs = [{ file_name: "demo.wav" }];
    api.state.scorePageIndex = 2;
    api.state.scoreViewerOpen = true;
    api.state.previewPageCount = 3;
    api.state.previewPageIndex = 1;
    api.state.editorIndexMap = new Map([[1, 2]]);
    api.state.editorIndexMapKey = "score-42:v1";
    api.state.viewerPageCount = 4;
    api.state.viewerPageRanges = [{ startMeasureNo: 1, endMeasureNo: 4 }];
    api.state.viewerPreparedKey = "prepared";
    api.state.viewerPreparedMusicxml = "<score-partwise />";
    api.state.viewerPreparedLayout = { systemsPerPage: 5 };
    api.state.viewerPageCache = new Map([[0, "<svg />"]]);
    api.state.viewerTransition = { phase: "animating", direction: 1, fromIndex: 1, toIndex: 2, progress: 1 };
    api.state.viewerGesture = { pointerId: 1 };
    api.state.viewerWheelAccumX = 120;
    api.state.viewerSuppressClickUntil = 9999;
    api.state.editorSelectedMxmlIndex = 8;
    api.state.editorSelectedKind = "note";
    api.state.editorSelectedSummary = "第 2 小节音符";
    api.state.editorJianpuLookup = { 8: {} };
    api.state.editorJianpuLookupKey = "guzheng:42";
    api.state.editorTechniqueIndex = { 8: {} };
    api.state.editorTechniqueIndexKey = "technique:42";
    api.state.editorHarmonyIndex = { 8: {} };
    api.state.editorHarmonyIndexKey = "harmony:42";

    const blankClassList = { toggle() {}, add() {}, remove() {} };
    api.els.projectTitleInput = { value: "保留的项目名" };
    api.els.analysisIdInput = { value: "analysis-42" };
    api.els.scoreMusicxmlInput = { value: "<score-partwise />" };
    api.els.pitchDetectFileInput = { value: "demo.wav" };
    api.els.analysisFileInput = { value: "analysis.wav" };
    api.els.scoreMusicxmlFileInput = { value: "score.musicxml" };
    api.els.pitchDetectStatus = { textContent: "旧状态", classList: blankClassList, style: {} };
    api.els.scoreViewerEntry = { innerHTML: "<div>old score</div>" };
    api.els.scoreViewerCanvas = { innerHTML: "<div>old viewer</div>" };
    api.els.guzhengScoreView = { innerHTML: "old guzheng" };
    api.els.guitarLeadSheetView = { innerHTML: "old guitar" };
    api.els.diziScoreView = { innerHTML: "old dizi" };
    api.els.guzhengDebugPanel = { innerHTML: "old guzheng debug" };
    api.els.guitarDebugPanel = { innerHTML: "old guitar debug" };
    api.els.diziDebugPanel = { innerHTML: "old dizi debug" };
    api.els.separateTracksOutput = { innerHTML: "old separation" };
    api.els.audioLogList = { innerHTML: "old logs" };
    api.els.exportList = { innerHTML: "old exports" };

    api.clearWorkbenchState();

    assert.equal(api.state.currentScore, null);
    assert.equal(api.state.guzhengResult, null);
    assert.equal(api.state.guzhengEngravedPreview, null);
    assert.equal(api.state.guitarLeadSheetResult, null);
    assert.equal(api.state.diziResult, null);
    assert.equal(api.state.diziEngravedPreview, null);
    assert.equal(api.state.guitarHighlightedChordSymbol, "");
    assert.equal(Array.isArray(api.state.latestPitchSequence), true);
    assert.equal(api.state.latestPitchSequence.length, 0);
    assert.equal(api.state.selectedScoreId, "");
    assert.equal(api.state.selectedNotationElementId, null);
    assert.equal(Array.isArray(api.state.exportList), true);
    assert.equal(api.state.exportList.length, 0);
    assert.equal(api.state.selectedExportRecordId, null);
    assert.equal(api.state.selectedExportDetail, null);
    assert.equal(api.state.beatDetectResult, null);
    assert.equal(api.state.separateTracksResult, null);
    assert.equal(api.state.chordGenerationResult, null);
    assert.equal(api.state.rhythmScoreResult, null);
    assert.equal(Array.isArray(api.state.audioLogs), true);
    assert.equal(api.state.audioLogs.length, 0);
    assert.equal(api.state.scorePageIndex, 0);
    assert.equal(api.state.scoreViewerOpen, false);
    assert.equal(api.state.previewPageCount, 0);
    assert.equal(api.state.previewPageIndex, 0);
    assert.equal(api.state.editorIndexMap, null);
    assert.equal(api.state.editorIndexMapKey, "");
    assert.equal(api.state.viewerPageCount, 0);
    assert.equal(Array.isArray(api.state.viewerPageRanges), true);
    assert.equal(api.state.viewerPageRanges.length, 0);
    assert.equal(api.state.viewerPreparedKey, "");
    assert.equal(api.state.viewerPreparedMusicxml, "");
    assert.equal(api.state.viewerPreparedLayout, null);
    assert.equal(api.state.viewerPageCache.size, 0);
    assert.equal(api.state.viewerTransition.phase, "idle");
    assert.equal(api.state.viewerGesture, null);
    assert.equal(api.state.viewerWheelAccumX, 0);
    assert.equal(api.state.viewerSuppressClickUntil, 0);
    assert.equal(api.state.editorSelectedMxmlIndex, null);
    assert.equal(api.state.editorSelectedKind, null);
    assert.equal(api.state.editorSelectedSummary, "");
    assert.equal(api.state.editorJianpuLookup, null);
    assert.equal(api.state.editorJianpuLookupKey, "");
    assert.equal(api.state.editorTechniqueIndex, null);
    assert.equal(api.state.editorTechniqueIndexKey, "");
    assert.equal(api.state.editorHarmonyIndex, null);
    assert.equal(api.state.editorHarmonyIndexKey, "");
    assert.equal(api.state.preferredTempo, 120);
    assert.equal(api.state.preferredTimeSignature, "4/4");
    assert.equal(api.state.preferredKeySignature, "C");

    assert.equal(api.els.projectTitleInput.value, "保留的项目名");
    assert.equal(api.els.analysisIdInput.value, "");
    assert.equal(api.els.scoreMusicxmlInput.value, "");
    assert.equal(api.els.pitchDetectFileInput.value, "");
    assert.equal(api.els.analysisFileInput.value, "");
    assert.equal(api.els.scoreMusicxmlFileInput.value, "");
    assert.equal(api.els.pitchDetectStatus.textContent, "");
    assert.equal(api.els.scoreViewerEntry.innerHTML, "");
    assert.equal(api.els.scoreViewerCanvas.innerHTML, "");
    assert.equal(api.els.guzhengScoreView.innerHTML, "");
    assert.equal(api.els.guitarLeadSheetView.innerHTML, "");
    assert.equal(api.els.diziScoreView.innerHTML, "");
    assert.equal(api.els.guzhengDebugPanel.innerHTML, "");
    assert.equal(api.els.guitarDebugPanel.innerHTML, "");
    assert.equal(api.els.diziDebugPanel.innerHTML, "");
    assert.equal(api.els.separateTracksOutput.innerHTML, "");
    assert.equal(api.els.audioLogList.innerHTML, "");
    assert.equal(api.els.exportList.innerHTML, "");

    assert.equal(storage.get("seemusic.transcription.title"), "保留的项目名");
    assert.equal(storage.get("seemusic.transcription.pitchSequence"), "[]");
    assert.equal(storage.has("seemusic.transcription.scoreId"), false);
    assert.equal(storage.has("seemusic.transcription.analysisId"), false);
    assert.equal(storage.has("seemusic.transcription.tempo"), false);
    assert.equal(storage.has("seemusic.transcription.timeSignature"), false);
    assert.equal(storage.has("seemusic.transcription.keySignature"), false);
});

test("guzheng press-note hints render as wave marks instead of the old 按 label", () => {
    const { api } = loadTranscriptionHarness();

    assert.equal(api.resolveGuzhengPressText({ press_note_candidate: true, open_degree: null }), "∽");
    assert.match(
        api.renderTraditionalPaperOrnaments({ technique_tags: ["按音候选"] }, "guzheng"),
        /∽/
    );
});

test("selection highlight syncs the same MusicXML index to preview and viewer", () => {
    const { api } = loadTranscriptionHarness();
    api.state.editorSelectedMxmlIndex = 4;
    api.els.scoreViewerEntry = buildVerovioHost([
        { measureNo: 1, symbols: [{ kind: "note", attrs: { "data-mxml-index": 4 } }, { kind: "note", attrs: { "data-mxml-index": 1 } }] },
    ]);
    api.els.scoreViewerCanvas = buildVerovioHost([
        { measureNo: 2, symbols: [{ kind: "note", attrs: { "data-mxml-index": 4 } }, { kind: "rest", attrs: { "data-mxml-index": 6 } }] },
    ]);
    api.els.guzhengScoreView = null;
    api.els.diziScoreView = null;
    api.els.guitarLeadSheetView = null;

    api.syncSelectionHighlightToCurrentSelection();

    assert.equal(api.els.scoreViewerEntry.symbols[0].classList.contains("is-selected"), true);
    assert.equal(api.els.scoreViewerEntry.symbols[1].classList.contains("is-selected"), false);
    assert.equal(api.els.scoreViewerCanvas.symbols[0].classList.contains("is-selected"), true);
    assert.equal(api.els.scoreViewerCanvas.symbols[1].classList.contains("is-selected"), false);
});

test("failed click mapping does not leave a fake selected highlight behind", () => {
    const { api } = loadTranscriptionHarness();
    const host = buildVerovioHost([
        { measureNo: 1, symbols: [{ id: "old", kind: "note", attrs: { "data-mxml-index": 1 } }, { id: "new", kind: "note" }] },
    ]);
    host.symbols[0].classList.add("is-selected");
    api.els.scoreViewerEntry = host;
    api.els.scoreViewerCanvas = null;
    api.els.guzhengScoreView = null;
    api.els.diziScoreView = null;
    api.els.guitarLeadSheetView = null;
    api.state.editorSelectedMxmlIndex = 1;
    api.state.selectedNotationElementId = "old";
    api.state.currentScore = null;

    api.handleScoreCanvasInteraction({
        currentTarget: host,
        target: {
            closest() {
                return host.symbols[1];
            },
        },
    });

    assert.equal(host.symbols[0].classList.contains("is-selected"), false);
    assert.equal(host.symbols[1].classList.contains("is-selected"), false);
    assert.equal(api.state.selectedNotationElementId, null);
    assert.equal(api.state.editorSelectedMxmlIndex, null);
    assert.match(api.els.selectedNoteSummary.textContent, /无法定位到 MusicXML/);
    assert.match(api.els.appStatus.textContent, /无法定位到 MusicXML/);
});
