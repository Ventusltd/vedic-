"""Check the real released prose and browser-only catalogue handling."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

CATALOGUE_URL = "**/data/prose-catalogue.json"


def fixture_file(records):
    data = {"schema": "vedic.prose.catalogue.v1", "records": records}
    return {"name": "test-only.json", "mimeType": "application/json",
            "buffer": json.dumps(data, ensure_ascii=False).encode("utf-8")}


def exercise_published(page, catalogue):
    expected = catalogue["records"]
    expect(page.locator("#proseStatus")).to_contain_text("Published catalogue")
    rows = page.locator("#proseRows tr")
    assert rows.count() == min(100, len(expected))
    for position, record in enumerate(expected[:100]):
        row = rows.nth(position)
        assert row.locator("strong").text_content() == record["id"]
        assert row.locator(".prose-text").first.text_content() == record["prose"]
        row.locator("summary").click()
        assert row.locator("details p").all_text_contents() == [record["provenance"], record["evidence"]]
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    final = expected[-1]
    page.locator("#proseSearch").fill(final["id"])
    assert rows.count() == 1
    assert rows.first.locator(".prose-text").first.text_content() == final["prose"]
    page.locator("#proseSearch").fill("")
    page.locator("#proseApp").select_option(final["software"])
    assert rows.count() == min(100, sum(r["software"] == final["software"] for r in expected))
    page.locator("#proseFull").click()
    expect(page.locator("#proseFull")).to_have_attribute("aria-pressed", "true")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    page.keyboard.press("Escape")
    expect(page.locator("#proseFull")).to_have_attribute("aria-pressed", "false")


def exercise_local(page, url):
    long_text = "An exact long paragraph \u2014 long enough to wrap. " * 200 + "\n\nA second paragraph and \u00a9."
    attack = '<img src="/should-never-send-local-import" onerror="window.importExecuted=true">'
    records = [{"id": f"LOCAL-{i:03}", "software": "Synthetic fixture",
                "prose": long_text if i == 0 else attack if i == 100 else f"Test passage {i}"}
               for i in range(101)]
    page.wait_for_load_state("networkidle")
    sent = []
    page.on("request", lambda request: sent.append(request.url))
    page.locator("#proseImport").set_input_files(fixture_file(records))
    expect(page.locator("#proseStatus")).to_contain_text("Local file")
    rows = page.locator("#proseRows tr")
    assert rows.count() == 100
    assert rows.first.locator(".prose-text").first.text_content() == long_text
    page.locator("#proseNext").click()
    assert rows.count() == 1
    assert rows.first.locator(".prose-text").first.text_content() == attack
    assert page.locator("#proseRows img").count() == 0
    assert not page.evaluate("Boolean(window.importExecuted)")
    page.locator("#proseSearch").fill("A second paragraph")
    assert rows.count() == 1
    assert rows.first.locator("strong").text_content() == "LOCAL-000"
    page.locator("#proseImport").set_input_files(fixture_file([records[0], records[0]]))
    expect(page.locator("#proseStatus")).to_contain_text("Import rejected")
    assert not sent, sent

    for code, body in ((404, ""), (200, '{"schema":"invalid","records":[]}')):
        def unavailable(route):
            route.fulfill(status=code, body=body, content_type="application/json")

        page.route(CATALOGUE_URL, unavailable)
        page.goto(url)
        expect(page.locator("#proseStatus")).to_contain_text("No published catalogue available")
        assert rows.count() == 0
        page.locator("#proseImport").set_input_files(fixture_file(records[:1]))
        expect(page.locator("#proseStatus")).to_contain_text("Local file")
        assert rows.first.locator(".prose-text").first.text_content() == long_text
        page.unroute(CATALOGUE_URL, unavailable)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("catalogue", type=Path)
    args = parser.parse_args()
    catalogue = json.loads(args.catalogue.read_bytes())
    with sync_playwright() as playwright:
        for engine in (playwright.chromium, playwright.webkit):
            browser = engine.launch(headless=True)
            try:
                for width, height in ((1280, 800), (390, 844), (844, 390)):
                    page = browser.new_page(viewport={"width": width, "height": height})
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(args.url)
                    exercise_published(page, catalogue)
                    exercise_local(page, args.url)
                    assert not errors, errors
                    page.close()
                    print(f"Prose PASS {engine.name} {width}x{height}", flush=True)
            finally:
                browser.close()


if __name__ == "__main__":
    main()
