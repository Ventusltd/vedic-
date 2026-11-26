"""Offline UI smoke against the exact checked-out VEDIC candidate."""
import json
import math
from urllib.parse import parse_qs, urlparse, quote
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

from prose_smoke import exercise_published, exercise_local

ROOT = Path(__file__).resolve().parents[1]

def main(root=ROOT, *, run_demos=True, offline=False, base_path=''):
    data_root = root / base_path
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/" + (base_path.rstrip("/") + "/" if base_path else "")
    entries = json.loads((data_root / 'data/dictionary.json').read_text(encoding='utf-8'))['entries']
    translations = {r["id"]: r for r in json.loads((data_root / "data/translation-geodesy.json").read_text(encoding="utf-8"))["records"]}
    identities = {e["gg_id"]: e for e in entries}
    def source_records(entry, seen=None):
        if seen is None:
            seen = set()
        if entry["gg_id"] in seen:
            return []
        seen.add(entry["gg_id"])
        t = translations.get(entry.get("translation_ref"), {})
        source = t.get("source") or entry.get("source")
        if source:
            return [source]
        return [s for identity in entry.get("components", []) for s in source_records(identities[identity], seen)]
    def expected_links(entry):
        sources = source_records(entry)
        return [
            ["https://github.com/"+s["repo"]+"/blob/"+s["commit"]+"/"+quote(s["path"], safe="/")+"#L"+str(s["first"])+"-L"+str(s["last"]) for s in sources],
            ["https://raw.githubusercontent.com/"+s["repo"]+"/"+s["commit"]+"/"+quote(s["path"], safe="/") for s in sources],
            ["https://ventusltd.github.io/stars/code.html" for s in sources],
            ["https://ventusltd.github.io/kuiper-belt/see-through/202611020012/#repo="+quote(s["repo"].split("/")[1], safe="") for s in sources]
        ]
    catalogue_path = data_root / "data/prose-catalogue.json"
    catalogue = json.loads(catalogue_path.read_bytes()) if catalogue_path.is_file() else None
    expected_count = min(100, len(entries))
    expected_pages = max(1, math.ceil(len(entries) / 100))
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
                        if offline:
                            page.route("**/*", lambda route: route.continue_()
                                       if route.request.url.startswith(url) else route.abort())
                        requests = []
                        page.on("request", lambda request: requests.append(request.url))
                        page.goto(url)
                        page.locator("#anatomy > summary").click()
                        page.get_by_text("9 recorded cartridges", exact=False).wait_for()
                        page.get_by_role("button", name="Find nearby grid infrastructure").click()
                        page.get_by_text("03 / VEDIC functional language", exact=True).wait_for()
                        page.get_by_text("04 / Source dependency diagram", exact=True).wait_for()
                        assert page.locator("#detail").get_by_text("Measure distance between two geographic points", exact=True).count() == 1
                        assert page.get_by_text("not loaded by the live Atlas", exact=False).count() == 1
                        assert page.get_by_role("link", name="Static dependency graph JSON").count() == 1
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
                        assert page.locator("#dictRows tr").count() == expected_count
                        assert page.locator("#dictPage").inner_text() == f"Page 1 / {expected_pages}"
                        assert page.locator("#dictRows tr").first.locator("td").first.inner_text() == min(entries, key=lambda e: (e.get("priority", 9), e["number"]))["word"]
                        page.locator("#dictSort").select_option("number")
                        assert page.locator("#dictRows tr").first.locator("td").first.inner_text() == "MEASURE"
                        page.locator("#dictSearch").fill("ORIENT")
                        assert page.locator("#dictRows tr").count() == 1
                        assert page.locator("#dictRows .code-cell a.code-source").count() == 2
                        assert "2026-11-26T01:35:15Z" in page.locator("#dictRows").inner_text()
                        page.get_by_role("button",name="CLEAR FILTERS").click()
                        assert page.locator("#dictRows tr").count() == expected_count
                        page.locator("#dictSort").select_option("priority")
                        assert page.locator("#dictRows tr").first.locator("td").first.inner_text() == "LINK"
                        assert page.locator("#dictRows tr td:nth-child(2) a").count() == expected_count
                        assert page.locator("#dictRows a[href^='./demo.html']").count() == 0
                        assert page.locator("#dictRows tr").first.get_by_text("How to see it:", exact=False).count() == 1
                        expected = {e["gg_id"]: e["application"]["url"] for e in entries}
                        for i in range(expected_pages):
                            rows = page.locator("#dictRows tr").evaluate_all("""(rs) => rs.map(r => [r.cells[6].textContent, r.cells[1].querySelector('a').getAttribute('href'), ['a.code-source','a[href^="https://raw.githubusercontent.com/"]','a[href^="https://ventusltd.github.io/stars/code.html"]','a[href^="https://ventusltd.github.io/kuiper-belt/"]'].map(sel => Array.from(r.cells[2].querySelectorAll(sel), a=>a.getAttribute('href')))])""")
                            assert len(rows) == min(100, len(entries) - 100*i)
                            for identity, href, links in rows:
                                assert expected.pop(identity) == href
                                assert links == expected_links(identities[identity]), (identity, links)
                            if i+1 < expected_pages:
                                page.locator("#dictNext").click()
                        assert not expected
                        page.locator("#dictSearch").fill("AREA")
                        assert page.locator("#dictRows tr").count() >= 2
                        page.get_by_role("button",name="CLEAR FILTERS").click()
                        links = [url + "demo.html?id=GG2050-VEDIC-" + str(i).zfill(6) for i in range(1,7)] if run_demos else []
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
                        if catalogue:
                            exercise_published(page, catalogue)
                            exercise_local(page, url)
                        if not catalogue:
                            assert not page.locator("#prose-library, #proseSearch, #proseImport").count()
                            assert "CONTINUOUS ENGLISH LIBRARY" not in page.locator("body").inner_text()
                            assert all("prose-catalogue.json" not in url for url in requests)
                            last = entries[-1]
                            page.locator("#dictSearch").fill(last["gg_id"])
                            assert page.locator("#dictRows tr").count() == 1
                            assert page.locator("#dictRows tr td").first.text_content() == last["word"]
                            assert not page.locator("#dictRows img").count()
                            assert all("fixture-should-never-request" not in url for url in requests)
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
