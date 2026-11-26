"""Offline UI smoke against the exact checked-out VEDIC candidate."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/"
    passed = 0
    try:
        with sync_playwright() as p:
            for engine in (p.chromium, p.webkit):
                browser = engine.launch(headless=True)
                try:
                    for width, height in ((1280, 800), (390, 844), (844, 390)):
                        page = browser.new_page(viewport={"width": width, "height": height})
                        errors = []
                        page.on("pageerror", lambda err: errors.append(str(err)))
                        page.goto(url)
                        page.get_by_text("9 recorded cartridges", exact=False).wait_for()
                        page.get_by_role("button", name="Find nearby grid infrastructure").click()
                        page.get_by_text("03 / VEDIC functional language", exact=True).wait_for()
                        page.get_by_text("04 / Source dependency diagram", exact=True).wait_for()
                        assert page.get_by_text("Measure distance between two geographic points", exact=True).count() == 1
                        assert page.get_by_text("not loaded by the live Atlas", exact=False).count() == 1
                        assert page.get_by_role("link", name="Spider-compatible graph JSON").count() == 1
                        page.locator("#search").fill("vicinity")
                        assert page.get_by_role("button", name="Explore Vicinity").count() == 1
                        assert page.get_by_role("button", name="Find nearby grid infrastructure").count() == 0
                        page.get_by_role("button", name="Explore Vicinity").click()
                        assert page.get_by_text("03 / VEDIC functional language", exact=True).count() == 0
                        page.get_by_role("button", name="Pipeline News", exact=True).click()
                        assert page.get_by_text("Not mapped yet.", exact=False).count() == 1
                        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "horizontal overflow"
                        page.get_by_role("button", name="GridAtlas", exact=True).click()
                        assert page.get_by_role("button", name="Find a place", exact=True).count() == 1
                        assert not errors, errors
                        page.close()
                        passed += 1
                        print(f"PASS {engine.name} {width}x{height}", flush=True)
                finally:
                    browser.close()
    finally:
        server.shutdown()
        server.server_close()
    assert passed == 6
    print("6/6 browser/viewport cases passed; no live handset claim")

if __name__ == "__main__":
    main()
