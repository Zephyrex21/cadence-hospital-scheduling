"""Thin repository over the two collections. No business rules here — just reads and
section-wise upserts (``None`` unsets a section)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.mongo.models import SCHEMA_VERSION
from app.mongo.schema import PATIENTS, STAFF


def _public(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc


def _update(
    insert: dict[str, Any],
    sections: dict[str, Any],
    actor_id: int | None,
    extra_set: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(UTC)
    update: dict[str, Any] = {
        "$setOnInsert": {**insert, "schema_version": SCHEMA_VERSION, "created_at": now,
                         "created_by": actor_id},
        "$set": {**{k: v for k, v in sections.items() if v is not None}, **extra_set,
                 "updated_at": now, "updated_by": actor_id},
    }
    cleared = {k: "" for k, v in sections.items() if v is None}
    if cleared:
        update["$unset"] = cleared
    return update


# --- patients -----------------------------------------------------------------------


def get_patient_doc(mdb: Any, patient_id: int) -> dict[str, Any] | None:
    return _public(mdb[PATIENTS].find_one({"patient_id": patient_id}))


def patient_ids_with_docs(mdb: Any) -> set[int]:
    return {d["patient_id"] for d in mdb[PATIENTS].find({}, {"patient_id": 1})}


def upsert_patient_doc(
    mdb: Any, *, patient_id: int, mrn: str, sections: dict[str, Any], actor_id: int | None
) -> dict[str, Any]:
    mdb[PATIENTS].update_one(
        {"patient_id": patient_id},
        _update({"patient_id": patient_id, "mrn": mrn}, sections, actor_id, {}),
        upsert=True,
    )
    doc = get_patient_doc(mdb, patient_id)
    assert doc is not None
    return doc


# --- staff --------------------------------------------------------------------------


def get_staff_doc(mdb: Any, user_id: int) -> dict[str, Any] | None:
    return _public(mdb[STAFF].find_one({"user_id": user_id}))


def staff_docs_by_user(mdb: Any) -> dict[int, dict[str, Any]]:
    return {d["user_id"]: _public(d) or {} for d in mdb[STAFF].find({})}


def upsert_staff_doc(
    mdb: Any, *, user_id: int, role: str, sections: dict[str, Any], actor_id: int | None
) -> dict[str, Any]:
    mdb[STAFF].update_one(
        {"user_id": user_id},
        _update({"user_id": user_id}, sections, actor_id, {"role": role}),
        upsert=True,
    )
    doc = get_staff_doc(mdb, user_id)
    assert doc is not None
    return doc
