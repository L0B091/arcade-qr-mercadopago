"""Pruebas rápidas (corren en Linux/Windows sin Mercado Pago real).
python -m pytest tests  ó  python tests/test_basico.py
"""
import hashlib, hmac, os, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["DISABLE_TUNNEL"] = "1"
os.environ["ADMIN_KEY"] = "clave-test"
os.environ["MP_WEBHOOK_SECRET"] = "secreto"
os.environ["KEY_PRESS_DELAY"] = "0"
from app import webhook, db, config  # noqa: E402


def sign(secret, data_id, req_id, ts):
    m = f"id:{data_id};request-id:{req_id};ts:{ts};"
    return f"ts={ts},v1=" + hmac.new(secret.encode(), m.encode(), hashlib.sha256).hexdigest()


def test_firma():
    h = sign("secreto", "123", "req-1", "1704908010")
    assert webhook.validate("secreto", h, "req-1", "123")
    assert not webhook.validate("otro", h, "req-1", "123")
    assert not webhook.validate("secreto", h, "req-1", "999")
    assert not webhook.validate("secreto", "basura", "req-1", "123")


def test_idempotencia():
    db.init()
    assert db.upsert_payment("p1", "pending", "", 2000, "r") is False
    assert db.upsert_payment("p1", "approved", "", 2000, "r") is True   # se acredita
    assert db.upsert_payment("p1", "approved", "", 2000, "r") is False  # aviso repetido
    assert db.pending_credits() == [{"payment_id": "p1", "credits": 1}]  # sobrevive reinicio
    db.mark_credited("p1")
    assert db.pending_credits() == []
    assert db.upsert_payment("p2", "rejected", "", 2000, "r") is False
    s = db.stats()
    assert s["total"]["income"] == 2000 and s["credits_used"] == 1


def test_app_completa():
    from fastapi.testclient import TestClient
    from app import main
    from app.credits import FakePresser
    main.worker.presser = FakePresser()
    main.mercadopago.get_payment = lambda pid: {"status": "approved", "transaction_amount": 2000,
                                                "status_detail": "accredited",
                                                "external_reference": "x"}
    with TestClient(main.app, client=("192.168.1.20", 5000)) as c:
        assert "2.000" in c.get("/").text
        url = "/api/mercadopago/webhook?data.id=555&type=payment"
        body = {"type": "payment", "data": {"id": "555"}}
        assert c.post(url, json=body, headers={"x-signature": "ts=1,v1=mal",
                                               "x-request-id": "a"}).status_code == 401
        for _ in range(3):  # MP manda el mismo aviso varias veces
            h = sign("secreto", "555", "a", "1704908010")
            r = c.post(url, json=body, headers={"x-signature": h, "x-request-id": "a"})
            assert r.status_code == 200
        main.worker.q.join()
        assert main.worker.presser.pressed == [config.CREDIT_KEY]  # 1 sola tecla
        k = {"X-Admin-Key": "clave-test"}
        assert c.get("/api/admin/stats").status_code == 401
        assert c.get("/api/admin/stats", headers={**k, "cf-connecting-ip": "1.2.3.4"}).status_code == 403
        assert c.put("/api/admin/price", json={"price": 2500}, headers=k).json()["price"] == 2500
        assert "2.500" in c.get("/").text
        assert c.get("/api/admin/stats", headers=k).json()["credits_used"] >= 1
        assert c.get("/api/admin/status", headers=k).json()["ok"]




def test_qr_admin():
    from fastapi.testclient import TestClient
    from app import main
    # Sin "with": no arrancamos de nuevo el worker (ya corrió en test_app_completa)
    c = TestClient(main.app, client=("192.168.1.20", 5000))
    if True:
        assert c.get("/api/admin/qr.png").status_code == 401                 # sin clave
        r = c.get("/api/admin/qr.png", headers={"X-Admin-Key": "clave-test"})
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert c.get("/api/admin/qr.png", headers={"X-Admin-Key": "clave-test",
                                                   "cf-ray": "x"}).status_code == 403
        assert c.get("/admin/qr/imprimir").status_code == 401
        assert c.get("/admin/qr/imprimir?key=mal").status_code == 401
        r = c.get("/admin/qr/imprimir?key=clave-test")
        assert r.status_code == 200 and "window.print()" in r.text and "data:image/png" in r.text
        assert c.get("/admin/qr/imprimir?key=clave-test",
                     headers={"cf-connecting-ip": "1.2.3.4"}).status_code == 403
    c = TestClient(main.app, client=("8.8.8.8", 5000))  # IP pública
    assert c.get("/admin/qr/imprimir?key=clave-test").status_code == 403


def test_qr_config():
    assert config.QR_URL == "https://frarcade-26.github.io/"
    assert config.GITHUB_PAGES_REPO == "frarcade-26/frarcade-26.github.io"


if __name__ == "__main__":
    for t in (test_firma, test_idempotencia, test_app_completa, test_qr_admin, test_qr_config):
        t(); print("OK", t.__name__)
