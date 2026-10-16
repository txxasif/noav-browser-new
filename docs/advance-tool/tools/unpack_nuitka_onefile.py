#!/usr/bin/env python3
"""Extract the payload of a Nuitka onefile executable (KAX = uncompressed blobs).

Format (nuitka/build/static_src/OnefileBootstrap.c):
  header : b"KA" + b"X" (no compression) or b"Y" (zstd)
  entry* : name (UTF-16LE on Windows / UTF-8 elsewhere, NUL-terminated)
           uint64 payload size
           uint32 archive size  (only when compression is on)
           payload bytes
  end    : empty name (single NUL / 0x0000)
"""
import argparse
import os
import struct
import sys


def find_header(data, magic):
    off = 0
    hits = []
    while True:
        i = data.find(magic, off)
        if i < 0:
            return hits
        hits.append(i)
        off = i + 1


def parse(f, base, outdir, namewidth=2, sizebytes=8, limit=None, verbose=True, whole=False):
    """whole=True -> read the entire file into memory (fast)."""
    entries = []
    if whole:
        import io

        f.seek(base + 3)
        r = f
        pos = base + 3
    else:
        f.seek(base + 3)
        r = f
        pos = base + 3

    n = 0
    while True:
        nb = bytearray()
        while True:
            ch = r.read(namewidth)
            pos += namewidth
            if len(ch) < namewidth:
                return entries, "EOF mid-name"
            if ch == b"\x00" * namewidth:
                break
            nb += ch
        name = nb.decode("utf-16-le" if namewidth == 2 else "utf-8", "replace")
        if name == "":
            return entries, "ok (clean terminator)"

        raw = r.read(sizebytes)
        pos += sizebytes
        if len(raw) < sizebytes:
            return entries, "EOF mid-size"
        size = struct.unpack("<Q", raw)[0] if sizebytes == 8 else struct.unpack("<I", raw)[0]

        if pos + size > os.path.getsize(f.name) and not whole:
            return entries, f"EOF mid-data for {name}"

        entries.append({"name": name, "size": size, "offset": pos})
        if outdir is not None:
            target = os.path.join(outdir, name.replace("\\", "/"))
            os.makedirs(os.path.dirname(target) or outdir, exist_ok=True)
            remaining = size
            with open(target, "wb") as out:
                while remaining:
                    chunk = r.read(min(1 << 22, remaining))
                    if not chunk:
                        return entries, f"short read for {name}"
                    out.write(chunk)
                    remaining -= len(chunk)
        else:
            r.seek(size, 1)
        pos += size

        n += 1
        if verbose and (n % 50 == 0 or n < 8):
            print(f"  [{n}] {name} ({size:,} bytes)", file=sys.stderr)
        if limit and n >= limit:
            return entries, "limit reached"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("-o", "--outdir", default=None)
    ap.add_argument("--base", type=lambda s: int(s, 0), default=None)
    ap.add_argument("--namewidth", type=int, default=2)
    ap.add_argument("--sizebytes", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--list-only", action="store_true")
    args = ap.parse_args()

    size = os.path.getsize(args.exe)
    if args.base is None:
        with open(args.exe, "rb") as f:
            hits = find_header(f.read(), b"KAX")
        print(f"KAX candidates: {[hex(h) for h in hits]}")
        if not hits:
            hits = find_header(open(args.exe, "rb").read(), b"KAY")
            print(f"KAY candidates: {[hex(h) for h in hits]}")
        if not hits:
            sys.exit("no payload header found")
        args.base = hits[0]

    outdir = None if args.list_only else (args.outdir or os.path.splitext(args.exe)[0] + "_payload")
    if outdir:
        os.makedirs(outdir, exist_ok=True)

    with open(args.exe, "rb") as f:
        entries, status = parse(f, args.base, outdir, args.namewidth, args.sizebytes, args.limit)

    print(f"\nbase={hex(args.base)} entries={len(entries)} status={status}")
    total = sum(e["size"] for e in entries)
    print(f"payload bytes: {total:,} (file {size:,})")
    print(f"last entry ends at {hex(entries[-1]['offset'] + entries[-1]['size']) if entries else '-'}")
    if args.limit:
        for e in entries:
            print(f"  {e['name']:60} {e['size']:>14,}")
    if outdir:
        print(f"extracted to {outdir}")


if __name__ == "__main__":
    main()
