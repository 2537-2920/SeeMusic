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
    els.projectTitleInput.value = localStorage.getItem(STORAGE_KEYS.title) || "B module live demo";
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
    if (requestOptions.body !== undefined) {
        requestOptions.headers = { "Content-Type": "application/json", ...requestOptions.headers };
        requestOptions.body = JSON.stringify(requestOptions.body);
    }

    const response = await fetch(buildApiUrl(path), requestOptions);
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : await response.text();

    if (!response.ok) {
        const detail =
            (payload && typeof payload === "object" && (payload.detail || payload.message)) || response.statusText;
        throw new Error(detail || "Request failed");
    }
    if (payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "code")) {
        if (payload.code !== 0) {
            throw new Error(payload.message || "Request failed");
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
            throw new Error("Health check failed");
        }
        state.backendHealthy = true;
        setAppStatus("Backend is reachable. You can create and edit scores from this page now.");
    } catch (error) {
        state.backendHealthy = false;
        setAppStatus(`Backend unavailable: ${error.message}`, true);
    } finally {
        renderBackendState();
        setBusy("ping", false);
    }
}

function renderBackendState() {
    els.backendStatusDot.classList.remove("online", "offline");
    els.backendStatusText.textContent = state.backendHealthy ? "Backend online" : "Backend offline";
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
        throw new Error("Pitch sequence JSON must be a non-empty array");
    }
    return parsed;
}

function parsePositiveInteger(value, label) {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed) || parsed <= 0) {
        throw new Error(`${label} must be a positive integer`);
    }
    return parsed;
}

function parsePositiveNumber(value, label) {
    const parsed = Number.parseFloat(value);
    if (!Number.isFinite(parsed) || parsed <= 0) {
        throw new Error(`${label} must be a positive number`);
    }
    return parsed;
}

function normalizePitchInput(rawValue) {
    const value = (rawValue || "").trim();
    if (!value) {
        throw new Error("Pitch is required");
    }
    if (/^rest$/i.test(value)) {
        return "Rest";
    }
    const match = value.match(/^([A-Ga-g])([#b]?)(-?\d+)$/);
    if (!match) {
        throw new Error("Pitch must look like C4, F#4, Bb3, or Rest");
    }
    const letter = match[1].toUpperCase();
    const accidental = match[2] || "";
    const octave = match[3];
    const noteName = accidental === "b" ? FLAT_TO_SHARP[`${letter}b`] : `${letter}${accidental}`;
    if (!Object.prototype.hasOwnProperty.call(NOTE_INDEX, noteName)) {
        throw new Error("Unsupported pitch name");
    }
    return `${noteName}${octave}`;
}

function buildNotePayloadFromInputs() {
    const measureNo = parsePositiveInteger(els.noteMeasureInput.value, "Measure");
    const startBeat = quantizeBeat(parsePositiveNumber(els.noteBeatInput.value, "Beat"));
    const beats = quantizeBeat(parsePositiveNumber(els.noteBeatsInput.value, "Note beats"));
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
        setAppStatus(`API base saved: ${state.apiBase}`);
        await checkBackendConnection();
    } catch (error) {
        setAppStatus(error.message, true);
    }
}

function loadSampleSequence() {
    els.pitchSequenceInput.value = JSON.stringify(DEFAULT_SEQUENCE, null, 2);
    localStorage.setItem(STORAGE_KEYS.pitchSequence, els.pitchSequenceInput.value);
    setAppStatus("Sample pitch sequence loaded. Create score is ready.");
}

function handleClearSequence() {
    els.pitchSequenceInput.value = "";
    localStorage.setItem(STORAGE_KEYS.pitchSequence, "");
    setAppStatus("Pitch sequence input cleared.");
}

async function handleCreateScore() {
    if (isBusy("create-score")) {
        return;
    }
    setBusy("create-score", true);
    try {
        const payload = {
            user_id: parsePositiveInteger(els.userIdInput.value, "User ID"),
            title: (els.projectTitleInput.value || "").trim() || null,
            analysis_id: (els.analysisIdInput.value || "").trim() || null,
            tempo: parsePositiveInteger(els.tempoInput.value, "Tempo"),
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
        setAppStatus(`Score created and linked: ${created.score_id}`);
    } catch (error) {
        setAppStatus(`Create score failed: ${error.message}`, true);
    } finally {
        setBusy("create-score", false);
    }
}

async function handleApplyScoreSettings() {
    try {
        await patchScore(
            [
                { type: "update_tempo", value: parsePositiveInteger(els.tempoInput.value, "Tempo") },
                { type: "update_time_signature", value: (els.timeSignatureInput.value || "").trim() || "4/4" },
                { type: "update_key_signature", value: (els.keySignatureInput.value || "").trim() || "C" },
            ],
            "score-settings",
            "Score settings synced to backend."
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
            "Note added to score.",
            { mode: "new", note: noteDraft.note, measureNo: noteDraft.measureNo }
        );
    } catch (error) {
        setAppStatus(error.message, true);
    }
}

async function handleUpdateSelectedNote() {
    if (!state.selectedNoteId) {
        setAppStatus("Select a note first.", true);
        return;
    }
    try {
        const noteDraft = buildNotePayloadFromInputs();
        await patchScore(
            [{ type: "update_note", note_id: state.selectedNoteId, beat: noteDraft.note.start_beat, note: noteDraft.note }],
            "note-update",
            "Selected note updated.",
            state.selectedNoteId
        );
    } catch (error) {
        setAppStatus(error.message, true);
    }
}

async function handleDeleteSelectedNote() {
    if (!state.selectedNoteId) {
        setAppStatus("Select a note before deleting.", true);
        return;
    }
    await patchScore([{ type: "delete_note", note_id: state.selectedNoteId }], "note-delete", "Selected note deleted.");
}

async function handleTransposeSelected(delta) {
    const selected = getSelectedNoteContext();
    if (!selected || selected.note.is_rest) {
        setAppStatus("Select a pitched note before transposing.", true);
        return;
    }
    await patchScore(
        [{ type: "update_note", note_id: selected.note.note_id, note: { pitch: transposePitch(selected.note.pitch, delta) } }],
        delta > 0 ? "transpose-up" : "transpose-down",
        `Selected note transposed ${delta > 0 ? "up" : "down"} by one semitone.`,
        selected.note.note_id
    );
}

async function handleUndo() {
    await runScoreAction("undo", "undo-action", "Undo applied.");
}

async function handleRedo() {
    await runScoreAction("redo", "redo-action", "Redo applied.");
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
        setAppStatus(`${message} Failed: ${error.message}`, true);
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
        setAppStatus(`Score update failed: ${error.message}`, true);
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
    setAppStatus("Note selection cleared. You can click a measure to prefill a new note.");
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
    renderExportList();
    renderExportDetail();
    renderControlState();
}

function renderScoreSummary() {
    const score = state.currentScore;
    const selected = getSelectedNoteContext();

    els.scoreLinkageStatus.textContent = score ? "Linked" : "Not linked";
    els.scoreTitleDisplay.textContent = score ? score.title || "Untitled score" : "No score loaded";
    els.scoreIdBadge.textContent = score ? score.score_id : "--";
    els.projectIdBadge.textContent = score ? score.project_id : "--";
    els.scoreVersionBadge.textContent = score ? score.version : "--";
    els.tempoDisplay.textContent = score ? score.tempo : "--";
    els.timeDisplay.textContent = score ? score.time_signature : "--";
    els.keyDisplay.textContent = score ? score.key_signature : "--";
    els.measureCountDisplay.textContent = score ? score.measure_count || score.measures.length : "--";
    els.selectedNoteSummary.textContent = selected
        ? `Measure ${selected.measure.measure_no}, beat ${formatBeat(selected.note.start_beat)}, ${selected.note.pitch}, ${formatBeat(selected.note.beats)} beat(s)`
        : "Select a note from the staff or add a new one.";
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
        header.innerHTML = `<span class="measure-index">Measure ${measure.measure_no}</span><span>${formatBeat(measure.used_beats)} / ${formatBeat(measure.total_beats)} beats</span>`;

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
        hint.textContent = "Click to prefill note";
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
            tag.textContent = `${note.pitch} @ ${formatBeat(note.start_beat)}`;
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
    button.title = `${note.pitch}, beat ${formatBeat(note.start_beat)}, duration ${formatBeat(note.beats)}`;
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
        setAppStatus(`Export created: ${created.file_name}`);
    } catch (error) {
        setAppStatus(`Export failed: ${error.message}`, true);
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
        setAppStatus(`Export history load failed: ${error.message}`, true);
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
        setAppStatus(`Export detail load failed: ${error.message}`, true);
    }
}

function renderExportList() {
    els.exportCountBadge.textContent = `${state.exportList.length} record${state.exportList.length === 1 ? "" : "s"}`;
    els.exportEmpty.hidden = state.exportList.length > 0;
    els.exportList.innerHTML = "";

    state.exportList.forEach((item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `export-item ${item.export_record_id === state.selectedExportRecordId ? "active" : ""}`;
        button.dataset.exportId = item.export_record_id;
        button.innerHTML = `
            <div class="export-row">
                <span class="export-title">${item.file_name || `Export ${item.export_record_id}`}</span>
                <span class="format-badge">${String(item.format || "").toUpperCase()}</span>
            </div>
            <div class="export-row">
                <span>${formatDate(item.updated_at || item.created_at)}</span>
                <span>${item.exists ? formatBytes(item.size_bytes) : "Missing"}</span>
            </div>
        `;
        els.exportList.appendChild(button);
    });
}

function renderExportDetail() {
    const detail = state.selectedExportDetail;
    els.previewEmpty.hidden = Boolean(detail);
    els.previewTitle.textContent = detail ? detail.file_name || `Export ${detail.export_record_id}` : "Nothing selected";
    els.detailFormat.textContent = detail ? String(detail.format || "").toUpperCase() : "--";
    els.detailSize.textContent = detail ? formatBytes(detail.size_bytes) : "--";
    els.detailUpdated.textContent = detail ? formatDate(detail.updated_at || detail.created_at) : "--";
    els.detailStatus.textContent = detail ? (detail.exists ? "Ready" : "File missing") : "--";
    els.previewStage.innerHTML = "";

    if (!detail) {
        els.previewStage.appendChild(els.previewEmpty);
        return;
    }
    if (!detail.exists) {
        els.previewStage.appendChild(buildPreviewMessage("The export record exists but the file is missing."));
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
        image.alt = detail.file_name || "Score export preview";
        els.previewStage.appendChild(image);
        return;
    }
    els.previewStage.appendChild(
        buildPreviewMessage("This format is not previewable inline yet. Use the download button to open it locally.")
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
        setAppStatus(`Export regenerated: ${regenerated.file_name}`);
    } catch (error) {
        setAppStatus(`Regenerate failed: ${error.message}`, true);
    } finally {
        setBusy("regenerate-export", false);
    }
}

function handleDownloadSelectedExport() {
    const detail = state.selectedExportDetail;
    if (!detail || !detail.exists) {
        setAppStatus("Select a ready export before downloading.", true);
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
    if (!window.confirm("Delete the selected export record and its file if unused elsewhere?")) {
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
        setAppStatus(`Export ${deletedId} deleted.`);
    } catch (error) {
        setAppStatus(`Delete export failed: ${error.message}`, true);
    } finally {
        setBusy("delete-export", false);
    }
}

function renderControlState() {
    const hasScore = Boolean(state.currentScore);
    const hasSelectedNote = Boolean(getSelectedNoteContext());
    const hasExport = Boolean(state.selectedExportDetail);

    els.pingBackendBtn.disabled = isBusy("ping");
    els.createScoreBtn.disabled = isBusy("create-score");
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
