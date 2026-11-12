"""Storage integrity and real Tk interaction checks, beside the app source."""

import json
import threading
import time
import tkinter as tk

import pytest

from portable_pipe_tools.defect_doctor.app import DoctorApp
from portable_pipe_tools.defect_doctor.storage import InstanceLock, Session, Store, default_data_dir


def test_history_round_trip_preserves_unicode_drafts_and_sessions(tmp_path):
    store = Store(tmp_path)
    first = Session()
    first.add("user", "My project won’t open 🩺\nHere are the details.")
    first.add("assistant", "Let’s take a look.")
    first.draft = "Unsaved-to-chat follow-up\n第二行"
    store.save(first)
    second = Session(title="Another issue")
    store.save(second)
    restored = Store(tmp_path)
    assert restored.load(first.id) == first
    assert {session.id for session in restored.list_sessions()} == {first.id, second.id}
    assert len(list((tmp_path / "sessions").glob("*.json"))) == 2
    assert not list((tmp_path / "sessions").glob("*.tmp"))


def test_failed_atomic_replace_keeps_original_and_removes_temporary(tmp_path, monkeypatch):
    store = Store(tmp_path)
    session = Session()
    session.add("user", "Original")
    store.save(session)
    original = store._session_path(session.id).read_bytes()
    session.add("user", "New message")

    def fail(*args):
        raise OSError("Disk full")

    monkeypatch.setattr("portable_pipe_tools.defect_doctor.storage.os.replace", fail)
    with pytest.raises(OSError, match="Disk full"):
        store.save(session)
    assert store._session_path(session.id).read_bytes() == original
    assert not list((tmp_path / "sessions").glob("*.tmp"))


def test_corrupt_history_is_skipped_and_never_overwritten(tmp_path):
    store = Store(tmp_path)
    session = Session()
    store.save(session)
    broken = Session()
    path = store._session_path(broken.id)
    path.write_text("{broken", encoding="utf-8")
    assert store.list_sessions() == [session]
    assert broken.id in store.warnings[0]
    assert path.read_text() == "{broken"


def test_history_ids_cannot_escape_storage_directory(tmp_path):
    store = Store(tmp_path)
    with pytest.raises(ValueError):
        store.load("../../outside")


def test_unknown_format_is_left_untouched(tmp_path):
    store = Store(tmp_path)
    session = Session()
    store.save(session)
    path = store._session_path(session.id)
    value = json.loads(path.read_text())
    value["version"] = 99
    path.write_text(json.dumps(value))
    assert store.list_sessions() == []
    assert "Unsupported" in store.warnings[0]
    assert json.loads(path.read_text())["version"] == 99


def test_second_instance_cannot_overwrite_same_history(tmp_path):
    lock = InstanceLock(tmp_path)
    try:
        with pytest.raises(RuntimeError, match="already using"):
            InstanceLock(tmp_path)
    finally:
        lock.close()
    next_lock = InstanceLock(tmp_path)
    next_lock.close()


def test_data_directory_override(tmp_path, monkeypatch):
    monkeypatch.setenv("DEFECT_DOCTOR_DATA_DIR", str(tmp_path))
    assert default_data_dir() == tmp_path.resolve()


@pytest.fixture
def app(tmp_path):
    root = tk.Tk()
    root.withdraw()
    errors = []
    root.report_callback_exception = lambda kind, value, trace: errors.append(value)
    window = DoctorApp(root, Store(tmp_path))
    yield window
    if not window.closed:
        window.close()
    assert not errors, f"Tk callback errors: {errors}"


def test_local_send_switch_draft_search_and_restart(app):
    app.composer.insert("1.0", "Krita keeps crashing")
    app.submit()
    first = app.session
    assert len(first.messages) == 1
    assert first.messages[0].role == "user"
    assert "no message has been sent" in app.status.get()
    assert not app.agent.connected
    assert str(app.access_button.cget("state")) == "disabled"
    app.composer.insert("1.0", "My draft follow-up")
    app.new_session()
    second = app.session
    assert second.id != first.id
    assert app.store.load(first.id).draft == "My draft follow-up"
    app.composer.insert("1.0", "Render issue")
    app.submit()
    app.select_session(first)
    assert app.composer.get("1.0", "end-1c") == "My draft follow-up"
    assert "Krita keeps crashing" in app.transcript.get("1.0", "end-1c")
    app.search.set("crashing")
    assert len(app.session_panel.body.winfo_children()) == 1
    app.close()
    root = tk.Tk()
    root.withdraw()
    reopened = DoctorApp(root, Store(app.store.directory))
    try:
        assert reopened.session.id == first.id
        assert reopened.composer.get("1.0", "end-1c") == "My draft follow-up"
        assert len(reopened.sessions) == 2
    finally:
        reopened.close()


def test_empty_message_and_duplicate_empty_session_are_ignored(app):
    app.composer.insert("1.0", "   \n")
    app.submit()
    assert not app.session.messages
    app.composer.delete("1.0", "end")
    app.new_session()
    app.new_session()
    assert len(app.sessions) == 1


def test_save_failure_retains_composer_and_prior_history(app, monkeypatch):
    app.composer.insert("1.0", "Do not lose this")
    errors = []
    monkeypatch.setattr("portable_pipe_tools.defect_doctor.app.messagebox.showerror", lambda *a, **k: errors.append(a))
    original_save = app.store.save

    def fail(session):
        raise OSError("Disk full")

    monkeypatch.setattr(app.store, "save", fail)
    app.submit()
    assert not app.session.messages
    assert app.session.title == "New session"
    assert app.composer.get("1.0", "end-1c") == "Do not lose this"
    assert errors
    monkeypatch.setattr(app.store, "save", original_save)
    app.submit()
    assert app.store.load(app.session.id).messages[0].content == "Do not lose this"


def test_switching_sessions_retries_unsaved_reply_even_with_unchanged_draft(app, monkeypatch):
    app.composer.insert("1.0", "Help")
    app.submit()
    first = app.session
    app.new_session()
    second = app.session
    app.select_session(first)
    first.add("assistant", "Reply awaiting a successful disk save")
    errors = []
    monkeypatch.setattr("portable_pipe_tools.defect_doctor.app.messagebox.showerror", lambda *a, **k: errors.append(a))
    original_save = app.store.save

    def fail(session):
        raise OSError("Disk full")

    monkeypatch.setattr(app.store, "save", fail)
    app.select_session(second)
    assert app.session is first
    assert errors
    monkeypatch.setattr(app.store, "save", original_save)
    app.select_session(second)
    assert app.session is second
    assert app.store.load(first.id).messages[-1].content == "Reply awaiting a successful disk save"


class FakeAgent:
    name = "Test Hermes"
    connected = True

    def reply(self, messages, cancel):
        assert threading.current_thread() is not threading.main_thread()
        assert messages[-1].content == "Help"
        yield "Hello "
        yield "from Hermes."


def pump_until(root, predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        root.update()
        time.sleep(.01)
    assert predicate(), "UI did not finish before timeout"


def test_injected_agent_replies_on_worker_thread_and_persists(app):
    app.agent = FakeAgent()
    app.composer.insert("1.0", "Help")
    app.submit()
    pump_until(app.root, lambda: not app.busy)
    assert app.session.messages[-1].content == "Hello from Hermes."
    assert app.store.load(app.session.id).messages[-1].role == "assistant"
    assert str(app.composer.cget("state")) == "normal"


def test_agent_error_preserves_user_message_and_recovers_ui(app, monkeypatch):
    errors = []
    monkeypatch.setattr("portable_pipe_tools.defect_doctor.app.messagebox.showerror", lambda *a, **k: errors.append(a))

    class BrokenAgent(FakeAgent):
        def reply(self, messages, cancel):
            raise ConnectionError("Service offline")

    app.agent = BrokenAgent()
    app.composer.insert("1.0", "Help")
    app.submit()
    pump_until(app.root, lambda: not app.busy)
    assert "Service offline" in app.status.get()
    assert "Service offline" in errors[0][1]
    assert len(app.store.load(app.session.id).messages) == 1
    assert str(app.new_button.cget("state")) == "normal"


def test_stopping_reply_persists_received_text(app):
    release = threading.Event()

    class SlowAgent(FakeAgent):
        def reply(self, messages, cancel):
            yield "Partial answer"
            release.wait(2)
            yield " should not appear"

    app.agent = SlowAgent()
    app.composer.insert("1.0", "Help")
    app.submit()
    pump_until(app.root, lambda: app.reply_message is not None)
    app.stop_reply()
    release.set()
    pump_until(app.root, lambda: not app.busy)
    assert app.store.load(app.session.id).messages[-1].content == "Partial answer"
    assert "stopped" in app.status.get()
