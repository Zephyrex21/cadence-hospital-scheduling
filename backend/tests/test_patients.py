"""Patient endpoint tests, including role-based access control."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.core.enums import Role
from app.models.user import User

_PATIENT = {"name": "Jane Doe", "date_of_birth": "1990-06-15", "sex": "female"}


def test_receptionist_can_register_patient(
    client: TestClient,
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    recep = user_factory(Role.RECEPTIONIST)
    resp = client.post("/patients", json=_PATIENT, headers=auth_headers(recep))
    assert resp.status_code == 201
    body = resp.json()
    assert body["mrn"].startswith("CAD-")
    assert body["name"] == "Jane Doe"


def test_doctor_cannot_register_patient(
    client: TestClient,
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    doctor = user_factory(Role.DOCTOR)
    resp = client.post("/patients", json=_PATIENT, headers=auth_headers(doctor))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_list_patients_requires_auth(client: TestClient) -> None:
    assert client.get("/patients").status_code == 401


def test_search_filters_by_name(
    client: TestClient,
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    recep = user_factory(Role.RECEPTIONIST)
    headers = auth_headers(recep)
    client.post("/patients", json=_PATIENT, headers=headers)
    client.post(
        "/patients",
        json={"name": "Bob Smith", "date_of_birth": "1985-01-01", "sex": "male"},
        headers=headers,
    )

    resp = client.get("/patients", params={"q": "jane"}, headers=headers)
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert names == ["Jane Doe"]


def test_get_missing_patient_is_404(
    client: TestClient,
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    recep = user_factory(Role.RECEPTIONIST)
    resp = client.get("/patients/9999", headers=auth_headers(recep))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
