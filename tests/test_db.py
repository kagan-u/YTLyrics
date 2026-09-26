import pytest

from ytlyrics.core.db import Database
from ytlyrics.core.models import Status


@pytest.fixture()
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_add_and_dedupe(db):
    a = db.add_request("Artist", "Song")
    b = db.add_request("artist", "song")
    assert a is not None
    assert b is None


def test_claim_next_order(db):
    db.add_request("A", "One")
    db.add_request("B", "Two")
    first = db.claim_next()
    assert first["title"] == "One"
    second = db.claim_next()
    assert second["title"] == "Two"
    assert db.claim_next() is None


def test_state_transitions(db):
    rid = db.add_request("A", "One")
    db.claim_next()
    assert db.set_status(rid, Status.ALIGNING)
    assert db.set_status(rid, Status.RENDERING)
    assert db.set_status(rid, Status.UPLOADING)
    assert db.set_status(rid, Status.DONE)
    # terminal states cannot move
    assert not db.set_status(rid, Status.QUEUED)


def test_invalid_transition_blocked(db):
    rid = db.add_request("A", "One")
    db.claim_next()  # -> downloading
    assert not db.set_status(rid, Status.DONE)  # skip stages
    assert db.set_status(rid, Status.CANCELLED)


def test_cancel_queued(db):
    rid = db.add_request("A", "One")
    assert db.cancel(rid)
    assert db.get_request(rid)["status"] == Status.CANCELLED.value
    # cancelled can be retried
    assert db.retry(rid)
    assert db.get_request(rid)["status"] == Status.QUEUED.value


def test_comment_seen(db):
    assert not db.has_comment_seen("c1")
    assert db.mark_comment_seen("c1")
    assert db.has_comment_seen("c1")
    assert not db.mark_comment_seen("c1")


def test_stats(db):
    db.add_request("A", "One")
    db.add_request("B", "Two")
    db.claim_next()
    s = db.stats()
    assert s["queued"] == 1
    assert s["downloading"] == 1


def test_recover_stale(db):
    stuck = db.add_request("A", "One")
    db.claim_next()  # -> downloading, simulates killed app
    db.set_progress(stuck, 0.42)
    done = db.add_request("B", "Two")
    db.claim_next()
    for s in (
        Status.ALIGNING,
        Status.RENDERING,
        Status.UPLOADING,
        Status.DONE,
    ):
        assert db.set_status(done, s)
    assert db.recover_stale() == 1
    r = db.get_request(stuck)
    assert r["status"] == Status.QUEUED.value
    assert r["progress"] == 0.0
    assert db.get_request(done)["status"] == Status.DONE.value
    assert db.recover_stale() == 0
