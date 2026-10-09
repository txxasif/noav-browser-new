"""Meta Creator — IG Creator full backup/restore (single CSV format).

One CSV schema for BOTH export and import, carrying everything needed to
restore a working session on any machine:

    id, username, instagram_username, name, email, password, meta_password,
    twofa_secret, cookies, mail_tokens, mail_provider, dob, device_model,
    device_ua, platform, target, status, created_at

- ``cookies`` is the ``; ``-joined session header (the pool drain, the combo
  exporter and the 2FA OTP reader all work from it — no cookie files needed).
- ``mail_tokens`` is a JSON object ``{"tempmail_token": ..., ...}`` so the
  mail.td inbox (password/2FA OTP reads) survives the move.
- ``session_file`` / ``profile_dir`` are LOCAL paths and deliberately NOT
  carried — they are rebuilt on next use.

"Damaged" (shared definition, also shown in the dashboard modal):

    status IN ('Failed','Banned') OR extra startswith 'Dead:' OR attempts >= 3

CLI (last stdout line is always a JSON summary for the Node backend)::

    python ig_backup.py export --kind ig [--exclude-damaged] --out backup.csv
    python ig_backup.py import --file backup.csv [--exclude-damaged]
                               [--skip-existing]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db  # noqa: E402
import store  # noqa: E402

FULL_COLUMNS = [
    "id", "username", "instagram_username", "name", "email", "password",
    "meta_password", "twofa_secret", "cookies", "mail_tokens",
    "mail_provider", "dob", "device_model", "device_ua",
    "platform", "target", "status", "attempts", "created_at",
]

DAMAGED_STATUSES = {"Failed", "Banned"}
MAX_ATTEMPTS = 3


def _extra_dead_reason(rec: dict) -> str:
    """Return the stored dead marker, accepting the legacy 'Dead: …' string
    and the merged-dict form written by store.mark_ig_creator_dead."""
    extra = rec.get("extra")
    if isinstance(extra, str) and extra.startswith("Dead:"):
        return extra[len("Dead:"):].strip()
    if rec.get("dead_reason"):
        return str(rec.get("dead_reason"))
    if isinstance(extra, dict) and extra.get("dead_reason"):
        return str(extra.get("dead_reason"))
    return ""


def is_damaged(rec: dict) -> bool:
    """Shared damaged-account test (export filter + import filter + modal hint)."""
    if str(rec.get("status") or "") in DAMAGED_STATUSES:
        return True
    if _extra_dead_reason(rec):
        return True
    try:
        if int(rec.get("attempts") or 0) >= MAX_ATTEMPTS:
            return True
    except (TypeError, ValueError):
        pass
    return False


def is_ig(rec: dict) -> bool:
    return (rec.get("target") or "") != "telegram" and str(rec.get("status") or "") != "MetaCreated"


def _row_for_export(rec: dict) -> dict:
    tokens = rec.get("mail_tokens") or {}
    if not isinstance(tokens, dict):
        tokens = {}
    # `extra` merge in db.dict_from_row already surfaces mail_tokens top-level.
    out = {}
    for col in FULL_COLUMNS:
        if col == "mail_tokens":
            out[col] = json.dumps(tokens, ensure_ascii=False) if tokens else ""
        else:
            v = rec.get(col)
            out[col] = "" if v is None else str(v)
    return out


def do_export(kind: str, exclude_damaged: bool, out_path: str) -> dict:
    recs = store.list_all()
    recs = [r for r in recs if (r.get("target") or "") != "telegram"]
    if kind == "ig":
        recs = [r for r in recs if is_ig(r)]
    elif kind == "meta":
        recs = [r for r in recs if not is_ig(r)]
    total = len(recs)
    skipped = 0
    if exclude_damaged:
        kept = []
        for r in recs:
            if is_damaged(r):
                skipped += 1
            else:
                kept.append(r)
        recs = kept
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FULL_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in recs:
            w.writerow(_row_for_export(r))
    return {"ok": True, "exported": len(recs), "skipped_damaged": skipped,
            "total": total, "file": out_path, "columns": FULL_COLUMNS}


def _parse_mail_tokens(raw: str) -> dict:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _order_rows(rows, order: str):
    """Order import rows by created_at ('%Y-%m-%d %H:%M:%S' sorts
    lexicographically). Rows without a date always go last, in file order,
    in both directions."""
    def key(r):
        return (r.get("created_at") or "").strip()
    dated = [r for r in rows if key(r)]
    dateless = [r for r in rows if not key(r)]
    dated.sort(key=key, reverse=(order != "oldest"))
    return dated + dateless


def do_import(file_path: str, exclude_damaged: bool, skip_existing: bool,
              limit: int = 0, order: str = "newest") -> dict:
    if not os.path.isfile(file_path):
        return {"ok": False, "error": f"file not found: {file_path}"}
    if os.path.getsize(file_path) > 100 * 1024 * 1024:
        return {"ok": False, "error": "file too large (max 100 MB)"}
    if file_path.lower().endswith(".xlsx"):
        import io
        try:
            _text = xlsx_to_csv_text(file_path)
        except Exception as exc:
            return {"ok": False, "error": f"could not read the .xlsx: {exc}"}
        _fh = io.StringIO(_text, newline="")
    else:
        _fh = open(file_path, "r", newline="", encoding="utf-8-sig")
    with _fh as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not {"username"}.intersection(
                set(reader.fieldnames or [])) and "instagram_username" not in (reader.fieldnames or []):
            return {"ok": False, "error": "not a Meta Creator backup: missing username columns"}
        rows = list(reader)

    order = "oldest" if str(order or "").lower() == "oldest" else "newest"
    for _ln, _r in enumerate(rows, start=2):
        _r["_lineno"] = _ln
    rows = _order_rows(rows, order)
    total_rows = len(rows)
    try:
        limit = max(0, int(limit or 0))
    except (TypeError, ValueError):
        limit = 0
    if limit:
        rows = rows[:limit]

    existing = store.list_all()
    by_id = {str(r.get("id")): r for r in existing if r.get("id")}
    by_uname = {}
    for r in existing:
        for key in (r.get("instagram_username"), r.get("username")):
            if key and str(key) not in by_uname:
                by_uname[str(key).lower()] = r

    imported = updated = skipped_existing = skipped_damaged = 0
    errors = []
    for row in rows:
        i = row.pop("_lineno", "?")
        try:
            uname = (row.get("instagram_username") or row.get("username") or "").strip()
            if not uname:
                errors.append(f"row {i}: no username")
                continue
            status = (row.get("status") or "Created").strip() or "Created"
            probe = {"status": status, "attempts": row.get("attempts") or 0,
                     "extra": row.get("extra") or ""}
            if exclude_damaged and is_damaged(probe):
                skipped_damaged += 1
                continue
            rec_id = (row.get("id") or "").strip()
            hit = by_id.get(rec_id) if rec_id else None
            if hit is None:
                hit = by_uname.get(uname.lower())
            if hit is not None and skip_existing:
                skipped_existing += 1
                continue
            tokens = _parse_mail_tokens(row.get("mail_tokens") or "")
            fresh = {
                "id": rec_id or None,
                "username": (row.get("username") or uname).strip(),
                "instagram_username": (row.get("instagram_username") or uname).strip(),
                "name": (row.get("name") or "").strip(),
                "email": (row.get("email") or "").strip(),
                "password": row.get("password") or "",
                "meta_password": row.get("meta_password") or row.get("password") or "",
                "twofa_secret": (row.get("twofa_secret") or "").strip(),
                "cookies": row.get("cookies") or "",
                "mail_tokens": tokens,
                "mail_provider": (row.get("mail_provider") or "mailtd").strip() or "mailtd",
                "dob": (row.get("dob") or "").strip(),
                "device_model": (row.get("device_model") or "").strip(),
                "device_ua": (row.get("device_ua") or "").strip(),
                "platform": (row.get("platform") or "Meta+Instagram").strip() or "Meta+Instagram",
                "target": (row.get("target") or "meta").strip() or "meta",
                "status": status,
            }
            if row.get("created_at"):
                fresh["created_at"] = row.get("created_at")
            try:
                fresh["attempts"] = max(0, int(row.get("attempts") or 0))
            except (TypeError, ValueError):
                pass
            if hit is not None:
                # Update: keep LOCAL paths (session_file/profile_dir) — the
                # backup never carries them, the local disk still has them.
                merged = dict(hit)
                merged.update({k: v for k, v in fresh.items() if k not in ("session_file", "profile_dir")})
                merged["id"] = hit["id"]
                if not merged.get("session_file"):
                    merged.pop("session_file", None)
                store.add(merged)
                updated += 1
                by_id[str(hit["id"])] = merged
                by_uname[uname.lower()] = merged
            else:
                if not fresh["id"]:
                    fresh.pop("id", None)
                elif fresh["id"] in by_id:
                    fresh.pop("id", None)
                saved = store.add(fresh)
                imported += 1
                by_id[str(saved.get("id"))] = saved
                by_uname[uname.lower()] = saved
        except Exception as exc:
            errors.append(f"row {i}: {exc}")
    return {"ok": True, "imported": imported, "updated": updated,
            "skipped_existing": skipped_existing,
            "skipped_damaged": skipped_damaged, "errors": errors[:20],
            "error_count": len(errors), "total_rows": total_rows,
            "selected_rows": len(rows), "limit": limit, "order": order}


def do_mark_dead(usernames) -> dict:
    """Flag saved rows as Failed so the pool drain never picks them again."""
    existing = [r for r in store.list_all() if (r.get("target") or "") != "telegram"]
    by_name = {}
    for r in existing:
        for key in (r.get("instagram_username"), r.get("username")):
            if key and str(key).lower() not in by_name:
                by_name[str(key).lower()] = r
    marked, missing, already = [], [], []
    for raw in usernames:
        uname = str(raw or "").strip().lstrip("@").lower()
        if not uname:
            continue
        hit = by_name.get(uname)
        if hit is None:
            missing.append(uname)
            continue
        if is_damaged(hit):
            already.append(uname)
            continue
        try:
            store.mark_ig_creator_dead(hit["id"], "ig-check not_found")
            marked.append(uname)
        except Exception as exc:
            missing.append(uname)
    return {"ok": True, "marked": marked, "already_damaged": already, "missing": missing}


# ---------------------------------------------------------------------------
# XLSX -> backup CSV (stdlib only: works in the shipped build, no openpyxl).
# Accepts the spreadsheet forms the older builds / Google Sheets produce:
#   * with or without a header row (headerless = FULL_COLUMNS order),
#   * dates turned into Excel serial numbers (dob / created_at),
#   * counts stored as floats ("0.0"), blank cells skipped by the writer.
# ---------------------------------------------------------------------------
_XL_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _xl_col_index(ref: str) -> int:
    n = 0
    for ch in ref:
        if not ch.isalpha():
            break
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def _xl_num_text(txt: str) -> str:
    try:
        f = float(txt)
    except (TypeError, ValueError):
        return txt or ""
    return str(int(f)) if f == int(f) else repr(f)


def _xl_serial_to_dt(txt: str):
    import datetime as _dt
    try:
        return _dt.datetime(1899, 12, 30) + _dt.timedelta(days=float(txt))
    except (TypeError, ValueError, OverflowError):
        return None


def xlsx_rows(path: str) -> list:
    """Return the first worksheet as a list of rows (lists of strings)."""
    import re
    import zipfile
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(_XL_NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(_XL_NS + "t")))
        sheets = sorted((n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n)),
                        key=lambda n: int(re.findall(r"\d+", n)[0]))
        if not sheets:
            raise ValueError("no worksheet found in the .xlsx")
        out = []
        for row in ET.fromstring(z.read(sheets[0])).iter(_XL_NS + "row"):
            cells = {}
            for c in row.findall(_XL_NS + "c"):
                ref = c.get("r") or ""
                idx = _xl_col_index(ref) if ref else len(cells)
                t = c.get("t")
                v = c.find(_XL_NS + "v")
                if t == "s" and v is not None and (v.text or "").isdigit():
                    val = shared[int(v.text)] if int(v.text) < len(shared) else ""
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(_XL_NS + "t"))
                elif t in ("str", "b", "e"):
                    val = (v.text or "") if v is not None else ""
                else:
                    val = _xl_num_text(v.text) if v is not None and v.text is not None else ""
                cells[idx] = val
            if cells and any(str(x).strip() for x in cells.values()):
                width = max(cells) + 1
                out.append([cells.get(i, "") for i in range(width)])
        return out


def xlsx_to_csv_text(path: str) -> str:
    """Convert a backup .xlsx into the standard full-backup CSV text."""
    import calendar
    rows = xlsx_rows(path)
    if not rows:
        raise ValueError("the spreadsheet is empty")
    first = [str(x).strip().lower() for x in rows[0]]
    has_header = any(h in ("id", "username", "instagram_username") for h in first)
    if has_header:
        cols = first
        body = rows[1:]
    else:
        cols = list(FULL_COLUMNS)
        body = rows
    idx = {name: i for i, name in enumerate(cols) if name in FULL_COLUMNS}
    if "username" not in idx and "instagram_username" not in idx:
        raise ValueError("not a Meta Creator backup: no username column")
    import io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(FULL_COLUMNS)
    for r in body:
        rec = {}
        for name in FULL_COLUMNS:
            i = idx.get(name)
            rec[name] = str(r[i]).strip("\ufeff") if i is not None and i < len(r) else ""
        if not (rec["username"] or rec["instagram_username"]):
            continue
        if rec["dob"] and rec["dob"].replace(".", "", 1).isdigit():
            d = _xl_serial_to_dt(rec["dob"])
            if d:
                rec["dob"] = f"{d.year}-{calendar.month_name[d.month]}-{d.day}"
        if rec["created_at"] and rec["created_at"].replace(".", "", 1).isdigit():
            d = _xl_serial_to_dt(rec["created_at"])
            if d:
                rec["created_at"] = d.strftime("%Y-%m-%d %H:%M:%S")
        if rec["attempts"]:
            rec["attempts"] = _xl_num_text(rec["attempts"])
        w.writerow([rec[c] for c in FULL_COLUMNS])
    return buf.getvalue()


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="IG Creator full backup/restore")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_exp = sub.add_parser("export", help="export accounts to a full-backup CSV")
    p_exp.add_argument("--kind", default="ig", choices=["ig", "meta", "all"])
    p_exp.add_argument("--exclude-damaged", action="store_true")
    p_exp.add_argument("--out", required=True)
    p_imp = sub.add_parser("import", help="import a full-backup CSV")
    p_imp.add_argument("--file", required=True)
    p_imp.add_argument("--exclude-damaged", action="store_true")
    p_imp.add_argument("--skip-existing", action="store_true", default=True)
    p_imp.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    p_imp.add_argument("--limit", type=int, default=0,
                       help="import at most N rows (0 = all)")
    p_imp.add_argument("--order", default="newest", choices=["newest", "oldest"],
                       help="which end of the file the --limit rows come from")
    p_x2c = sub.add_parser("xlsx2csv", help="convert a backup .xlsx to full-backup CSV text")
    p_x2c.add_argument("--file", required=True)
    p_clear = sub.add_parser("clear-kind", help="delete one workspace list (meta|ig)")
    p_clear.add_argument("--kind", default="ig", choices=["ig", "meta"])
    p_purge = sub.add_parser("purge-damaged", help="delete only damaged rows in one list (meta|ig)")
    p_purge.add_argument("--kind", default="ig", choices=["ig", "meta"])
    p_dead = sub.add_parser("mark-dead", help="flag saved rows Failed by username")
    p_dead.add_argument("--usernames-json", default="[]")
    args = ap.parse_args(argv)
    if args.cmd == "export":
        summary = do_export(args.kind, bool(args.exclude_damaged), args.out)
    elif args.cmd == "xlsx2csv":
        try:
            _csv = xlsx_to_csv_text(args.file)
            summary = {"ok": True, "csv_text": _csv, "rows": max(0, _csv.count("\n") - 1)}
        except Exception as exc:
            summary = {"ok": False, "error": str(exc)[:200]}
    elif args.cmd == "mark-dead":
        try:
            names = json.loads(args.usernames_json)
        except Exception:
            names = []
        summary = do_mark_dead(names if isinstance(names, list) else [])
    elif args.cmd == "clear-kind":
        summary = {"ok": True, "kind": args.kind,
                   "deleted": store.clear_kind(args.kind)}
    elif args.cmd == "purge-damaged":
        summary = {"ok": True, "kind": args.kind,
                   "removed": store.purge_damaged(args.kind)}
    else:
        summary = do_import(args.file, bool(args.exclude_damaged), bool(args.skip_existing),
                            limit=args.limit, order=args.order)
    sys.stdout.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
