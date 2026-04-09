"""Tests for cli/commands/connect.py."""

from cli.commands.connect import cmd_connect


class _DummyStatus:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyConsole:
    def status(self, _message):
        return _DummyStatus()


class _DummySession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _DetachedLikeAccount:
    """Raises if attributes are read after session close."""

    def __init__(self, session):
        self._session = session

    @property
    def id(self):
        if self._session.closed:
            raise RuntimeError("id accessed after session close")
        return "12345678-abcd"

    @property
    def display_name(self):
        if self._session.closed:
            raise RuntimeError("display_name accessed after session close")
        return "test-user"


def test_cmd_connect_reads_account_fields_before_session_close(monkeypatch):
    session = _DummySession()
    success_messages = []

    def fake_get_session():
        return session

    def fake_connect(_session, _provider, _api_key):
        return _DetachedLikeAccount(_session)

    def fake_print_success(message):
        success_messages.append(message)

    monkeypatch.setattr("db.session.get_session", fake_get_session)
    monkeypatch.setattr("services.connect_service.connect", fake_connect)
    monkeypatch.setattr("utils.console.console", _DummyConsole())
    monkeypatch.setattr("utils.console.print_success", fake_print_success)
    monkeypatch.setattr("utils.console.print_error", lambda _msg: None)

    cmd_connect("openai", "dummy-key")

    assert session.closed is True
    assert len(success_messages) == 1
    assert "Connected" in success_messages[0]
    assert "test-user" in success_messages[0]
    assert "12345678" in success_messages[0]

