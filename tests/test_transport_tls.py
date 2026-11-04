"""Native TLS fixture verifies the HTTP adapter's CA, SNI and host checks."""

from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import ssl
import threading

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from app.providers import Provider


@pytest.fixture
def tls_endpoint(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Aptilume TLS fixture CA")]
    )
    ca = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
        .sign(ca_key, hashes.SHA256())
    )
    key = ec.generate_private_key(ec.SECP256R1())
    cert = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "llm.fixture.test")])
        )
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("llm.fixture.test")]), False
        )
        .sign(ca_key, hashes.SHA256())
    )
    cafile = tmp_path / "ca.pem"
    certfile = tmp_path / "server.pem"
    keyfile = tmp_path / "server.key"
    cafile.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    keyfile.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["content-length"]))
            seen["host"] = self.headers["Host"]
            body = json.dumps(
                {
                    "choices": [
                        {"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}
                    ]
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile, keyfile)
    context.set_servername_callback(lambda sock, name, ctx: seen.update(sni=name))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Trusted test-only injection; no resolver hook is exposed in the application API.
    monkeypatch.setattr("app.network.resolve_target", lambda *a, **kw: ["127.0.0.1"])
    yield server.server_address[1], str(cafile), seen
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_real_tls_with_pinned_address_preserves_sni_and_certificate_name(tls_endpoint):
    port, ca, seen = tls_endpoint
    provider = Provider(
        {
            "provider": "openai_compatible_chat",
            "model": "fixture",
            "endpoint": f"https://llm.fixture.test:{port}/v1",
        },
        f"llm.fixture.test:{port}",
        ca_file=ca,
    )
    assert provider.complete("test", {})[0] == {"ok": True}
    assert (
        seen["sni"] == "llm.fixture.test" and seen["host"] == f"llm.fixture.test:{port}"
    )


def test_real_tls_rejects_wrong_certificate_hostname(tls_endpoint):
    port, ca, _ = tls_endpoint
    provider = Provider(
        {
            "provider": "openai_compatible_chat",
            "model": "fixture",
            "endpoint": f"https://wrong.fixture.test:{port}/v1",
        },
        f"wrong.fixture.test:{port}",
        ca_file=ca,
    )
    with pytest.raises(httpx.ConnectError):
        provider.complete("test", {})


def test_real_tls_rejects_untrusted_ca(tls_endpoint):
    port, _, _ = tls_endpoint
    provider = Provider(
        {
            "provider": "openai_compatible_chat",
            "model": "fixture",
            "endpoint": f"https://llm.fixture.test:{port}/v1",
        },
        f"llm.fixture.test:{port}",
    )
    with pytest.raises(httpx.ConnectError):
        provider.complete("test", {})
