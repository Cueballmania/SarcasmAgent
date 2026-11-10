"""Audience markup and deterministic QR contract; real device checks are separate."""

import socket
import threading
import time
from contextlib import contextmanager
from unittest.mock import patch

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from app.main import create_app
from app.qr import qr_bytes
from tests.test_audit_api import MemoryAudit, StubDetector, client_for
from tests.test_config import settings


@contextmanager
def browser_server():
    """Own a loopback-only ephemeral server and stop its thread after the checks."""
    application = create_app(
        settings=settings(),
        database=MemoryAudit(),
        detector=StubDetector(delay=0.2),
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                application,
                host="127.0.0.1",
                port=port,
                access_log=False,
                log_level="error",
            )
        )
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert server.started, "Owned local UI server did not become ready"
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            assert not thread.is_alive(), "Owned local UI server failed to stop"


async def test_phone_form_and_static_assets_are_audited() -> None:
    async with client_for() as (client, store, detector, app):
        response = await client.get("/")
        assert response.status_code == 200
        assert 'for="message"' in response.text and 'role="status"' in response.text
        assert 'role="alert"' in response.text and 'method="post"' in response.text
        assert "metadata" in response.text and "Unknown" in response.text
        assert "stored in Langfuse" in response.text and "displayed to everyone" in response.text
        assert "not your message text" not in response.text
        assert (await client.get("/static/app.js")).status_code == 200
        assert (await client.get("/static/app.css")).status_code == 200
        assert len(store.rows) == 3 and detector.calls == 0
        assert "default-src 'self'" in response.headers["content-security-policy"]


async def test_missing_qr_configuration_never_uses_host() -> None:
    async with client_for() as (client, store, detector, app):
        response = await client.get("/qr.png", headers={"Host": "evil.test"})
        assert response.status_code == 503 and "evil.test" not in response.text


async def test_presenter_and_both_qr_formats() -> None:
    async with client_for(public_base_url="https://example.test") as (
        client,
        store,
        detector,
        app,
    ):
        assert "https://example.test/" in (await client.get("/presenter")).text
        svg = await client.get("/qr.svg")
        png = await client.get("/qr.png")
        assert svg.status_code == png.status_code == 200
        assert b"<svg" in svg.content and png.content.startswith(b"\x89PNG")
        with patch("app.qr.segno.make_qr") as make:
            qr_bytes("https://example.test", kind="svg")
            make.assert_called_once_with("https://example.test/", error="m")
            options = make.return_value.save.call_args.kwargs
            assert options["border"] == 4 and options["light"] == "white"


@pytest.mark.parametrize("width", [320, 1024])
def test_real_browser_keyboard_loading_result_error_and_reflow(width: int) -> None:
    """Exercise actual JS/keyboard/live state, not just markup presence."""
    with browser_server() as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": width, "height": 800})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url)
            input_field = page.get_by_label("Your message")
            input_field.fill("A harmless test message")
            input_field.focus()
            input_field.press("Tab")
            button = page.get_by_role("button", name="Detect sarcasm")
            expect(button).to_be_focused()
            button.press("Enter")
            expect(button).to_be_disabled()
            expect(page.get_by_role("status")).to_have_text("Detecting sarcasm...")
            expect(page.get_by_role("status")).to_have_text("Unknown")
            expect(button).to_be_enabled()
            page.route(
                "**/api/classify",
                lambda route: route.fulfill(
                    status=503,
                    json={"error": {"message": "Service unavailable."}},
                ),
            )
            button.click()
            expect(page.get_by_role("alert")).to_have_text("Service unavailable.")
            expect(page.get_by_role("status")).to_have_text("")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors
        finally:
            browser.close()
