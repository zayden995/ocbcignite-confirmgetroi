"""Drive the production frontend and HTTP routes together on an ephemeral loopback port."""
import json
import os
import re
import socket
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from types import SimpleNamespace

import pytest
import uvicorn
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import errors, types
from playwright.sync_api import expect, sync_playwright

import app.llm as llm
from app import config
from app.assessment.intake import FIXTURE
from app.assessment.mapping import fixture_map
from app.llm import accounting
from app.main import app


@pytest.fixture(scope="module")
def site():
    static = StaticFiles(directory=Path(__file__).resolve().parents[2] / "frontend/dist", html=True)

    async def local(scope, receive, send):
        handler = app if scope["type"] == "lifespan" or scope["path"].startswith("/api/") else static
        await handler(scope, receive, send)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(local, log_level="error"))
        thread = Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = monotonic() + 10
            while not server.started and monotonic() < deadline:
                sleep(.02)
            assert server.started
            yield f"http://127.0.0.1:{sock.getsockname()[1]}"
        finally:
            server.should_exit = True
            thread.join(5)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as driver:
        channel = os.getenv("TREE_BROWSER_CHANNEL", "chrome")
        browser = driver.chromium.launch(channel=channel, headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser, site, monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    p = browser.new_page(viewport={"width": 1440, "height": 1000})
    p.set_default_timeout(6000)
    errors_seen = []
    p.on("pageerror", lambda err: errors_seen.append(str(err)))
    p.goto(site)
    yield p
    p.close()
    assert not errors_seen


def click(p, name):
    p.get_by_role("button", name=name, exact=True).click()


def verdict(p, heading):
    expect(p.get_by_role("heading", name=heading, exact=True)).to_be_visible()


def inspector(p):
    p.get_by_role("link", name="Admin", exact=True).click()
    p.get_by_role("tab", name="Verification cost").click()


def test_three_runs_keyboard_evidence_and_original(page):
    p = page
    p.get_by_role("button", name=re.compile("offline fixture Quote the standard rate$")).click()
    click(p, "Run decision check")
    verdict(p, "Ready · 1/1")
    p.get_by_text("Review question and answer", exact=True).click()
    p.get_by_label("Employee question", exact=True).fill(FIXTURE.question)
    click(p, "Run decision check")
    verdict(p, "Hold · 1/2")
    branch = p.get_by_role("button", name=re.compile("Required decision · omitted Single FAST transfer"))
    branch.focus()
    branch.press("Enter")
    drawer = p.get_by_role("dialog", name="Single FAST transfer")
    for text in ("FD-301#p1 · v2", "S$100,000", "S$50,000", "S$150,000", "No quoted text"):
        expect(drawer).to_contain_text(text)
    p.get_by_role("button", name="Close", exact=True).press("Escape")
    click(p, "Use proposed answer for recheck")
    click(p, "Run decision check")
    verdict(p, "Ready · 2/2")
    p.get_by_label("Inspect assessment").select_option(index=1)
    verdict(p, "Hold · 1/2")
    expect(p.locator(".decision-verdict")).to_contain_text("Historical assessment")
    inspector(p)
    expect(p.locator(".cost-inspector")).to_contain_text("Offline fixture · no provider call")
    expect(p.locator(".cost-inspector")).to_contain_text("0 samples")
    p.get_by_role("link", name="Employee", exact=True).click()
    verdict(p, "Hold · 1/2")


def test_stale_response_and_profile_change(page):
    p = page
    p.get_by_role("button", name=re.compile("offline fixture Quote the rate and check")).click()
    p.get_by_text("Review question and answer", exact=True).click()
    # Delay delivery of a genuine already-computed result while later requests use normal fetch.
    p.evaluate("""() => {
      const original = window.fetch;
      window.delayNext = () => {window.gate = new Promise(r => window.release = r)};
      window.fetch = async (...args) => {
        const gate = String(args[0]).includes('/v2/assess') && window.gate;
        if (gate) window.gate = null;
        const response = await original(...args);
        if (gate) await gate;
        return response;
      };
      window.delayNext();
    }""")
    click(p, "Run decision check")
    p.get_by_label("Full answer to check").fill(FIXTURE.answer + " This transfer exceeds the cap.")
    click(p, "Run decision check")
    verdict(p, "Ready · 2/2")
    p.evaluate("window.release()")
    expect(p.get_by_label("Inspect assessment").locator("option")).to_have_count(1)
    p.evaluate("window.delayNext()")
    click(p, "Run decision check")
    p.get_by_label("Region", exact=True).select_option("MY")
    click(p, "Run decision check")
    verdict(p, "Hold · 0/2")
    p.evaluate("window.release()")
    expect(p.get_by_label("Inspect assessment").locator("option")).to_have_count(2)
    verdict(p, "Hold · 0/2")

    def wrong_bundle(route):
        response = route.fetch()
        result = response.json()
        result["bundle_id"] = "superseded-bundle"
        route.fulfill(response=response, json=result)

    p.route("**/api/v2/assess?*", wrong_bundle)
    click(p, "Run decision check")
    expect(p.get_by_role("alert")).to_contain_text("another assessment revision")
    expect(p.get_by_label("Full answer to check")).to_have_value(FIXTURE.answer + " This transfer exceeds the cap.")


def test_original_chat_and_inspector(page):
    p = page
    p.locator(".starter").nth(2).click()
    click(p, "Run TREE")
    expect(p.locator(".verdict-do li")).to_have_count(2)
    click(p, "Run all 4 scenarios")
    expect(p.locator(".tree-score")).to_contain_text("4 of 4")
    p.get_by_role("link", name="Admin", exact=True).click()
    for tab in ("Pipeline trace", "Corpus and whitelist", "Matrix and settings", "Graph", "Raw payload"):
        p.get_by_role("tab", name=tab, exact=True).click()
        expect(p.get_by_role("tabpanel")).not_to_be_empty()


class MeteredModels:
    """A simulated transport. Requests, receipt emission, retries and inspector totals are real."""
    def __init__(self, missing):
        self.checks = 0
        self.missing = missing

    def generate_content(self, *, model, contents, config):
        types.GenerateContentConfig.model_validate(config)
        assert config["http_options"]["retry_options"]["attempts"] == 1
        if config.get("response_schema"):
            self.checks += 1
            if self.checks == 1:
                raise errors.ServerError(503, {"error": {"message": "simulated outage",
                    "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 0}}})
            tokens = 20 if self.checks == 2 else 40
            text = contents.split("\nAnswer: ")[-1]
            answer = json.dumps({"observations": [o.model_dump() for o in fixture_map(text)]})
        else:
            tokens, answer = 30, FIXTURE.answer
        usage = {"prompt_token_count": tokens, "candidates_token_count": 0}
        if self.missing == "usage" and self.checks == 2:
            usage = None
        return SimpleNamespace(text=answer, usage_metadata=usage)


@pytest.mark.parametrize("missing", [None, "usage", "price"])
def test_cost_journey(page, monkeypatch, missing):
    monkeypatch.setenv("GEMINI_API_KEY", "browser-test-only")
    monkeypatch.setenv("TREE_GEMINI_MODEL", "priced-test")
    fake = MeteredModels(missing)
    monkeypatch.setattr(genai, "Client", lambda **kwargs: SimpleNamespace(models=fake))
    monkeypatch.setattr(llm, "_INSTANCE", None)
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    provider = llm.get_llm()
    prices = {"currency":"USD", "pricing_date":"2026-11-20", "tokens_per_unit":1000,
              "models":{"priced-test":[{"from":"2026-01-01","input":1,"output":1,"thinking":1,"cached":1}]}}
    monkeypatch.setattr(accounting, "PRICE_TABLE", prices)
    p = page
    p.reload()
    question = "Can my customer fund the whole deposit in one FAST transfer, and what standard rate applies?"
    p.get_by_label("Message the OCBC assistant").fill(question)
    with p.expect_response(lambda r: r.url.endswith("/api/ask")) as sent:
        click(p, "Send")
    assert sent.value.ok, sent.value.text()
    p.get_by_text("Employee facts · 0 fields").click()
    for key, label, value in [
        ("product","Product","SteadyGrowth"), ("currency","Currency","SGD"), ("booking_region","Booking region","SG"),
        ("segment","Customer segment","retail"), ("channel","Funding channel","FAST"), ("tenor_months","Tenor (months)","12"),
        ("deposit_cents","Deposit amount (SGD)","150000"), ("transfer_cents","Amount in this single transfer (SGD)","150000"),
    ]:
        p.get_by_label(label, exact=True).fill(value)
    click(p, "Run decision check")
    expect(p.get_by_role("alert")).to_contain_text("simulated outage")
    if missing == "price":
        monkeypatch.setattr(provider, "_model", "unpriced-test")
    click(p, "Retry check")
    verdict(p, "Hold · 1/2")
    monkeypatch.setattr(provider, "_model", "priced-test")
    click(p, "Use proposed answer for recheck")
    click(p, "Run decision check")
    verdict(p, "Ready · 2/2")
    inspector(p)
    labels = p.locator(".cost-grid dd")
    expect(labels.nth(0)).to_have_text(re.compile("0.01" if missing else "0.03"))
    expect(labels.nth(1)).to_have_text(re.compile(r"Unknown · known subtotal USD\s*0.05" if missing else r"USD\s*0.07"))
    expect(labels.nth(2)).to_have_text(re.compile(r"USD\s*0.03"))
    expect(p.get_by_role("heading", name="Provider attempts · 4")).to_be_visible()
    original_totals = labels.all_text_contents()
    p.get_by_role("link", name="Employee", exact=True).click()
    p.get_by_label("Inspect assessment").select_option(index=0)
    inspector(p)
    assert original_totals == labels.all_text_contents() and fake.checks == 3
