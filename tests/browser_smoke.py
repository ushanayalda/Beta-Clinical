#!/usr/bin/env python3
"""Browser-level smoke test for the static learner renderer.

The test injects the synthetic fixture into a temporary HTML document. This avoids
network access and never places the fixture in the production website index.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "valid-learner-export.json"
EVIDENCE = ROOT / "evidence"


def build_index(data: dict) -> dict:
    item = {
        "case_id": data["case_id"],
        "title": data["title"],
        "file": "data/fixture-case.json",
        "phase_id": data["navigation"]["phase_id"],
        "pattern_label": data["navigation"]["pattern_label"],
    }
    return {
        "schema_version": "2.0.0",
        "generated_at": "2026-07-12",
        "phases": [{
            "phase_id": data["navigation"]["phase_id"],
            "label": data["navigation"]["phase_label"],
            "patterns": [{
                "label": data["navigation"]["pattern_label"],
                "cases": [{"case_id": data["case_id"], "title": data["title"], "file": item["file"]}],
            }],
        }],
        "cases": [item],
    }


def instrumented_html(fixture: dict, query: str) -> str:
    index = build_index(fixture)
    css = (ROOT / "website" / "styles.css").read_text(encoding="utf-8")
    app = (ROOT / "website" / "app.js").read_text(encoding="utf-8")
    app = app.replace(
        "return new URLSearchParams(window.location.search);",
        "return new URLSearchParams(window.__TEST_QUERY || window.location.search);",
    )
    body = """
      <button id="menuButton" class="menu-button" aria-expanded="false" aria-controls="sidebar">Cases</button>
      <aside id="sidebar" class="sidebar" aria-label="Case navigation">
        <a class="brand" href="./">Clinical Pathway</a>
        <nav id="caseNavigation"></nav>
      </aside>
      <main id="main" class="main" tabindex="-1">
        <section id="screen" class="screen" aria-live="polite"></section>
      </main>
    """
    prelude = f"""
      window.__TEST_QUERY = {json.dumps(query)};
      window.__TEST_INDEX = {json.dumps(index)};
      window.__TEST_CASE = {json.dumps(fixture)};
      const __store = new Map();
      Object.defineProperty(window, 'localStorage', {{value: {{
        getItem: (key) => __store.has(key) ? __store.get(key) : null,
        setItem: (key, value) => __store.set(key, String(value)),
        removeItem: (key) => __store.delete(key),
        clear: () => __store.clear()
      }}}});
      window.fetch = async (path) => ({{
        ok: true,
        json: async () => String(path).includes('index.json') ? window.__TEST_INDEX : window.__TEST_CASE
      }});
    """
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Clinical Pathway Test</title><style>{css}</style></head><body>{body}<script>{prelude}</script><script>{app}</script></body></html>"""


def load_view(page: Page, fixture: dict, view: str) -> None:
    query = "" if view == "home" else f"?case={fixture['case_id']}&view={view}"
    page.set_content(instrumented_html(fixture, query), wait_until="load")
    page.wait_for_function("document.querySelector('#screen').textContent.trim().length > 0")


def attach_error_capture(page: Page, results: dict[str, object]) -> None:
    page.on("console", lambda msg: results["console_errors"].append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda error: results["page_errors"].append(str(error)))


def main() -> int:
    EVIDENCE.mkdir(exist_ok=True)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    results: dict[str, object] = {
        "status": "FAIL",
        "fixture_only": True,
        "checks": {},
        "console_errors": [],
        "page_errors": [],
    }
    with sync_playwright() as p:
        launch_args = {"headless": True, "args": ["--no-sandbox"]}
        requested = os.environ.get("CHROMIUM_PATH")
        if requested and Path(requested).is_file():
            launch_args["executable_path"] = requested
        elif Path("/usr/bin/chromium").is_file():
            launch_args["executable_path"] = "/usr/bin/chromium"
        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})

        home_page = context.new_page()
        attach_error_capture(home_page, results)
        load_view(home_page, fixture, "home")
        results["checks"]["home_surface"] = home_page.get_by_role("heading", name="Choose a case.").is_visible()
        home_page.close()

        stem_page = context.new_page()
        attach_error_capture(stem_page, results)
        load_view(stem_page, fixture, "stem")
        results["checks"]["stem_title"] = stem_page.get_by_role("heading", name=fixture["title"]).is_visible()
        results["checks"]["task_count"] = stem_page.locator(".task").count() == len(fixture["stem_page"]["tasks"])
        results["checks"]["two_clock_maps"] = stem_page.locator(".clock-card").count() == 2
        stem_page.locator(".hint-button").first.click()
        results["checks"]["hint_expands"] = stem_page.locator(".hint-panel.open").count() == 1
        before = stem_page.locator("#progressLabel").inner_text()
        stem_page.locator("#progressRing").click()
        after = stem_page.locator("#progressLabel").inner_text()
        results["checks"]["progress_changes_without_loss"] = before != after and after == "Finding the path"
        stem_page.screenshot(path=EVIDENCE / "browser-smoke-stem.png", full_page=True)
        stem_page.close()

        script_page = context.new_page()
        attach_error_capture(script_page, results)
        load_view(script_page, fixture, "script")
        results["checks"]["script_turn_count"] = script_page.locator(".turn").count() == len(fixture["script_page"]["turns"])
        results["checks"]["decision_hint_displayed"] = script_page.locator("#TURN-006 .hint-button").count() >= 1
        script_page.screenshot(path=EVIDENCE / "browser-smoke-script.png", full_page=True)
        script_page.close()
        context.close()

        mobile = browser.new_context(viewport={"width": 390, "height": 844})
        mobile_page = mobile.new_page()
        attach_error_capture(mobile_page, results)
        load_view(mobile_page, fixture, "stem")
        mobile_page.locator("#menuButton").click()
        mobile_page.wait_for_timeout(250)
        sidebar_rect = mobile_page.locator("#sidebar").bounding_box()
        results["checks"]["mobile_navigation_opens"] = (
            "open" in (mobile_page.locator("#sidebar").get_attribute("class") or "")
            and sidebar_rect is not None and abs(sidebar_rect["x"]) < 1
        )
        results["checks"]["mobile_menu_accessible_state"] = mobile_page.locator("#menuButton").get_attribute("aria-expanded") == "true"
        mobile_page.screenshot(path=EVIDENCE / "browser-smoke-mobile.png", full_page=True)
        mobile.close()
        browser.close()

    checks = results["checks"]
    checks["console_errors_absent"] = not results["console_errors"]
    checks["page_errors_absent"] = not results["page_errors"]
    results["status"] = "PASS" if all(checks.values()) else "FAIL"
    (EVIDENCE / "browser-smoke-results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0 if results["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
