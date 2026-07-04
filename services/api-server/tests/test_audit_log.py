"""追記専用監査ログ(`api_server.audit.log`)のテスト(E3-7)。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest


def _make_record(action: str = "pmdf.story.create", prev_hash: str | None = None):
    from api_server.audit.log import AuditRecord

    return AuditRecord.create(
        actor="user:tester",
        action=action,
        target_kind="story",
        target_id="story-01HZZZZZZZZZZZZZZZZZZZZZZZ",
        detail={"field": "value"},
        prev_hash=prev_hash,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_append_record_writes_jsonl_line(tmp_path: Path) -> None:
    from api_server.audit.log import append_record

    log_path = tmp_path / "audit.log.jsonl"
    record = _make_record()

    append_record(record, log_path)

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["action"] == "pmdf.story.create"
    assert parsed["actor"] == "user:tester"


def test_append_record_is_append_only(tmp_path: Path) -> None:
    from api_server.audit.log import append_record, read_records

    log_path = tmp_path / "audit.log.jsonl"
    first = _make_record(action="pmdf.story.create")
    append_record(first, log_path)

    records = read_records(log_path)
    second = _make_record(action="pmdf.story.update", prev_hash=records[-1].hash)
    append_record(second, log_path)

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["action"] == "pmdf.story.create"
    assert json.loads(lines[1])["action"] == "pmdf.story.update"


def test_record_hash_depends_on_prev_hash_and_fields(tmp_path: Path) -> None:
    from api_server.audit.log import AuditRecord

    record_a = AuditRecord.create(
        actor="user:a",
        action="pmdf.story.create",
        target_kind="story",
        target_id="story-1",
        detail={},
        prev_hash=None,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )
    record_b = AuditRecord.create(
        actor="user:b",
        action="pmdf.story.create",
        target_kind="story",
        target_id="story-1",
        detail={},
        prev_hash=None,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert record_a.hash != record_b.hash


def test_verify_chain_on_untampered_log_reports_ok(tmp_path: Path) -> None:
    from api_server.audit.log import append_record, verify_chain

    log_path = tmp_path / "audit.log.jsonl"
    record1 = _make_record(action="pmdf.story.create")
    append_record(record1, log_path)
    record2 = _make_record(action="pmdf.story.update", prev_hash=record1.hash)
    append_record(record2, log_path)

    result = verify_chain(log_path)

    assert result.ok is True
    assert result.tampered_line is None


def test_verify_chain_detects_tampering(tmp_path: Path) -> None:
    from api_server.audit.log import append_record, verify_chain

    log_path = tmp_path / "audit.log.jsonl"
    record1 = _make_record(action="pmdf.story.create")
    append_record(record1, log_path)
    record2 = _make_record(action="pmdf.story.update", prev_hash=record1.hash)
    append_record(record2, log_path)

    # 中間行(1行目)を意図的に書き換える。
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    tampered = json.loads(lines[0])
    tampered["actor"] = "user:attacker"
    lines[0] = json.dumps(tampered, ensure_ascii=False)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify_chain(log_path)

    assert result.ok is False
    assert result.tampered_line == 1


def test_verify_chain_on_empty_or_missing_log_reports_ok(tmp_path: Path) -> None:
    from api_server.audit.log import verify_chain

    result = verify_chain(tmp_path / "does-not-exist.jsonl")

    assert result.ok is True
    assert result.tampered_line is None


@pytest.mark.asyncio
async def test_pmdf_create_appends_audit_record(monkeypatch, tmp_path: Path) -> None:
    import json as _json

    from api_server.auth.password import hash_password

    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path / "pmdf-repo"))
    audit_log_path = tmp_path / "audit.log.jsonl"
    monkeypatch.setenv("AUDIT_LOG_PATH", str(audit_log_path))

    user_store_path = tmp_path / "users.json"
    user_store_path.write_text(
        _json.dumps(
            [
                {
                    "id": "user-editor",
                    "email": "editor@example.com",
                    "password_hash": hash_password("editor-pass"),
                    "role": "editor",
                    "totp_secret": None,
                    "product_scopes": None,
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("USER_STORE_PATH", str(user_store_path))

    from api_server.pmdf_store.store import PmdfStore

    PmdfStore.init(tmp_path / "pmdf-repo")

    from api_server.main import create_app
    from httpx import ASGITransport, AsyncClient

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_response = await client.post(
            "/auth/login", json={"email": "editor@example.com", "password": "editor-pass"}
        )
        token = login_response.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"

        response = await client.post(
            "/pmdf/story",
            json={
                "pmdf_version": "1.0.0",
                "kind": "story",
                "id": "story-01HZZZZZZZZZZZZZZZZZZZZZZZ",
                "provenance": {
                    "created_by": "user:tester",
                    "updated_at": "2026-01-01T00:00:00Z",
                },
                "attachments": [],
                "title": "テストストーリー",
                "as_a": "ユーザー",
                "i_want": "機能を使いたい",
                "so_that": "価値を得る",
                "acceptance_criteria": ["条件1"],
                "priority": {"method": "RICE"},
                "status": "draft",
            },
        )
        assert response.status_code == 201, response.text

    assert audit_log_path.exists()
    lines = audit_log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["action"] == "pmdf.story.create"
    assert record["target_id"] == "story-01HZZZZZZZZZZZZZZZZZZZZZZZ"
