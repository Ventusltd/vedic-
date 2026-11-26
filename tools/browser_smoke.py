"""Offline UI smoke against the exact checked-out VEDIC candidate."""
import json
import math
from urllib.parse import parse_qs, urlparse
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
                        assert page.locator("#detail").get_by_text("Measure distance between two geographic points", exact=True).count() == 1
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
                        page.locator("#dictRows tr").first.wait_for()
                        assert page.locator("#dictRows tr").count() == 6
                        assert page.locator("#dictRows tr").first.locator("td").first.inner_text() == "BEARING"
                        page.locator("#dictSort").select_option("number")
                        assert page.locator("#dictRows tr").first.locator("td").first.inner_text() == "MEASURE"
                        page.locator("#dictSearch").fill("ORIENT")
                        assert page.locator("#dictRows tr").count() == 1
                        assert "2026-11-26T01:35:15Z" in page.locator("#dictRows").inner_text()
                        page.locator("#dictSearch").fill("")
                        links = page.locator('#dictRows a[href^="./demo.html?id="]').evaluate_all("(els) => els.map(e => e.href)")
                        assert len(links) == 6 and len(set(links)) == 6
                        for demo_url in links:
                            demo = browser.new_page(viewport={"width":width,"height":height})
                            demo.goto(demo_url)
                            demo.get_by_role("button",name="RUN DEMONSTRATION").wait_for()
                            demo.get_by_role("button",name="RUN DEMONSTRATION").click(timeout=10000)
                            result = demo.locator("#result").inner_text()
                            assert result not in ("Ready","Loading…") and not result.startswith(("Cannot run","Demonstration unavailable")), result
                            actual = json.loads(result)
                            identity = parse_qs(urlparse(demo_url).query)["id"][0]
                            # Independent known-answer checks for the seeded examples.
                            expected = {
                                "GG2050-VEDIC-000001": 111.31949079327357,
                                "GG2050-VEDIC-000002": [1, 0.5],
                                "GG2050-VEDIC-000003": [132, 33, 0.75],
                                "GG2050-VEDIC-000004": [0.8983152841195214, 0],
                                "GG2050-VEDIC-000005": 90,
                                "GG2050-VEDIC-000006": {"distance_km":111.31949079327357,"initial_bearing_deg":90}
                            }[identity]
                            def close(a, b):
                                if isinstance(b, dict):
                                    return isinstance(a, dict) and a.keys() == b.keys() and all(close(a[k], b[k]) for k in b)
                                if isinstance(b, list):
                                    return isinstance(a, list) and len(a) == len(b) and all(close(x,y) for x,y in zip(a,b))
                                return isinstance(a,(int,float)) and math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-9)
                            assert close(actual, expected), (identity,actual,expected)
                            demo.locator("#args").fill("not JSON")
                            demo.get_by_role("button",name="RUN DEMONSTRATION").click()
                            assert demo.locator("#result").inner_text().startswith("Cannot run:")
                            demo.close()
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
