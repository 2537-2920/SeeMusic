import xml.etree.ElementTree as ET

import pytest
from fastapi import HTTPException

from backend.api.api_routes import patch_score, score_detail, score_export, score_from_pitch_sequence, score_redo, score_undo
from backend.api.schemas import PitchToScoreRequest, ScoreExportRequest, ScoreUpdateRequest


def _replace_tempo(musicxml: str, tempo: int) -> str:
    root = ET.fromstring(musicxml.encode("utf-8"))
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "per-minute":
            element.text = str(tempo)
        if tag == "sound" and "tempo" in element.attrib:
            element.set("tempo", str(tempo))
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def test_score_routes_happy_path(score_database: dict[str, int | str]):
    create_response = score_from_pitch_sequence(
        PitchToScoreRequest(
            user_id=score_database["user_id"],
            tempo=120,
            time_signature="4/4",
            key_signature="C",
            pitch_sequence=[
                {"time": 0.0, "frequency": 440.0, "duration": 0.5},
                {"time": 0.5, "frequency": 493.88, "duration": 0.5},
            ],
        )
    )
    created_score = create_response["data"]
    score_id = created_score["score_id"]

    detail_response = score_detail(score_id)
    edit_response = patch_score(
        score_id,
        ScoreUpdateRequest(musicxml=_replace_tempo(created_score["musicxml"], 96)),
    )
    edited_score = edit_response["data"]
    assert detail_response["data"]["score_id"] == score_id
    assert edited_score["tempo"] == 96
    assert edited_score["version"] == 2

    undo_response = score_undo(score_id)
    assert undo_response["data"]["tempo"] == 120

    redo_response = score_redo(score_id)
    assert redo_response["data"]["tempo"] == 96

    export_response = score_export(
        score_id,
        ScoreExportRequest(format="pdf", page_size="A4", with_annotations=True),
    )
    export_data = export_response["data"]
    assert export_data["file_name"].endswith(".pdf")
    assert export_data["manifest"]["kind"] == "pdf"


def test_score_routes_return_404_for_missing_score(score_database: dict[str, int | str]):
    with pytest.raises(HTTPException) as exc_info:
        score_export("score_missing", ScoreExportRequest(format="midi", page_size="A4", with_annotations=True))
    assert exc_info.value.status_code == 404
