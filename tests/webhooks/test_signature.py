"""Tests for webhook HMAC signature utilities."""

import time

from app.services.webhook import (
    build_signature_header,
    sign_payload,
    verify_signature_header,
)

SECRET = "test-signing-secret"


def test_signature_is_stable_hex():
    body = b'{"hello":"world"}'
    ts = 1234567890
    assert sign_payload(body, SECRET, ts) == sign_payload(body, SECRET, ts)
    assert len(sign_payload(body, SECRET, ts)) == 64


def test_header_format():
    body = b"payload"
    ts = int(time.time())
    header = build_signature_header(body, SECRET, ts)
    prefix = f"t={ts},v1="
    assert header.startswith(prefix)
    assert header[len(prefix) :] == sign_payload(body, SECRET, ts)


def test_signature_roundtrip_valid():
    body = b'{"hello":"world"}'
    header = build_signature_header(body, SECRET, int(time.time()))
    assert verify_signature_header(body, SECRET, header) is True


def test_tampered_body_rejected():
    body = b'{"hello":"world"}'
    header = build_signature_header(body, SECRET, int(time.time()))
    assert verify_signature_header(b'{"hello":"evil"}', SECRET, header) is False


def test_wrong_secret_rejected():
    body = b"payload"
    header = build_signature_header(body, SECRET, int(time.time()))
    assert verify_signature_header(body, "other-secret", header) is False


def test_stale_timestamp_rejected():
    body = b"payload"
    old_ts = int(time.time()) - 3600
    header = build_signature_header(body, SECRET, old_ts)
    assert verify_signature_header(body, SECRET, header) is False


def test_custom_tolerance_respected():
    body = b"payload"
    old_ts = int(time.time()) - 3600
    header = build_signature_header(body, SECRET, old_ts)
    assert verify_signature_header(body, SECRET, header, tolerance_seconds=7200) is True


def test_malformed_header_rejected():
    body = b"payload"
    ts = int(time.time())
    assert verify_signature_header(body, SECRET, "") is False
    assert verify_signature_header(body, SECRET, "garbage") is False
    assert verify_signature_header(body, SECRET, "v1=abc") is False
    assert verify_signature_header(body, SECRET, "t=notanumber,v1=abc") is False
    assert verify_signature_header(body, SECRET, None) is False
