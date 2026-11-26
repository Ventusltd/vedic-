"""Apply additive candidate checking to pinned factory in isolated CI checkout.
Formal registry and admit() are unchanged. No new builder.
"""
from pathlib import Path
import sys
p=Path(sys.argv[1])/"tools/package_factory.py"
s=p.read_text()
old='    pin=REVIEWED_RECEIPTS[family]\n    need(sha(raw)==pin["receipt_sha256"],"RECEIPT_DIGEST")'
new='    return check_receipt_pin(REVIEWED_RECEIPTS[family],raw,source_files,closure_raw)\n\ndef check_receipt_pin(pin, raw, source_files, closure_raw):\n    """Common receipt validation; does not register or grant admission."""\n    need(sha(raw)==pin["receipt_sha256"],"RECEIPT_DIGEST")'
assert s.count(old)==1
p.write_text(s.replace(old,new))
