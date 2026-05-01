from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path


class WebBuilderPlaywrightTest(unittest.TestCase):
    def test_right_panel_clicks_update_state_and_complete_agent(self) -> None:
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import expect, sync_playwright
        except Exception as exc:  # pragma: no cover - optional local browser test
            raise unittest.SkipTest(f"playwright is not installed: {exc}") from exc

        port = _free_port()
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "agent_foundry.cli",
                    "serve-web",
                    "--llm-provider",
                    "mock",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--output",
                    tmp,
                ],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                base = f"http://127.0.0.1:{port}"
                _wait_for_health(base)
                with sync_playwright() as p:
                    try:
                        browser = p.chromium.launch(headless=True)
                    except PlaywrightError as exc:
                        raise unittest.SkipTest(f"playwright chromium is not installed: {exc}") from exc
                    page = browser.new_page()
                    page.goto(base + "/", wait_until="networkidle")
                    page.get_by_role("button", name="开始设计").click()
                    expect(page.locator("#sessionStatus")).to_contain_text("asking")

                    self.assertEqual(page.locator(".board input:checked").count(), 0)
                    page.get_by_text("定时扫描", exact=True).click()
                    expect(page.get_by_text("当前选择：scheduled")).to_be_visible()
                    self.assertEqual(page.locator(".board input:checked").evaluate_all("(nodes) => nodes.map((node) => node.value)"), ["scheduled"])

                    page.get_by_text("安全风险", exact=True).click()
                    expect(page.get_by_role("heading", name="自治程度应该设为哪一档？")).to_be_visible()

                    for _ in range(8):
                        if "completed" in page.locator("#sessionStatus").inner_text():
                            break
                        page.get_by_role("button", name="采用推荐").first.click()
                        page.wait_for_timeout(250)

                    expect(page.locator("#sessionStatus")).to_contain_text("completed")
                    expect(page.get_by_role("heading", name="已生成 Agent")).to_be_visible()
                    result_text = page.locator("#result").inner_text()
                    self.assertIn("svn-reviewer", result_text)
                    self.assertIn("Dry run", result_text)
                    browser.close()
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    try:
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def _wait_for_health(base: str) -> None:
    deadline = time.time() + 8
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            health = json.loads(_http_get(base + "/health"))
            if health.get("status") in {"ok", "degraded"}:
                return
        except Exception as exc:  # pragma: no cover - failure reported below
            last_error = exc
            time.sleep(0.1)
    raise AssertionError(f"server did not become healthy: {last_error}")


def _http_get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")
