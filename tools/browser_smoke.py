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
from dictionary_shards import write_bundle as write_command_shards
from stage_pages import FIRST_PROSE_ROUTE, TELEPRINTER_PROSE_ROUTE

ROOT = Path(__file__).resolve().parents[1]

def audit_all_code_rows(page, entries, expected_links):
    """Exercise every lazy-loaded source control, not just sample rows."""
    for entry in entries:
        identity = entry["gg_id"]
        page.locator("#dictSearch").fill(identity)
        row = page.locator("#dictRows tr")
        assert row.count() == 1, identity
        assert row.locator("td").first.inner_text() == entry["word"], identity
        button = row.locator(".code-cell button")
        if button.count():
            button.click()
        try:
            row.locator("a.code-source").first.wait_for(timeout=8000)
        except Exception as exc:
            raise AssertionError(f"{identity} {entry['word']}: {row.inner_text()}") from exc
        selectors = ['a.code-source', 'a[href^="https://raw.githubusercontent.com/"]',
                     'a[href^="https://ventusltd.github.io/stars/code.html"]',
                     'a[href^="https://ventusltd.github.io/kuiper-belt/"]']
        actual = [row.locator(".code-cell").locator(sel).evaluate_all(
            "(links) => links.map(link => link.href)") for sel in selectors]
        assert actual == expected_links(entry), (identity, actual, expected_links(entry))
        assert not row.get_by_text("Command details unavailable", exact=False).count(), identity
    print(f"PASS all {len(entries)} command code controls and source targets", flush=True)


def audit_live():
    """Read-only audit of the deployed website, independent of the checkout."""
    url = "https://ventusltd.github.io/vedic-/"
    with sync_playwright() as p:
        for engine in (p.chromium, p.webkit):
            browser = engine.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True,
                                        has_touch=True, device_scale_factor=3)
                errors, failed = [], []
                page.on("pageerror", lambda err: errors.append(str(err)))
                page.on("response", lambda response: failed.append((response.status, response.url))
                        if response.url.startswith(url) and response.status >= 400 else None)
                page.on("requestfailed", lambda req: failed.append((req.failure, req.url))
                        if req.url.startswith(url) else None)
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.locator("#dictRows tr").first.wait_for(timeout=30000)
                def live_json(path):
                    response = page.request.get(url + path, headers={"Cache-Control": "no-cache"}, timeout=30000)
                    assert response.ok, (path, response.status)
                    return response.json()
                release = live_json("release.json")
                entries = live_json("data/dictionary.json")["entries"]
                translations = {r["id"]: r for r in live_json("data/translation-geodesy.json")["records"]}
                identities = {e["gg_id"]: e for e in entries}
                def sources(entry, seen=None):
                    if seen is None:
                        seen = set()
                    if entry["gg_id"] in seen:
                        return []
                    seen.add(entry["gg_id"])
                    src = translations.get(entry.get("translation_ref"), {}).get("source") or entry.get("source")
                    if src:
                        return [src]
                    return [s for identity in entry.get("components", []) for s in sources(identities[identity], seen)]
                def expected(entry):
                    ss = sources(entry)
                    return [
                        ["https://github.com/"+s["repo"]+"/blob/"+s["commit"]+"/"+quote(s["path"], safe="/")+"#L"+str(s["first"])+"-L"+str(s["last"]) for s in ss],
                        ["https://raw.githubusercontent.com/"+s["repo"]+"/"+s["commit"]+"/"+quote(s["path"], safe="/") for s in ss],
                        ["https://ventusltd.github.io/stars/code.html" for s in ss],
                        ["https://ventusltd.github.io/kuiper-belt/see-through/202611020012/#repo="+quote(s["repo"].split("/")[1], safe="") for s in ss],
                    ]
                assert release["row_count"] == len(entries), release
                print(f"LIVE {engine.name}: {release['source_commit']} / {len(entries)} commands", flush=True)
                audit_all_code_rows(page, entries, expected)
                assert not errors, errors
                assert not failed, failed
                page.reload(wait_until="domcontentloaded", timeout=45000)
                page.locator("#dictRows tr").first.wait_for(timeout=30000)
                audit_all_code_rows(page, entries[:3], expected)
                assert not errors, errors
                assert not failed, failed
                page.close()
            finally:
                browser.close()


def main(root=ROOT, *, run_demos=True, offline=False, base_path=''):
    data_root = root / base_path
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/" + (base_path.rstrip("/") + "/" if base_path else "")
    paged = 'data/command-index.json' in (data_root/'index.html').read_text(encoding='utf-8')
    if paged and not (data_root/'data/command-index.json').exists():
        write_command_shards(data_root)
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
    catalogue = (json.loads(catalogue_path.read_bytes())
                 if base_path in (FIRST_PROSE_ROUTE, TELEPRINTER_PROSE_ROUTE) else None)
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
                        def wait_dictionary():
                            if paged:
                                page.locator("#dictRows[aria-busy=false]").wait_for(state="attached")
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
                        wait_dictionary()
                        if paged:
                            assert any("/data/command-index.json" in x for x in requests)
                            assert not any("/data/dictionary.json" in x or "/data/prose-catalogue.json" in x for x in requests)
                            assert not any("/data/command-pages/" in x for x in requests)
                        assert page.locator("#dictRows tr").count() == expected_count
                        assert page.locator("#dictPage").inner_text() == f"Page 1 / {expected_pages}"
                        ordering = page.locator("#dictSort").input_value()
                        if ordering != "word":
                            assert page.locator("#dictRows tr").first.locator("td").first.inner_text() == min(entries, key=lambda e: (e.get("priority", 9), e["number"]))["word"]
                        else:
                            first_label = page.evaluate("words => words.sort((a, b) => a.localeCompare(b))[0]", [entry["word"] for entry in entries])
                            assert page.locator("#dictRows tr td").first.inner_text() == first_label
                        page.locator("#dictSort").select_option("number")
                        wait_dictionary()
                        assert page.locator("#dictRows tr").first.locator("td").first.inner_text() == "MEASURE"
                        page.locator("#dictSearch").fill("ORIENT")
                        wait_dictionary()
                        assert page.locator("#dictRows tr").count() == 1
                        if paged:
                            code_button = page.locator("#dictRows .code-cell button")
                            code_button.focus()
                            code_button.press("Enter")
                            code_link = page.locator("#dictRows .code-cell a.code-source").first
                            code_link.wait_for()
                            assert code_link.evaluate("(element) => element === document.activeElement")
                        assert page.locator("#dictRows .code-cell a.code-source").count() == 2
                        assert "2026-11-26T01:35:15Z" in page.locator("#dictRows").inner_text()
                        page.get_by_role("button",name="CLEAR FILTERS").click()
                        wait_dictionary()
                        assert page.locator("#dictRows tr").count() == expected_count
                        page.locator("#dictSort").select_option("priority")
                        wait_dictionary()
                        assert page.locator("#dictRows tr").first.locator("td").first.inner_text() == "LINK"
                        assert page.locator("#dictRows tr td:nth-child(2) a").count() == expected_count
                        assert page.locator("#dictRows a[href^='./demo.html']").count() == 0
                        if not paged:
                            assert page.locator("#dictRows tr").first.get_by_text("How to see it:", exact=False).count() == 1
                        expected = {e["gg_id"]: e["application"]["url"] for e in entries}
                        for i in range(expected_pages):
                            rows = page.locator("#dictRows tr").evaluate_all("""(rs) => rs.map(r => [r.cells[6].textContent, r.cells[1].querySelector('a').getAttribute('href'), ['a.code-source','a[href^="https://raw.githubusercontent.com/"]','a[href^="https://ventusltd.github.io/stars/code.html"]','a[href^="https://ventusltd.github.io/kuiper-belt/"]'].map(sel => Array.from(r.cells[2].querySelectorAll(sel), a=>a.getAttribute('href')))])""")
                            assert len(rows) == min(100, len(entries) - 100*i)
                            for identity, href, links in rows:
                                assert expected.pop(identity) == href
                                if paged:
                                    assert all(not group for group in links), (identity, links)
                                else:
                                    assert links == expected_links(identities[identity]), (identity, links)
                            if i+1 < expected_pages:
                                page.locator("#dictNext").click()
                                wait_dictionary()
                        assert not expected
                        page.locator("#dictSearch").fill("AREA")
                        wait_dictionary()
                        assert page.locator("#dictRows tr").count() >= 2
                        page.get_by_role("button",name="CLEAR FILTERS").click()
                        wait_dictionary()
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
                            if paged:
                                page.locator("#patternFilter").select_option("Measure and calculate")
                                wait_dictionary()
                                assert page.locator("#dictRows tr").count()>0
                                assert "MEASURE" in page.locator("#dictRows").inner_text()
                                page.get_by_role("button",name="CLEAR FILTERS").click()
                                wait_dictionary()
                            assert not page.locator("#prose-library, #proseSearch, #proseImport").count()
                            assert "CONTINUOUS ENGLISH LIBRARY" not in page.locator("body").inner_text()
                            assert all("prose-catalogue.json" not in url for url in requests)
                            last = entries[-1]
                            page.locator("#dictSearch").fill(last["gg_id"])
                            wait_dictionary()
                            assert page.locator("#dictRows tr").count() == 1
                            assert page.locator("#dictRows tr td").first.text_content() == last["word"]
                            if paged:
                                before = [request for request in requests if "/data/command-pages/" in request]
                                row = page.locator("#dictRows tr").first
                                assert not row.locator("a.code-source").count()
                                row.locator(".code-cell button").click()
                                row.locator(".code-cell a.code-source").first.wait_for()
                                assert row.get_by_text("How to see it:", exact=False).count() == 1
                                assert row.locator("a.code-source").evaluate_all("(links) => links.map(link => link.href)") == expected_links(last)[0]
                                after = [request for request in requests if "/data/command-pages/" in request]
                                assert len(after) >= len(before)
                                if expected_pages > 1:
                                    index = json.loads((data_root/"data/command-index.json").read_bytes())
                                    second = next(entry for entry in index["entries"] if entry["page"].endswith("000002.json"))
                                    page.locator("#dictSearch").fill(second["gg_id"])
                                    wait_dictionary()
                                    assert page.locator("#dictRows tr").count() == 1
                                    page.locator("#dictRows .code-cell button").click()
                                    page.locator("#dictRows .code-cell a.code-source").first.wait_for()
                                    assert any("/"+second["page"] in request for request in requests)
                            assert not page.locator("#dictRows img").count()
                            assert all("fixture-should-never-request" not in url for url in requests)
                        if paged and not catalogue:
                            page.locator("#dictClear").click()
                            audit_all_code_rows(page, entries, expected_links)
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
    audit_live()
