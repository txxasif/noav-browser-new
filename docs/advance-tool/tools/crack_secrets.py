#!/usr/bin/env python3
"""Pull the raw masked-secret byte literals out of the blob and try to unmask them.

The app stores its secrets as `_dyn_decrypt_sec(enc_data, mask_data) -> str` byte
pairs (`_K_ENC/_K_MSK`, `_BT_ENC/_BT_MSK`, ...).  The decryption is one of a few
XOR based one-liners; rather than guess, try them all and keep whatever yields
readable text.

Usage:  python3 crack_secrets.py <main.dll>
"""
import importlib.util
import os
import re
import struct
import sys

spec = importlib.util.spec_from_file_location(
    "nb", os.path.join(os.path.dirname(os.path.abspath(__file__)), "nuitka_blob.py"))
nb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nb)

DLL = sys.argv[1] if len(sys.argv) > 1 else "main.dll"


def raw_value_bytes(v, out):
    if isinstance(v, dict):
        if "__code__" in v:
            return
        for k in v:
            raw_value_bytes(v[k], out)
    elif isinstance(v, list):
        for i in v:
            raw_value_bytes(i, out)
    elif isinstance(v, (bytes, bytearray)):
        out.append(bytes(v))


def get_module_values(name):
    data = open(DLL, "rb").read()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsize = struct.unpack_from("<H", data, pe + 20)[0]
    sec = pe + 24 + optsize
    for i in range(nsec):
        o = sec + i * 40
        if data[o:o + 8].rstrip(b"\0") == b".rdata":
            vsize, vaddr, size, raw = struct.unpack_from("<IIII", data, o + 8)
            base, span = raw, data[raw:raw + size]
            break
    name_re = re.compile(rb"[A-Za-z_][A-Za-z0-9_.]{0,60}\x00")
    entries, _ = nb.find_directory(span, name_re)
    for n, off, sz in entries:
        if n == name:
            b = nb.Blob(data, off + base, off + base + sz)
            count = b.u16()
            return [b.value() for _ in range(count)]
    raise SystemExit(f"{name} not found")


def printable_score(b):
    if not b:
        return 0
    ok = sum(1 for c in b if 32 <= c < 127)
    return ok / len(b)


def try_algorithms(enc, mask):
    out = {}
    # 1. plain byte XOR, mask cycled
    for shift in range(len(mask)):
        m = mask[shift:] + mask[:shift]
        x = bytes(a ^ m[i % len(m)] for i, a in enumerate(enc))
        out[f"xor-cycle shift={shift}"] = x
    # 2. mask repeated over enc reversed
    for shift in range(len(mask)):
        m = mask[shift:] + mask[:shift]
        x = bytes(a ^ m[i % len(m)] for i, a in enumerate(enc[::-1]))
        out[f"xor-cycle-reversed shift={shift}"] = x
    # 3. every mask byte used as a single-byte key
    for kb in set(mask):
        out[f"xor-const {kb:#04x}"] = bytes(a ^ kb for a in enc)
    # 4. mask XOR constant then xor-cycle
    return out


def main():
    targets = sys.argv[2:] or ["sell_engine.config", "instagram_engine.config", "config",
                               "instagram_engine.app_gui"]
    for mod in targets:
        vals = get_module_values(mod)
        raw = []
        raw_value_bytes(vals, raw)
        raw = [b for b in raw if len(b) >= 4]
        print(f"\n########## {mod}: {len(raw)} byte literals, lengths {[len(b) for b in raw]}")
        encs = [b for b in raw if len(b) != 16]
        masks = [b for b in raw if len(b) == 16]
        for enc in encs:
            for mask in masks:
                for alg, res in try_algorithms(enc, mask).items():
                    sc = printable_score(res)
                    if sc > 0.9:
                        print(f"  len={len(enc)} mask={mask.hex()} {alg:28} -> {res[:90]!r}")


if __name__ == "__main__":
    main()
