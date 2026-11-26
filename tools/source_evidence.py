"""Verify immutable source bytes and conservative function boundaries without executing code."""
import ast
import hashlib
import re
import subprocess
from pathlib import PurePosixPath
from urllib.parse import quote

MAX_SOURCE_BYTES = 1_000_000
POLICY = "vedic.static-source.v1"
POLICY_SCHEMA = "vedic.static-policy-receipt.v1"
POLICY_STATE = "STATIC_POLICY_REPRODUCED"
LIGHTNING_LAYER_SOURCE = {
    "repo": "Ventusltd/gridatlas",
    "commit": "afffa9781f6130529ae93052604cd3d98d172a35",
    "blob": "9268a1c4aeac981dea019e3ec63ad8e8384ae227",
    "path": "atlas/cartridges/202610221600-sld-sandbox-v9-8.js",
    "first": 8680,
    "last": 8698,
}
LIGHTNING_LAYER_SYMBOL = "addPublicLightningLayer"
LIGHTNING_INITIALIZER = re.compile(
    r"^[ \t]*window\.initVentusMap[ \t]*=[ \t]*function[ \t]+"
    + LIGHTNING_LAYER_SYMBOL + r"[ \t]*(?=\()", re.MULTILINE
)
JS_FUNCTION = re.compile(
    r"^[ \t]*(?:export[ \t]+)?(?:async[ \t]+)?function[ \t]+"
    r"([A-Za-z_$][A-Za-z0-9_$]*)[ \t]*(?=\()", re.MULTILINE
)
JS_NON_CODE = re.compile(
    r"""/\*[\s\S]*?\*/|//[^\r\n]*|'(?:\\[^\r\n]|[^'\\\r\n])*'|"(?:\\[^\r\n]|[^"\\\r\n])*"|[/`'"]"""
)


def source_link(source):
    path = quote(source["path"], safe="/")
    return (f"https://github.com/{source['repo']}/blob/{source['commit']}/{path}"
            f"#L{source['first']}-L{source['last']}")


def verify_blob(source, raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("source bytes invalid or too large")
    blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    if blob != source["blob"]:
        raise ValueError("source blob differs from pinned evidence")


def python_spans(raw, symbol):
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError) as error:
        raise ValueError("unsupported Python source") from error
    return [
        (min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)]), node.end_lineno)
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol
    ]


def mask_javascript(match):
    value = match[0]
    if len(value) == 1:
        raise ValueError("JavaScript lexical construct outside supported boundary-check subset")
    return re.sub(r"[^\r\n]", " ", value)


def matching_delimiter(text, start, opening, closing):
    depth = 0
    for offset in range(start, len(text)):
        char = text[offset]
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return offset
    raise ValueError("unclosed JavaScript function delimiter")


def verify_javascript_syntax(raw):
    try:
        syntax = subprocess.run(
            ["node", "--check", "--input-type=module"], input=raw,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("JavaScript syntax verifier unavailable") from error
    if syntax.returncode != 0:
        raise ValueError("invalid JavaScript source")


def javascript_text(raw):
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if any(separator in text for separator in ("\r", "\u2028", "\u2029")):
        raise ValueError("unsupported JavaScript line endings")
    return text


def verify_lightning_initializer(raw, first, last):
    """Check the complete assignment in the independently reviewed cartridge."""
    text = javascript_text(raw)
    matches = list(LIGHTNING_INITIALIZER.finditer(text))
    if len(matches) != 1 or text.count("\n", 0, matches[0].start()) + 1 != first:
        raise ValueError("lightning initializer differs from the reviewed assignment")
    snippet = "\n".join(text.split("\n")[first - 1:last])
    masked = JS_NON_CODE.sub(mask_javascript, snippet)
    match = LIGHTNING_INITIALIZER.match(masked)
    params_end = matching_delimiter(masked, match.end(), "(", ")")
    body = re.match(r"\s*\{", masked[params_end + 1:])
    if not body:
        raise ValueError("lightning initializer has no function body")
    close = matching_delimiter(masked, params_end + body.end(), "{", "}")
    if masked[close + 1:].strip() != ";" or masked.count("\n", 0, close) + first != last:
        raise ValueError("lightning initializer span must end at the complete assignment")
    verify_javascript_syntax(raw)


def javascript_spans(raw, symbol):
    masked = JS_NON_CODE.sub(mask_javascript, javascript_text(raw))
    verify_javascript_syntax(raw)

    spans = []
    for match in JS_FUNCTION.finditer(masked):
        if match[1] != symbol:
            continue
        prefix = masked[:match.start()]
        if any(prefix.count(a) != prefix.count(b) for a, b in ("()", "[]", "{}")):
            continue
        # Reject named continuation expressions even when top-level delimiters
        # are balanced. Only plain declarations in this subset are supported.
        if prefix.strip() and prefix.rstrip()[-1] not in ";}":
            continue
        params_end = matching_delimiter(masked, match.end(), "(", ")")
        body = re.match(r"\s*\{", masked[params_end + 1:])
        if not body:
            continue
        body_start = params_end + body.end()
        close = matching_delimiter(masked, body_start, "{", "}")
        if masked[close + 1:].split("\n", 1)[0].strip():
            raise ValueError("JavaScript function end shares a line with another statement")
        spans.append((prefix.count("\n") + 1, masked.count("\n", 0, close) + 1))
    return spans


def verify_exact_span(source, symbol, raw):
    verify_blob(source, raw)
    if source == LIGHTNING_LAYER_SOURCE and symbol == LIGHTNING_LAYER_SYMBOL:
        verify_lightning_initializer(raw, source["first"], source["last"])
        return
    extension = PurePosixPath(source["path"]).suffix
    if extension == ".py":
        spans = python_spans(raw, symbol)
    elif extension in {".js", ".mjs"}:
        spans = javascript_spans(raw, symbol)
    else:
        raise ValueError("unsupported source language")
    if spans != [(source["first"], source["last"])]:
        raise ValueError("source span differs from unique complete top-level function")
