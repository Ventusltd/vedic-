"""Read-only semantic enrichment of existing VEDIC source pins.

No estate scan, ID allocation, execution, LLM call, telemetry or source copying.
Optional esprima/BeautifulSoup adapters are static observations, not contracts.
"""
import argparse
import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

UNVERIFIED = "UNVERIFIED"
SCHEMA = "vedic.semantic-contracts.v1"
SHA = re.compile(r"[0-9a-f]{40}")
ID = re.compile(r"GG2050-VEDIC-\d{6,}")
TOKENS = re.compile(r"[a-z0-9]+")
STOP = set("a an and as at by for from how in is it of on or the to with i want".split())

def require(ok, message):
    if not ok:
        raise ValueError(message)

def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def source_key(s):
    require(re.fullmatch(r"Ventusltd/[A-Za-z0-9_.-]+", s["repo"]), "invalid repo")
    require(all(SHA.fullmatch(s[k]) for k in ("commit", "blob")), "invalid source pin")
    path = s["path"]
    require(path and not path.startswith("/") and all(x not in ("", ".", "..") for x in path.split("/")) and "\\" not in path and not any(c in path for c in "?#\r\n"), "invalid path")
    require(type(s["first"]) is int and type(s["last"]) is int and 1 <= s["first"] <= s["last"], "invalid line span")
    return (s["repo"], s["commit"], path, s["blob"], s["first"], s["last"])

def physical_lines(raw):
    # Git lines: LF separates records; preserve CRLF and unterminated last line.
    parts = raw.split(b"\n")
    return [p + b"\n" for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])

def ast_walk(node):
    if isinstance(node, dict):
        if "type" in node:
            yield node
        for key, value in node.items():
            if key not in ("loc", "range"):
                yield from ast_walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from ast_walk(value)

def python_observations(text, first, last):
    tree = ast.parse(text)
    matches = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
               and n.lineno == first and n.end_lineno == last]
    if len(matches) != 1:
        return {"parser": "python.ast", "state": "SPAN_NOT_EXACT_AST_NODE"}
    node = matches[0]
    nodes = list(ast.walk(node))
    params = None
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        a = node.args
        params = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs]
        params += [x.arg for x in (a.vararg, a.kwarg) if x is not None]
    return {"parser": "python.ast", "state": "STATIC_SYNTAX_OBSERVATION",
            "symbol": node.name, "parameters": params,
            "names_read": sorted({n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}),
            "names_written": sorted({n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))}),
            "explicit_global_names": sorted({x for n in nodes if isinstance(n, ast.Global) for x in n.names}),
            "return_statements": sum(isinstance(n, ast.Return) for n in nodes),
            "file_imports": sorted({n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} |
                                   {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names})}

def js_observations(text, first, last):
    import esprima
    try:
        tree = esprima.parseModule(text, loc=True).toDict()
    except esprima.Error:
        tree = esprima.parseScript(text, loc=True).toDict()
    all_nodes = list(ast_walk(tree))
    candidates = [n for n in all_nodes if n["type"] in ("FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression", "ClassDeclaration", "ClassExpression")
                  and n.get("loc", {}).get("start", {}).get("line") == first
                  and n.get("loc", {}).get("end", {}).get("line") == last]
    if len(candidates) != 1:
        return {"parser": "esprima", "state": "SPAN_NOT_EXACT_AST_NODE"}
    n = candidates[0]
    nodes = list(ast_walk(n))
    def literals_for(method):
        result = set()
        for x in nodes:
            if x["type"] != "CallExpression":
                continue
            c = x.get("callee", {})
            prop = c.get("property", {})
            args = x.get("arguments", [])
            if c.get("type") == "MemberExpression" and not c.get("computed") and prop.get("name") == method and args:
                a = args[0]
                if a.get("type") == "Literal" and isinstance(a.get("value"), str):
                    result.add(a["value"])
        return sorted(result)
    return {"parser": "esprima", "state": "STATIC_SYNTAX_OBSERVATION",
            "symbol": (n.get("id") or {}).get("name"),
            "parameters": [p.get("name", UNVERIFIED) for p in n.get("params", [])],
            "identifier_occurrences": sorted({x["name"] for x in nodes if x["type"] == "Identifier"}),
            "file_imports": sorted({x["source"]["value"] for x in all_nodes if x["type"] == "ImportDeclaration"}),
            "literal_dom_id_arguments": literals_for("getElementById"),
            "literal_selector_arguments": sorted(set(literals_for("querySelector") + literals_for("querySelectorAll"))),
            "literal_event_arguments": literals_for("addEventListener"),
            "literal_fetch_arguments": sorted({x["arguments"][0]["value"] for x in nodes if x["type"] == "CallExpression"
                and x.get("callee", {}).get("name") == "fetch" and x.get("arguments")
                and x["arguments"][0].get("type") == "Literal" and isinstance(x["arguments"][0].get("value"), str)})}

def observations(path, raw, first, last):
    suffix = Path(path).suffix.lower()
    try:
        text = raw.decode("utf-8")
        if suffix == ".py":
            return python_observations(text, first, last)
        if suffix in (".js", ".mjs", ".cjs"):
            return js_observations(text, first, last)
        if suffix in (".html", ".htm"):
            # DOM observations only when the record is the entire document.
            if first != 1 or last != len(physical_lines(raw)):
                return {"parser": "BeautifulSoup", "state": "HTML_SUBSPAN_REQUIRES_PRODUCER_BOUNDARY"}
            from bs4 import BeautifulSoup
            doc = BeautifulSoup(text, "html.parser")
            return {"parser": "BeautifulSoup", "state": "STATIC_SYNTAX_OBSERVATION",
                    "dom_ids": sorted({n["id"] for n in doc.select("[id]")}),
                    "script_src": sorted({n["src"] for n in doc.select("script[src]")})}
        return {"parser": None, "state": "UNSUPPORTED_LANGUAGE"}
    except ImportError:
        return {"parser": suffix, "state": "PARSER_UNAVAILABLE"}
    except (SyntaxError, UnicodeError, ValueError, RecursionError):
        return {"parser": suffix, "state": "PARSE_UNVERIFIED"}
    except Exception as exc:
        # esprima's parser exception is not a SyntaxError on all versions.
        if type(exc).__module__.startswith("esprima"):
            return {"parser": suffix, "state": "PARSE_UNVERIFIED"}
        raise

def compile_manifest(dictionary, translations, reader, parse=True):
    require(dictionary["schema"] == "vedic.dictionary.v1", "wrong dictionary schema")
    records = dictionary["entries"]
    ids = [e["gg_id"] for e in records]
    require(len(ids) == len(set(ids)) and all(ID.fullmatch(i) for i in ids), "invalid/duplicate dictionary identity")
    tr = {r["id"]: r for r in translations["records"]}
    require(len(tr) == len(translations["records"]), "duplicate translation reference")
    cache, spans, result = {}, {}, []
    for e in records:
        t = tr.get(e.get("translation_ref"), {})
        s = e.get("source") or t.get("source")
        p = None
        if s:
            key = source_key(s)
            file_key = key[:3]
            if file_key not in cache:
                cache[file_key] = reader(*file_key)
            raw = cache[file_key]
            require(isinstance(raw, bytes) and len(raw) <= 1_000_000, "unsupported source bytes")
            require(git_blob(raw) == s["blob"], "source blob mismatch: " + str(file_key))
            lines = physical_lines(raw)
            require(s["last"] <= len(lines), "span exceeds file")
            if key not in spans:
                chunk = b"".join(lines[s["first"]-1:s["last"]])
                spans[key] = {"source": dict(s), "line_count": s["last"]-s["first"]+1,
                              "byte_count": len(chunk), "span_sha256": hashlib.sha256(chunk).hexdigest(),
                              "syntax": observations(s["path"], raw, s["first"], s["last"]) if parse else {"state": "NOT_REQUESTED"}}
            p = spans[key]
        purpose = e.get("purpose") or t.get("purpose")
        limits = e.get("limits") or t.get("limits")
        result.append({"gg_id": e["gg_id"], "word": e["word"], "kind": e["kind"],
                       "estate_group": e.get("estate_group"), "discipline": e.get("discipline"),
                       "vedic_class_candidate": e.get("vedic_class_candidate"),
                       "mechanical": p,
                       "operational": {"purpose": purpose or UNVERIFIED, "limits": limits or UNVERIFIED,
                                       "state": "EXISTING_CURATED_TEXT" if purpose else UNVERIFIED,
                                       "declared_inputs": e.get("inputs"), "declared_output": e.get("output")},
                       "state_signature": {"inputs": UNVERIFIED, "outputs": UNVERIFIED,
                                           "external_dependencies": UNVERIFIED, "side_effects": UNVERIFIED},
                       "output_class": UNVERIFIED, "components": e.get("components", []),
                       "application": e.get("application"), "runtime_verified": False,
                       "producer_ids": {k: e.get(k, t.get(k)) for k in ("family_id", "element_id", "tablet_id", "line_ids")},
                       "kuiper_key": UNVERIFIED})
    graph = {e["gg_id"]: e["components"] for e in result}
    for e in result:
        require(all(x in graph for x in e["components"]), "unknown composition component")
        require(len(e["components"]) == len(set(e["components"])), "duplicate composition component")
        if e["kind"] == "FUNCTION":
            require(e["mechanical"] is not None and not e["components"], "function missing source or has components")
        elif e["kind"] == "COMPOSITION":
            require(len(e["components"]) >= 2 and e["mechanical"] is None, "invalid composition structure")
        else:
            raise ValueError("unknown dictionary kind")
    visiting, done = set(), set()
    def visit(node):
        require(node not in visiting, "composition cycle")
        if node in done:
            return
        visiting.add(node)
        for dep in graph[node]:
            visit(dep)
        visiting.remove(node)
        done.add(node)
    for node in graph:
        visit(node)
    syntax_counts = Counter(p["syntax"]["state"] for p in spans.values())
    return {"schema": SCHEMA, "dictionary_entries": len(result),
            "unique_verified_spans": len(spans), "unique_verified_files": len(cache),
            "syntax_observation_counts": dict(sorted(syntax_counts.items())),
            "fully_verified_state_signatures": 0, "entries": result}

def verify_candidate_receipt(receipt, reader):
    """Verify original bytes and explicit sub-body boundaries; do not allocate IDs."""
    require(receipt["schema"] == "vedic.candidate-receipt.v1", "invalid receipt schema")
    cache, keys, words, result = {}, set(), set(), []
    def load(s):
        k = source_key(s)
        file_key = k[:3]
        if file_key not in cache:
            cache[file_key] = reader(*file_key)
        raw = cache[file_key]
        require(isinstance(raw, bytes) and len(raw) <= 1_000_000, "unsupported source bytes")
        require(git_blob(raw) == s["blob"], "source blob mismatch")
        lines = physical_lines(raw)
        require(s["last"] <= len(lines), "span exceeds file")
        return k, raw, lines
    for e in receipt["entries"]:
        require(e["word"] not in words and bool(e["word"].strip()), "duplicate or empty candidate word")
        words.add(e["word"])
        require(all(e.get(k) is None for k in ("vedic_id","kuiper_key","family_id","element_id","tablet_id","line_ids")), "unverified identity assigned")
        require(e["state"] == "STATIC_SOURCE_REVIEW" and e["application_state"] == "RELATED_APPLICATION_RUNTIME_UNVERIFIED", "unsupported proof state")
        require(e["output_class"] in ("VERIFIED_SOURCE_DATA","ILLUSTRATIVE_INDICATIVE_MODEL","UNVERIFIED"), "invalid output classification")
        require(all(e.get(k) for k in ("purpose","inputs","outputs","mechanical","limits","activation","dependencies")), "incomplete candidate")
        s = e["source"]
        key, raw, lines = load(s)
        require(key not in keys, "duplicate exact source span")
        keys.add(key)
        # Formal JS parser may not support modern syntax. An independent lexical
        # anchor proves only the pinned parent header, not AST validity.
        name = e["parent_symbol"]
        require(bool(re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", name)), "invalid parent symbol")
        headers = [i+1 for i, line in enumerate(lines) if re.match(rb"^\s*function\s+" + name.encode() + rb"\s*\(", line)]
        require(len(headers) == 1, "ambiguous or missing parent declaration")
        parent_first = headers[0]
        if e["kind"] == "FUNCTION":
            require(parent_first == s["first"] and lines[s["last"]-1].strip() == b"}", "whole-function anchor mismatch")
        elif e["kind"] == "SUB_BODY":
            require(parent_first < s["first"] and not any(parent_first < i <= s["last"] for i,line in enumerate(lines,1)
                if re.match(rb"^function\s+[A-Za-z_$][A-Za-z0-9_$]*\s*\(",line)), "sub-body crosses next top-level function")
        else:
            raise ValueError("unknown candidate kind")
        chunk = b"".join(lines[s["first"]-1:s["last"]])
        result.append({"word":e["word"],"source":s,"line_count":s["last"]-s["first"]+1,"byte_count":len(chunk),
                       "span_sha256":hashlib.sha256(chunk).hexdigest(),"parent_first":parent_first,
                       "boundary_state":"SOURCE_ANCHOR_VERIFIED_NOT_AST_PROOF","output_class":e["output_class"]})
    # All UI evidence files share the explicitly pinned source repo/commit.
    require(len({(e["source"]["repo"],e["source"]["commit"]) for e in receipt["entries"]}) == 1, "mixed receipt sources")
    source = receipt["entries"][0]["source"]
    for evidence in receipt["source_activation_evidence"]:
        for first,last in evidence["ranges"]:
            load({"repo":source["repo"],"commit":source["commit"],"path":evidence["path"],"blob":evidence["blob"],"first":first,"last":last})
    return {"schema":"vedic.candidate-verification.v1","candidate_count":len(result),
            "verified_files_including_activation":len(cache),"entries":result,"runtime_verified":False}

def terms(text):
    return set(TOKENS.findall(text.casefold())) - STOP

def search(manifest, query, limit=10):
    require(type(limit) is int and 1 <= limit <= 100, "invalid limit")
    wanted = terms(query)
    if not wanted:
        return []
    scored = []
    for e in manifest["entries"]:
        op = e["operational"]
        fields = ((e["word"], 5), (op["purpose"], 3), (e.get("estate_group"), 2),
                  (e.get("discipline"), 1), (op.get("declared_inputs"), 1),
                  (op.get("declared_output"), 1))
        score = sum(weight * len(wanted & terms(str(value or ""))) for value, weight in fields if value != UNVERIFIED)
        if score:
            scored.append({"gg_id": e["gg_id"], "word": e["word"], "score": score,
                           "purpose": op["purpose"], "source": (e.get("mechanical") or {}).get("source"),
                           "state": "CANDIDATE_NOT_EXECUTION_AUTHORITY"})
    return sorted(scored, key=lambda e: (-e["score"], e["gg_id"]))[:limit]

def compatibility(output, input_):
    """Check explicit port declarations only; never certify execution."""
    if not isinstance(output, dict) or not isinstance(input_, dict):
        return "UNVERIFIED_PORTS"
    keys = ("type", "unit", "shape", "schema")
    for p in (output, input_):
        if p.get("state") != "VERIFIED_CONTRACT" or any(k not in p or p[k] in (None, UNVERIFIED, "") for k in keys):
            return "UNVERIFIED_PORTS"
    return "DECLARED_PORT_MATCH_NOT_EXECUTION_PROOF" if all(output[k] == input_[k] for k in keys) else "ADAPTER_REQUIRED"

def main():
    from validate_translation import fetch
    p = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    p.add_argument("--dictionary", type=Path, default=root/"data/dictionary.json")
    p.add_argument("--translations", type=Path, default=root/"data/translation-geodesy.json")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--query")
    p.add_argument("--candidate-receipt", type=Path)
    p.add_argument("--no-parse", action="store_true")
    a = p.parse_args()
    manifest = compile_manifest(json.loads(a.dictionary.read_text()), json.loads(a.translations.read_text()), fetch, not a.no_parse)
    if a.candidate_receipt is not None:
        manifest["candidate_verification"] = verify_candidate_receipt(json.loads(a.candidate_receipt.read_text()), fetch)
    if a.query is not None:
        manifest["intent_candidates"] = search(manifest, a.query)
    with a.output.open("x", encoding="utf-8") as f:
        json.dump(manifest, f, sort_keys=True, indent=2); f.write("\n")
    print(json.dumps({k:v for k,v in manifest.items() if k not in ("entries", "intent_candidates", "candidate_verification")}, sort_keys=True))
    if "candidate_verification" in manifest:
        print(json.dumps({k:v for k,v in manifest["candidate_verification"].items() if k != "entries"}, sort_keys=True))

if __name__ == "__main__":
    main()
