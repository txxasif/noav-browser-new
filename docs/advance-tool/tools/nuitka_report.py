#!/usr/bin/env python3
"""Reconstruct a source skeleton from the decoded Nuitka structure JSON.

Nuitka compiles Python to C, so statement bodies are gone, but every code object
keeps its name, its enclosing scope (qualname), source line number, and full
co_varnames/arg layout.  Combined with the constants blob (all literal strings)
this rebuilds the *shape* of the original source: classes, defs with their
signatures, line numbers, and every literal.
"""
import argparse
import json
import re
from collections import defaultdict

APP_PREFIXES = ("instagram_engine", "meta_engine", "sell_engine", "combined_engine",
                "core", "utils")
APP_EXACT = {"main", "__main__", "pipeline_bridge", "config", "git_updater",
             "mail_service_app", "master_suite"}

FLAG_QUALNAME = 0x01
FLAG_FREEVARS = 0x02
FLAG_KW_ONLY = 0x04
FLAG_POS_ONLY = 0x08
FLAG_OPTIMIZED = 0x40
FLAG_NEWLOCALS = 0x80
FLAG_VARARGS = 0x100
FLAG_VARKEYWORDS = 0x200
KIND_MASK = 0x30
KINDS = {0: "", 0x10: "  # generator", 0x20: "  # async", 0x30: "  # async generator"}

DECOR_HINT = re.compile(r"^(setter|getter|deleter|property)$")


def is_app(mod):
    return mod.startswith(APP_PREFIXES) or mod.split(".")[0] in APP_EXACT


def all_codes(values):
    out = []

    def rec(v):
        if isinstance(v, dict):
            if "__code__" in v:
                out.append(v)
                return
            for k in v:
                rec(v[k])
        elif isinstance(v, list):
            for i in v:
                rec(i)

    rec(values)
    return out


def signature(c):
    names = [a for a in (c.get("args") or []) if isinstance(a, str)]
    argc = c.get("arg_count") or 0
    flags = c.get("flags") or 0
    kwn = c.get("kw_only") or 0
    posn = c.get("pos_only") or 0
    pos = names[:argc]
    rest = names[argc:]
    parts = []
    for i, n in enumerate(pos):
        parts.append(n)
        if posn and i == posn - 1:
            parts.append("/")
    idx = 0
    if flags & FLAG_VARARGS:
        parts.append("*" + (rest[idx] if idx < len(rest) else "args"))
        idx += 1
    elif kwn:
        parts.append("*")
    for n in rest[idx:idx + kwn]:
        parts.append(n)
    idx += kwn
    if flags & FLAG_VARKEYWORDS and idx < len(rest):
        parts.append("**" + rest[idx])
    return ", ".join(parts)


def module_report(mod, values, fh):
    codes = all_codes(values)
    interesting = [c for c in codes if not str(c["name"]).startswith("<")]
    exprs = [c for c in codes if str(c["name"]).startswith("<")]
    maxline = max((c.get("line") or 0) for c in interesting) if interesting else 0

    kinds = defaultdict(int)
    for c in codes:
        kinds[c["__code__"]] += 1

    fh.write("=" * 100 + "\n")
    fh.write(f"MODULE  {mod}\n")
    fh.write(f"  {len(codes)} code objects {dict(kinds)}   last source line: ~{maxline}\n")
    fh.write("=" * 100 + "\n")

    # group code objects by their enclosing scope (qualname)
    scopes = defaultdict(list)
    for c in interesting:
        own, parent = str(c["name"]), str(c["qualname"])
        if own == parent:                       # module body or its own definition
            continue
        scopes[parent].append(c)

    top = sorted((c for c in interesting if str(c["name"]) == str(c["qualname"])),
                 key=lambda x: x.get("line") or 0)

    def emit_callable(c, indent=0, label=None):
        own = str(c["name"])
        pad = "    " * indent
        tag = label or ("class" if own in scopes else "def  ")
        fh.write(f"{pad}{tag} {own}({signature(c)})".ljust(84) +
                 f"# line {c.get('line')}{KINDS.get((c.get('flags') or 0) & KIND_MASK, '')}\n")

    for c in top:
        own = str(c["name"])
        if own in scopes:                        # class body code object
            fh.write(f"\nclass {own}({signature(c)})".ljust(84) + f"# line {c.get('line')}\n")
            for m in sorted(scopes[own], key=lambda x: x.get("line") or 0):
                emit_callable(m, 1, label="def ")
            scopes.pop(own)
        else:
            fh.write(f"\ndef  {own}({signature(c)})".ljust(84) + f"# line {c.get('line')}\n")
            for m in sorted(scopes.pop(own, []), key=lambda x: x.get("line") or 0):
                emit_callable(m, 1, label="def ")     # nested closures

    # scopes without their own code object (Nuitka stores classes without one)
    for scope in sorted(scopes, key=lambda s: min(x.get("line") or 0 for x in scopes[s])):
        members = sorted(scopes[scope], key=lambda x: x.get("line") or 0)
        is_class = any(str(m["name"]) == "__init__" for m in members) or \
            any((m.get("args") or [None])[:1] == ["self"] for m in members)
        line = min((m.get("line") or 0) for m in members)
        fh.write(f"\n{'class' if is_class else 'scope'} {scope}".ljust(84) + f"# ~line {line}\n")
        for m in members:
            emit_callable(m, 1, label="def ")

    if exprs:
        lines = sorted({(c.get("line") or 0) for c in exprs})
        fh.write(f"\n# {len(exprs)} module/comprehension/expression code objects "
                 f"(lines {lines[0]}..{lines[-1]})\n")
    fh.write("\n")


def collect_strings(values, out):
    def rec(v):
        if isinstance(v, str):
            if v:
                out.append(v)
        elif isinstance(v, list):
            for i in v:
                rec(i)
        elif isinstance(v, dict):
            if "__code__" in v or "__bytes__" in v or "__bytearray__" in v:
                return
            for k in v:
                rec(k)
                rec(v[k])

    rec(values)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("structure")
    ap.add_argument("--skeleton", default=None)
    ap.add_argument("--strings", default=None)
    ap.add_argument("--all-modules", action="store_true")
    args = ap.parse_args()
    mods = json.load(open(args.structure))

    if args.skeleton:
        with open(args.skeleton, "w", encoding="utf-8", errors="backslashreplace") as fh:
            for mod in sorted(mods):
                if args.all_modules or is_app(mod):
                    module_report(mod, mods[mod], fh)
        print(f"wrote {args.skeleton}")

    if args.strings:
        with open(args.strings, "w", encoding="utf-8", errors="backslashreplace") as fh:
            for mod in sorted(mods):
                if not (args.all_modules or is_app(mod)):
                    continue
                strs, seen = [], set()
                collect_strings(mods[mod], strs)
                uniq = [s for s in strs if not (s in seen or seen.add(s))]
                fh.write("=" * 100 + f"\nMODULE  {mod}   ({len(uniq)} distinct string literals)\n" + "=" * 100 + "\n")
                for s in uniq:
                    fh.write(repr(s if len(s) <= 400 else s[:400] + f"...[{len(s)} chars]") + "\n")
                fh.write("\n")
        print(f"wrote {args.strings}")


if __name__ == "__main__":
    main()
