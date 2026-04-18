const test = require("node:test");
const assert = require("node:assert/strict");

const {
    assignStaffForPitch,
    assignStaffSequence,
    buildViewerPagination,
    groupMeasuresIntoSystems,
    scoreMeasureComplexity,
} = require("../frontend/score_viewer_layout.js");

function makeMeasure(measureNo, notes) {
    return { measureNo, notes };
}

const SIMPLE_MEASURES = Array.from({ length: 6 }, (_, index) =>
    makeMeasure(index + 1, [
        { pitch: "C4", beats: 2, isRest: false, alter: 0, tieCount: 0, slurCount: 0, dotCount: 0 },
        { pitch: "E4", beats: 2, isRest: false, alter: 0, tieCount: 0, slurCount: 0, dotCount: 0 },
    ])
);

const DENSE_MEASURES = Array.from({ length: 8 }, (_, index) =>
    makeMeasure(index + 1, [
        { pitch: "C4", beats: 0.5, isRest: false, alter: 0, tieCount: 0, slurCount: 1, dotCount: 0 },
        { pitch: "D#4", beats: 0.5, isRest: false, alter: 1, tieCount: 1, slurCount: 1, dotCount: 0 },
        { pitch: "E4", beats: 0.5, isRest: false, alter: 0, tieCount: 1, slurCount: 0, dotCount: 0 },
        { pitch: "F#4", beats: 0.5, isRest: false, alter: 1, tieCount: 0, slurCount: 1, dotCount: 0 },
        { pitch: "G4", beats: 0.5, isRest: false, alter: 0, tieCount: 0, slurCount: 0, dotCount: 1 },
        { pitch: "A4", beats: 0.5, isRest: false, alter: 0, tieCount: 0, slurCount: 0, dotCount: 0 },
        { pitch: "B4", beats: 0.5, isRest: false, alter: 0, tieCount: 0, slurCount: 0, dotCount: 0 },
        { pitch: "C5", beats: 0.5, isRest: false, alter: 0, tieCount: 0, slurCount: 0, dotCount: 0 },
    ])
);

const WIDE_REGISTER_EVENTS = [
    { pitch: "G2", isRest: false },
    { pitch: "Rest", isRest: true },
    { pitch: "C5", isRest: false },
    { pitch: "Rest", isRest: true },
    { pitch: "A3", isRest: false },
];

test("simple measures stay light enough to pack six bars in one system", () => {
    const simpleComplexity = scoreMeasureComplexity(SIMPLE_MEASURES[0]);
    const denseComplexity = scoreMeasureComplexity(DENSE_MEASURES[0]);

    assert.ok(simpleComplexity < denseComplexity);

    const systems = groupMeasuresIntoSystems(SIMPLE_MEASURES);
    assert.equal(systems.length, 1);
    assert.equal(systems[0].measureCount, 6);
});

test("dense measures rebalance to four bars per system", () => {
    const systems = groupMeasuresIntoSystems(DENSE_MEASURES);

    assert.equal(systems.length, 2);
    assert.deepEqual(
        systems.map((system) => system.measureCount),
        [4, 4]
    );
});

test("pagination caps each page at five systems", () => {
    const manyMeasures = Array.from({ length: 36 }, (_, index) =>
        makeMeasure(index + 1, [
            { pitch: "C4", beats: 2, isRest: false, alter: 0, tieCount: 0, slurCount: 0, dotCount: 0 },
            { pitch: "G4", beats: 2, isRest: false, alter: 0, tieCount: 0, slurCount: 0, dotCount: 0 },
        ])
    );

    const pagination = buildViewerPagination(manyMeasures);
    assert.equal(pagination.pages.length, 2);
    assert.equal(pagination.pages[0].systemCount, 5);
    assert.equal(pagination.pages[1].systemCount, 1);
    assert.deepEqual(pagination.pageRanges[0], { pageIndex: 0, startMeasureNo: 1, endMeasureNo: 30 });
});

test("staff assignment prefers treble at C4 and above, bass below B3", () => {
    assert.equal(assignStaffForPitch("C4"), "treble");
    assert.equal(assignStaffForPitch("B3"), "bass");
    assert.equal(assignStaffForPitch("A5"), "treble");
    assert.equal(assignStaffForPitch("F2"), "bass");
});

test("rests inherit nearby register when assigning grand staff display", () => {
    const staffs = assignStaffSequence(WIDE_REGISTER_EVENTS);
    assert.deepEqual(staffs, ["bass", "bass", "treble", "treble", "bass"]);
});
