"""Helpers for transpose suggestion generation."""

from __future__ import annotations

import math
from typing import Any, Iterable

from backend.core.score.key_detection import (
    CANONICAL_MAJOR_KEY_BY_TOKEN,
    CANONICAL_MINOR_KEY_BY_TOKEN,
    MAJOR_KEY_TO_FIFTHS,
    MINOR_KEY_TO_FIFTHS,
)
from backend.core.score.note_mapping import frequency_to_midi, midi_to_note, note_to_midi


VOICE_PROFILE = {
    "male": {
        "lowest_midi": note_to_midi("A2"),
        "highest_midi": note_to_midi("A4"),
        "median_min_midi": note_to_midi("A3"),
        "median_max_midi": note_to_midi("D4"),
        "display_name": "男声",
    },
    "female": {
        "lowest_midi": note_to_midi("F3"),
        "highest_midi": note_to_midi("E5"),
        "median_min_midi": note_to_midi("D4"),
        "median_max_midi": note_to_midi("G4"),
        "display_name": "女声",
    },
}
BASELINE_SUGGESTIONS = {
    ("male", "female"): {"recommended": 4, "alternatives": [3, 5]},
    ("female", "male"): {"recommended": -4, "alternatives": [-3, -5]},
}
PITCH_CLASS_TO_NAME_SHARP = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def _root_name(key_signature: str) -> str:
    return key_signature[:-1] if key_signature.endswith("m") else key_signature


def _mode_name(key_signature: str) -> str:
    return "minor" if key_signature.endswith("m") else "major"


def _tonic_pitch_class(key_signature: str) -> int:
    tonic_midi = note_to_midi(f"{_root_name(key_signature)}4")
    if tonic_midi is None:
        return 0
    return int(tonic_midi % 12)


def _resolve_key_signature(value: str) -> str:
    compact = str(value or "").strip().replace(" ", "")
    if not compact:
        raise ValueError("current_key 不能为空。")

    upper = compact.upper()
    if upper.endswith("M") and len(compact) > 1 and compact[-1].islower():
        resolved = CANONICAL_MINOR_KEY_BY_TOKEN.get(upper)
    else:
        resolved = CANONICAL_MAJOR_KEY_BY_TOKEN.get(upper)
    if not resolved:
        raise ValueError(f"不支持的调号：{value}")
    return resolved


def _choose_key_name_for_pitch_class(pitch_class: int, *, mode: str, prefer_flats: bool) -> str:
    candidates_source = MINOR_KEY_TO_FIFTHS if mode == "minor" else MAJOR_KEY_TO_FIFTHS
    candidates = [
        (key_signature, fifths)
        for key_signature, fifths in candidates_source.items()
        if _tonic_pitch_class(key_signature) == int(pitch_class) % 12
    ]
    if not candidates:
        root = PITCH_CLASS_TO_NAME_SHARP[int(pitch_class) % 12]
        return f"{root}m" if mode == "minor" else root

    def rank(item: tuple[str, int]) -> tuple[int, int, str]:
        key_signature, fifths = item
        has_flat = "b" in _root_name(key_signature)
        return (abs(int(fifths)), 0 if has_flat == prefer_flats else 1, key_signature)

    return min(candidates, key=rank)[0]


def transpose_key_signature(key_signature: str, semitones: int) -> str:
    normalized = _resolve_key_signature(key_signature)
    original_pitch_class = _tonic_pitch_class(normalized)
    prefer_flats = "b" in _root_name(normalized)
    target_pitch_class = (original_pitch_class + int(semitones)) % 12
    return _choose_key_name_for_pitch_class(
        target_pitch_class,
        mode=_mode_name(normalized),
        prefer_flats=prefer_flats,
    )


def _percentile(sorted_values: list[int], ratio: float) -> float:
    if not sorted_values:
        raise ValueError("sorted_values cannot be empty")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    clamped_ratio = max(0.0, min(float(ratio), 1.0))
    position = (len(sorted_values) - 1) * clamped_ratio
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    lower_value = sorted_values[lower]
    upper_value = sorted_values[upper]
    weight = position - lower
    return float(lower_value + (upper_value - lower_value) * weight)


def _extract_voice_profile(pitch_sequence: Iterable[dict[str, Any]] | None) -> dict[str, Any] | None:
    midi_values: list[int] = []
    for item in pitch_sequence or []:
        frequency = item.get("frequency")
        if frequency is None:
            continue
        try:
            midi = frequency_to_midi(float(frequency))
        except (TypeError, ValueError):
            continue
        if midi is None:
            continue
        confidence = item.get("confidence")
        try:
            confidence_value = float(confidence) if confidence is not None else 1.0
        except (TypeError, ValueError):
            confidence_value = 1.0
        if confidence_value <= 0.2:
            continue
        midi_values.append(int(midi))

    if len(midi_values) < 8:
        return None

    sorted_values = sorted(midi_values)
    lowest = round(_percentile(sorted_values, 0.10))
    median = round(_percentile(sorted_values, 0.50))
    highest = round(_percentile(sorted_values, 0.90))
    if highest <= lowest:
        return None
    return {
        "lowest_midi": int(lowest),
        "median_midi": int(median),
        "highest_midi": int(highest),
        "lowest_note": midi_to_note(int(lowest)),
        "median_note": midi_to_note(int(median)),
        "highest_note": midi_to_note(int(highest)),
        "sample_size": len(sorted_values),
    }


def _range_penalty(profile: dict[str, Any], *, target_gender: str, semitones: int) -> int:
    target = VOICE_PROFILE[target_gender]
    transposed_low = int(profile["lowest_midi"]) + int(semitones)
    transposed_mid = int(profile["median_midi"]) + int(semitones)
    transposed_high = int(profile["highest_midi"]) + int(semitones)

    median_min = int(target["median_min_midi"])
    median_max = int(target["median_max_midi"])
    median_penalty = 0
    if transposed_mid < median_min:
        median_penalty = median_min - transposed_mid
    elif transposed_mid > median_max:
        median_penalty = transposed_mid - median_max

    low_penalty = max(int(target["lowest_midi"]) - transposed_low, 0)
    high_penalty = max(transposed_high - int(target["highest_midi"]), 0)
    return median_penalty * 2 + low_penalty + high_penalty


def _resolve_audio_adjustment(
    profile: dict[str, Any] | None,
    *,
    target_gender: str,
    baseline_main: int,
) -> tuple[int, bool]:
    if not profile:
        return 0, False

    best_delta = 0
    best_penalty = None
    for delta in range(-2, 3):
        penalty = _range_penalty(profile, target_gender=target_gender, semitones=baseline_main + delta)
        ranking = (penalty, abs(delta), 0 if delta == 0 else 1)
        if best_penalty is None or ranking < best_penalty:
            best_penalty = ranking
            best_delta = delta
    return best_delta, best_delta != 0


def _baseline_template(source_gender: str, target_gender: str) -> tuple[int, list[dict[str, Any]]]:
    baseline = BASELINE_SUGGESTIONS.get((source_gender, target_gender))
    if baseline:
        main = int(baseline["recommended"])
        alternative_a, alternative_b = sorted(int(value) for value in baseline["alternatives"])
        conservative = alternative_a if abs(alternative_a) < abs(alternative_b) else alternative_b
        expressive = alternative_b if conservative == alternative_a else alternative_a
        return main, [
            {"tier": "recommended", "label": "最推荐", "semitones": main},
            {"tier": "conservative", "label": "偏保守", "semitones": conservative},
            {
                "tier": "bright" if expressive > main else "deep",
                "label": "偏明亮" if expressive > main else "偏低沉",
                "semitones": expressive,
            },
        ]

    return 0, [
        {"tier": "recommended", "label": "最推荐", "semitones": 0},
        {"tier": "lower", "label": "偏低版", "semitones": -2},
        {"tier": "bright", "label": "偏明亮", "semitones": 2},
    ]


def _build_reason(
    *,
    source_gender: str,
    target_gender: str,
    semitones: int,
    current_key: str,
    target_key: str,
    tier: str,
    used_audio_adjustment: bool,
) -> str:
    direction = "升高" if semitones > 0 else "降低" if semitones < 0 else "保持"
    amount = f"{abs(int(semitones))} 个半音" if semitones else "原调"
    source_name = VOICE_PROFILE[source_gender]["display_name"]
    target_name = VOICE_PROFILE[target_gender]["display_name"]
    if semitones == 0:
        base_text = f"当前 {current_key} 调已经接近 {target_name} 的常用舒适区，可先保持原调练唱。"
    else:
        base_text = (
            f"从 {source_name} 常见音区转向 {target_name} 常见音区，建议从 {current_key} 调{direction} {amount} 到 {target_key} 调。"
        )

    if tier == "conservative":
        return f"{base_text} 这档更接近原曲听感，适合先小幅适配。"
    if tier in {"bright", "higher"}:
        return f"{base_text} 这档整体更高更亮，适合需要更靠上声区的版本。"
    if tier in {"deep", "lower"}:
        return f"{base_text} 这档整体更低更稳，适合希望声音更厚实的版本。"
    if used_audio_adjustment:
        return f"{base_text} 已结合本次演唱音域做了微调。"
    return base_text


def _build_summary_text(
    *,
    source_gender: str,
    target_gender: str,
    main_suggestion: dict[str, Any],
    profile: dict[str, Any] | None,
    used_audio_adjustment: bool,
) -> str:
    target_name = VOICE_PROFILE[target_gender]["display_name"]
    if not profile:
        return (
            f"当前没有足够稳定的音域数据，先按 {VOICE_PROFILE[source_gender]['display_name']} 转 {target_name} 的标准规则给出建议："
            f"优先 {main_suggestion['direction_text']} {main_suggestion['amount_text']}。"
        )

    range_text = (
        f"检测到本次演唱的稳定音区约为 {profile['lowest_note']} - {profile['highest_note']}，"
        f"中位音在 {profile['median_note']}。"
    )
    if used_audio_adjustment:
        return f"{range_text} 结合目标 {target_name} 舒适区，建议优先 {main_suggestion['direction_text']} {main_suggestion['amount_text']}。"
    return f"{range_text} 目标 {target_name} 舒适区与标准建议已经基本匹配，可优先采用 {main_suggestion['amount_text']} 的标准变调。"


def generate_transpose_suggestions(
    analysis_id: str,
    current_key: str,
    source_gender: str,
    target_gender: str,
    pitch_sequence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if source_gender not in VOICE_PROFILE:
        raise ValueError(f"不支持的原唱性别：{source_gender}")
    if target_gender not in VOICE_PROFILE:
        raise ValueError(f"不支持的目标性别：{target_gender}")

    normalized_key = _resolve_key_signature(current_key)
    baseline_main, template = _baseline_template(source_gender, target_gender)
    profile = _extract_voice_profile(pitch_sequence)
    adjustment, used_audio_adjustment = _resolve_audio_adjustment(
        profile,
        target_gender=target_gender,
        baseline_main=baseline_main,
    )

    suggestions: list[dict[str, Any]] = []
    for item in template:
        semitones = int(item["semitones"]) + adjustment
        target_key = transpose_key_signature(normalized_key, semitones)
        suggestion = {
            "tier": item["tier"],
            "label": item["label"],
            "semitones": semitones,
            "target_key": target_key,
            "reason": _build_reason(
                source_gender=source_gender,
                target_gender=target_gender,
                semitones=semitones,
                current_key=normalized_key,
                target_key=target_key,
                tier=item["tier"],
                used_audio_adjustment=used_audio_adjustment,
            ),
        }
        suggestion["direction_text"] = "升高" if semitones > 0 else "降低" if semitones < 0 else "保持"
        suggestion["amount_text"] = f"{abs(semitones)} 个半音" if semitones else "原调"
        suggestions.append(suggestion)

    main_suggestion = next(item for item in suggestions if item["tier"] == "recommended")
    summary_text = _build_summary_text(
        source_gender=source_gender,
        target_gender=target_gender,
        main_suggestion=main_suggestion,
        profile=profile,
        used_audio_adjustment=used_audio_adjustment,
    )
    for item in suggestions:
        item.pop("direction_text", None)
        item.pop("amount_text", None)

    return {
        "analysis_id": str(analysis_id),
        "current_key": normalized_key,
        "source_gender": source_gender,
        "target_gender": target_gender,
        "used_audio_adjustment": used_audio_adjustment,
        "detected_range": (
            {
                "lowest_note": profile["lowest_note"],
                "highest_note": profile["highest_note"],
                "median_note": profile["median_note"],
            }
            if profile
            else None
        ),
        "suggestions": suggestions,
        "summary_text": summary_text,
    }
