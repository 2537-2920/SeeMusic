(function (root, factory) {
    const api = factory();
    if (typeof module === "object" && module.exports) {
        module.exports = api;
    }
    if (root) {
        root.SeeMusicScoreViewerLayout = api;
    }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
    const DEFAULT_VIEWER_LAYOUT_OPTIONS = {
        minMeasuresPerSystem: 4,
        maxMeasuresPerSystem: 6,
        systemsPerPage: 5,
        targetComplexityPerSystem: 12.5,
        splitMidi: 60,
        defaultStaff: "treble",
    };

    const STEP_TO_SEMITONE = {
        C: 0,
        D: 2,
        E: 4,
        F: 5,
        G: 7,
        A: 9,
        B: 11,
    };

    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }

    function roundValue(value, digits) {
        const factor = 10 ** digits;
        return Math.round(Number(value || 0) * factor) / factor;
    }

    function pitchToMidi(pitch) {
        if (!pitch || pitch === "Rest") {
            return null;
        }
        const match = String(pitch).trim().match(/^([A-Ga-g])([#b]?)(-?\d+)$/);
        if (!match) {
            return null;
        }
        const [, stepRaw, accidental, octaveRaw] = match;
        const step = stepRaw.toUpperCase();
        const octave = Number.parseInt(octaveRaw, 10);
        if (!Number.isFinite(octave) || !(step in STEP_TO_SEMITONE)) {
            return null;
        }
        const alter = accidental === "#" ? 1 : accidental === "b" ? -1 : 0;
        return (octave + 1) * 12 + STEP_TO_SEMITONE[step] + alter;
    }

    function normalizeStaffName(staffName, fallback) {
        const normalized = String(staffName || fallback || DEFAULT_VIEWER_LAYOUT_OPTIONS.defaultStaff).toLowerCase();
        return normalized === "bass" ? "bass" : "treble";
    }

    function assignStaffForPitch(pitch, options) {
        const config = { ...DEFAULT_VIEWER_LAYOUT_OPTIONS, ...(options || {}) };
        const midi = pitchToMidi(pitch);
        if (midi == null) {
            return normalizeStaffName(config.defaultStaff);
        }
        return midi >= config.splitMidi ? "treble" : "bass";
    }

    function assignStaffSequence(items, options) {
        const config = { ...DEFAULT_VIEWER_LAYOUT_OPTIONS, ...(options || {}) };
        const resolved = (items || []).map((item) => {
            const isRest = Boolean(item?.isRest) || String(item?.pitch || "") === "Rest";
            if (!isRest) {
                return assignStaffForPitch(item?.pitch, config);
            }
            return null;
        });

        for (let index = 0; index < resolved.length; index += 1) {
            if (resolved[index]) {
                continue;
            }
            let previous = null;
            for (let scan = index - 1; scan >= 0; scan -= 1) {
                if (resolved[scan]) {
                    previous = resolved[scan];
                    break;
                }
            }
            let next = null;
            for (let scan = index + 1; scan < resolved.length; scan += 1) {
                if (resolved[scan]) {
                    next = resolved[scan];
                    break;
                }
            }
            resolved[index] = previous || next || normalizeStaffName(config.defaultStaff);
        }

        return resolved;
    }

    function scoreMeasureComplexity(measure) {
        const notes = Array.isArray(measure?.notes) ? measure.notes : [];
        if (!notes.length) {
            return 1.2;
        }

        let complexity = 0.85;
        let pitchedCount = 0;
        let restCount = 0;
        let shortValues = 0;
        let denseValues = 0;
        let accidentals = 0;
        let ties = 0;
        let slurs = 0;
        let dots = 0;

        notes.forEach((note) => {
            const isRest = Boolean(note?.isRest) || String(note?.pitch || "") === "Rest";
            const beats = Number(note?.beats || 0);
            if (isRest) {
                restCount += 1;
                complexity += 0.3;
            } else {
                pitchedCount += 1;
                complexity += 0.8;
            }

            if (beats > 0 && beats <= 1) {
                shortValues += 1;
                complexity += 0.38;
            }
            if (beats > 0 && beats <= 0.5) {
                denseValues += 1;
                complexity += 0.55;
            }

            const accidentalWeight = Math.abs(Number(note?.alter || 0)) + (note?.hasAccidental ? 1 : 0);
            accidentals += accidentalWeight;
            complexity += accidentalWeight * 0.28;

            const tieWeight = Number(note?.tieCount || 0);
            ties += tieWeight;
            complexity += tieWeight * 0.35;

            const slurWeight = Number(note?.slurCount || 0);
            slurs += slurWeight;
            complexity += slurWeight * 0.25;

            const dotWeight = Number(note?.dotCount || 0);
            dots += dotWeight;
            complexity += dotWeight * 0.12;
        });

        if (pitchedCount && pitchedCount <= 2 && !denseValues && !accidentals && !ties && !slurs) {
            complexity -= 0.45;
        }
        if (pitchedCount + restCount >= 6) {
            complexity += 0.45;
        }

        return roundValue(Math.max(complexity, 0.8), 2);
    }

    function rebalanceTrailingSystem(systems, minMeasuresPerSystem) {
        if (systems.length < 2) {
            return systems;
        }

        const trailing = systems[systems.length - 1];
        const previous = systems[systems.length - 2];
        while (
            trailing.measures.length < minMeasuresPerSystem &&
            previous.measures.length > minMeasuresPerSystem
        ) {
            trailing.measures.unshift(previous.measures.pop());
        }

        previous.measureCount = previous.measures.length;
        previous.measureIndices = previous.measures.map((measure) => measure.index);
        previous.startMeasureNo = previous.measures[0]?.measureNo || previous.startMeasureNo;
        previous.endMeasureNo = previous.measures[previous.measures.length - 1]?.measureNo || previous.endMeasureNo;
        previous.complexity = roundValue(
            previous.measures.reduce((total, measure) => total + measure.complexity, 0),
            2
        );

        trailing.measureCount = trailing.measures.length;
        trailing.measureIndices = trailing.measures.map((measure) => measure.index);
        trailing.startMeasureNo = trailing.measures[0]?.measureNo || trailing.startMeasureNo;
        trailing.endMeasureNo = trailing.measures[trailing.measures.length - 1]?.measureNo || trailing.endMeasureNo;
        trailing.complexity = roundValue(
            trailing.measures.reduce((total, measure) => total + measure.complexity, 0),
            2
        );

        return systems;
    }

    function createSystemRecord(measures, systemIndex) {
        return {
            index: systemIndex,
            measures,
            measureCount: measures.length,
            measureIndices: measures.map((measure) => measure.index),
            startMeasureNo: measures[0]?.measureNo || 1,
            endMeasureNo: measures[measures.length - 1]?.measureNo || measures[0]?.measureNo || 1,
            complexity: roundValue(measures.reduce((total, measure) => total + measure.complexity, 0), 2),
        };
    }

    function groupMeasuresIntoSystems(measures, options) {
        const config = { ...DEFAULT_VIEWER_LAYOUT_OPTIONS, ...(options || {}) };
        const normalized = (measures || []).map((measure, index) => ({
            ...measure,
            index,
            measureNo: Number(measure?.measureNo || measure?.number || index + 1),
            complexity: Number(measure?.complexity || scoreMeasureComplexity(measure)),
        }));

        if (!normalized.length) {
            return [];
        }

        const systems = [];
        let currentMeasures = [];
        let currentComplexity = 0;

        normalized.forEach((measure) => {
            const nextComplexity = currentComplexity + measure.complexity;
            const shouldBreakForMax = currentMeasures.length >= config.maxMeasuresPerSystem;
            const shouldBreakForBudget =
                currentMeasures.length >= config.minMeasuresPerSystem &&
                nextComplexity > config.targetComplexityPerSystem;

            if (currentMeasures.length && (shouldBreakForMax || shouldBreakForBudget)) {
                systems.push(createSystemRecord(currentMeasures, systems.length));
                currentMeasures = [];
                currentComplexity = 0;
            }

            currentMeasures.push(measure);
            currentComplexity += measure.complexity;
        });

        if (currentMeasures.length) {
            systems.push(createSystemRecord(currentMeasures, systems.length));
        }

        return rebalanceTrailingSystem(systems, config.minMeasuresPerSystem);
    }

    function paginateSystems(systems, options) {
        const config = { ...DEFAULT_VIEWER_LAYOUT_OPTIONS, ...(options || {}) };
        const pages = [];

        for (let index = 0; index < (systems || []).length; index += config.systemsPerPage) {
            const pageSystems = systems.slice(index, index + config.systemsPerPage);
            const measureIndices = pageSystems.flatMap((system) => system.measureIndices);
            const measureNumbers = pageSystems.flatMap((system) =>
                system.measures.map((measure) => measure.measureNo)
            );
            pages.push({
                index: pages.length,
                systems: pageSystems,
                systemCount: pageSystems.length,
                measureIndices,
                startMeasureNo: measureNumbers[0] || 1,
                endMeasureNo: measureNumbers[measureNumbers.length - 1] || measureNumbers[0] || 1,
            });
        }

        return pages;
    }

    function buildViewerPagination(measures, options) {
        const config = { ...DEFAULT_VIEWER_LAYOUT_OPTIONS, ...(options || {}) };
        const systems = groupMeasuresIntoSystems(measures, config);
        const pages = paginateSystems(systems, config);
        return {
            measures: (measures || []).map((measure, index) => ({
                ...measure,
                index,
            })),
            systems,
            pages,
            pageRanges: pages.map((page) => ({
                pageIndex: page.index,
                startMeasureNo: page.startMeasureNo,
                endMeasureNo: page.endMeasureNo,
            })),
        };
    }

    return {
        DEFAULT_VIEWER_LAYOUT_OPTIONS,
        assignStaffForPitch,
        assignStaffSequence,
        buildViewerPagination,
        clamp,
        groupMeasuresIntoSystems,
        paginateSystems,
        pitchToMidi,
        scoreMeasureComplexity,
    };
});
