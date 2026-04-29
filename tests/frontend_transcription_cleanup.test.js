const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const html = fs.readFileSync(path.join(__dirname, "../frontend/transcription.html"), "utf8");
const script = fs.readFileSync(path.join(__dirname, "../frontend/transcription.js"), "utf8");
const styles = fs.readFileSync(path.join(__dirname, "../frontend/transcription.css"), "utf8");

test("transcription page no longer exposes lyrics controls or analysis cards", () => {
    assert.ok(!html.includes("lyrics-mode-input"));
    assert.ok(!html.includes("lyrics-file-input"));
    assert.ok(!html.includes("lyrics-import-output"));
    assert.ok(!html.includes("歌词导入"));
});

test("transcription script no longer sends lyrics payloads or renders lyrics summaries", () => {
    [
        'formData.append("lyrics_file"',
        'formData.append("lyrics_mode"',
        "renderLyricsImportPanel",
        "buildLyricsImportSummary",
        "resolveLyricsMode",
        "lyricsImportResult",
    ].forEach((token) => {
        assert.ok(!script.includes(token), `unexpected token: ${token}`);
    });
});

test("traditional jianpu controls no longer render the removed middle-row markup toggle", () => {
    [
        "renderTraditionalMarkupModeToggle",
        "data-jianpu-markup-mode",
        "纯净简谱",
        "带弦位/技法",
        "带指法/技法",
        "完整标注",
        "弦位层",
    ].forEach((token) => {
        assert.ok(!script.includes(token), `unexpected legacy control token: ${token}`);
    });
});

test("guzheng and dizi result heroes no longer render the removed metrics card block", () => {
    [
        "guzheng-sheet-metrics traditional-sheet-metrics",
        "dizi-sheet-metrics traditional-sheet-metrics",
    ].forEach((token) => {
        assert.ok(!script.includes(token), `unexpected legacy metrics block token: ${token}`);
    });
});

test("guzheng and dizi pages no longer expose manual jianpu edit sections", () => {
    [
        "手动编辑视图",
        "点击下方简谱中任意音符即可修改",
        "下方是可交互的 HTML 简谱",
        'const jianpuTarget = event.target.closest(".guzheng-jianpu-note-group[data-mxml-index]");',
    ].forEach((token) => {
        assert.ok(!script.includes(token), `unexpected traditional edit token: ${token}`);
    });

    assert.ok(styles.includes(".traditional-edit-shell"), "legacy edit-shell styles can remain inert without rendering");
});

test("guitar debug process no longer uses collapsed toggle controls", () => {
    [
        "state.guitarDebugExpanded",
        "setGuitarDebugExpanded",
        'renderDebugToggleControl("guitar"',
        "data-guitar-toggle-debug",
    ].forEach((token) => {
        assert.ok(!script.includes(token), `unexpected guitar debug toggle token: ${token}`);
    });
});

test("guitar result hero no longer renders removed score summary cards", () => {
    [
        '${metricCard("调号", escapeHtmlText(songSheet.meta.key))}',
        '${metricCard("拍号", escapeHtmlText(songSheet.meta.timeSignature))}',
        '${metricCard("速度", songSheet.meta.tempo ? `${songSheet.meta.tempo} BPM` : "--")}',
        '${metricCard("小节", songSheet.measures.length || 0)}',
        '<span class="guitar-meta-label">识别质量</span>',
    ].forEach((token) => {
        assert.ok(!script.includes(token), `unexpected guitar score summary token: ${token}`);
    });
});

test("guzheng analysis no longer uses collapsed process toggle state", () => {
    [
        "state.guzhengDebugExpanded",
        "setGuzhengDebugExpanded",
        'renderDebugToggleControl("guzheng"',
        "[data-guzheng-toggle-debug]",
    ].forEach((token) => {
        assert.ok(!script.includes(token), `unexpected guzheng debug toggle token: ${token}`);
    });
});

test("dizi analysis no longer uses collapsed process toggle state", () => {
    [
        "state.diziDebugExpanded",
        "setDiziDebugExpanded",
        'renderDebugToggleControl("dizi"',
        "[data-dizi-toggle-debug]",
    ].forEach((token) => {
        assert.ok(!script.includes(token), `unexpected dizi debug toggle token: ${token}`);
    });
});

test("dizi analysis copy no longer mentions track separation", () => {
    assert.ok(
        !script.includes("上传样例音频并生成笛子谱后，这里可展开查看分离轨、定调结果、可吹性统计与指法候选。"),
        "unexpected legacy dizi analysis copy",
    );
});

test("custom instrument modes force-hide the piano track-separation grid in CSS", () => {
    assert.match(styles, /body\[data-instrument-type="dizi"\] #piano-analysis-grid/);
});

test("transcription page exposes a shared refresh-and-clear workbench button", () => {
    assert.match(html, /id="refresh-workbench-btn"/);
    assert.match(script, /function clearWorkbenchState/);
    assert.match(script, /function handleRefreshWorkbench/);
});
