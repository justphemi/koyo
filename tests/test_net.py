from koyoapp import net


class _Socket:
    def __init__(self, ip=None, error=None):
        self._ip = ip
        self._error = error
        self.closed = False

    def connect(self, address):
        if self._error is not None:
            raise self._error

    def getsockname(self):
        return (self._ip, 54321)

    def close(self):
        self.closed = True


def test_detect_lan_ip_returns_outbound_address(monkeypatch):
    monkeypatch.setattr(net.socket, "socket", lambda *args, **kwargs: _Socket(ip="192.168.1.42"))
    assert net.detect_lan_ip() == "192.168.1.42"


def test_detect_lan_ip_none_on_connect_failure(monkeypatch):
    monkeypatch.setattr(
        net.socket, "socket", lambda *args, **kwargs: _Socket(error=OSError("no network"))
    )
    assert net.detect_lan_ip() is None


def test_detect_lan_ip_none_on_non_ipv4(monkeypatch):
    monkeypatch.setattr(net.socket, "socket", lambda *args, **kwargs: _Socket(ip="::1"))
    assert net.detect_lan_ip() is None