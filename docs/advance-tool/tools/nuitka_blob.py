#!/usr/bin/env python3
"""Decode the Nuitka constants blob out of a compiled Windows binary (main.dll).

Implements the tag system from nuitka/build/include/nuitka/constants_blob_spec.h
and the readers in nuitka/build/static_src/HelpersConstantsBlob.c.

Layout
------
The blob is a flat directory:

    for each module:  <module name>\\0  uint32 data_size  <data_size bytes>
    (repeated for every compiled module; the directory itself is split across
     several linked regions in the PE, so every region is walked separately)

Then, per module, the data is:

    uint16  count          # number of top level constants
    <count tagged values>

Tagged values are one tag byte + payload (see TAGS below).  Code objects carry
the function/class name, qualname, source line number, argument names and
annotation mapping - i.e. the source skeleton - plus the module's string
constants.
"""
import argparse
import json
import re
import struct
import sys

# ---------------------------------------------------------------- tag table
TAG_PREVIOUS = 0x70          # 'p'
TAG_NONE = 0x6E              # 'n'
TAG_TRUE = 0x74              # 't'
TAG_FALSE = 0x46             # 'F'
TAG_TUPLE = 0x54             # 'T'
TAG_LIST = 0x4C              # 'L'
TAG_DICT = 0x44              # 'D'
TAG_SET = 0x53               # 'S'
TAG_FROZENSET = 0x50         # 'P'
TAG_FROZENDICT = 0x65        # 'e'
TAG_LONG_POS_SMALL = 0x6C    # 'l'
TAG_LONG_NEG_SMALL = 0x71    # 'q'
TAG_LONG_POS_LARGE = 0x67    # 'g'
TAG_LONG_NEG_LARGE = 0x47    # 'G'
TAG_INT_POSITIVE = 0x69      # 'i'
TAG_INT_NEGATIVE = 0x49      # 'I'
TAG_FLOAT_SPECIAL = 0x5A     # 'Z'
TAG_FLOAT = 0x66             # 'f'
TAG_TEXT_EMPTY = 0x73        # 's'
TAG_TEXT_SINGLE = 0x77       # 'w'
TAG_TEXT_UTF8_LEN = 0x76     # 'v'
TAG_TEXT_UTF8_Z = 0x75       # 'u'
TAG_ATTRIBUTE_NAME = 0x61    # 'a'
TAG_BYTES_LEN = 0x62         # 'b'
TAG_BYTES_Z = 0x63           # 'c'
TAG_BYTES_SINGLE = 0x64      # 'd'
TAG_SLICE = 0x3A             # ':'
TAG_RANGE = 0x3B             # ';'
TAG_COMPLEX_SPECIAL = 0x4A   # 'J'
TAG_COMPLEX = 0x6A           # 'j'
TAG_BYTEARRAY = 0x42         # 'B'
TAG_BUILTIN_ANON = 0x4D      # 'M'
TAG_BUILTIN_SPECIAL = 0x51   # 'Q'
TAG_BLOB_DATA = 0x58         # 'X'
TAG_GENERIC_ALIAS = 0x41     # 'A'
TAG_UNION_TYPE = 0x48        # 'H'
TAG_BUILTIN_NAMED = 0x4F     # 'O'
TAG_BUILTIN_EXCEPTION = 0x45 # 'E'
TAG_CODE_OBJECT = 0x43       # 'C'
TAG_MODULE_CODE = 0x4B       # 'K'
TAG_CLASS_CODE = 0x57        # 'W'
TAG_GENEXPR_CODE = 0x59      # 'Y'
TAG_END = 0x2E               # '.'

ANON_NAMES = {
    0: "NoneType", 1: "ellipsis", 2: "NotImplementedType", 3: "function",
    4: "generator", 5: "builtin_function_or_method", 6: "code", 7: "module",
    10: "UnionType",
}
SPECIAL_NAMES = {0: "Ellipsis", 1: "NotImplemented", 2: "sys.version_info"}
FLOAT_SPECIALS = {0: 0.0, 1: -0.0, 2: float("nan"), 3: float("-nan"),
                  4: float("inf"), 5: float("-inf")}

CODE_FLAG_QUALNAME = 0x01
CODE_FLAG_FREE_VARS = 0x02
CODE_FLAG_KW_ONLY = 0x04
CODE_FLAG_POS_ONLY = 0x08
CODE_KIND_MASK = 0x30
CODE_KIND_GENERATOR = 0x10
CODE_KIND_COROUTINE = 0x20
CODE_KIND_ASYNCGEN = 0x30


class CodeObject:
    __slots__ = ("name", "qualname", "line", "arg_names", "arg_count",
                 "kw_only", "pos_only", "flags", "kind", "is_class", "is_module")

    def __init__(self, name, qualname, line, arg_names, arg_count, flags):
        self.name = name
        self.qualname = qualname
        self.line = line
        self.arg_names = arg_names
        self.arg_count = arg_count
        self.kw_only = 0
        self.pos_only = 0
        self.flags = flags
        kind = flags & CODE_KIND_MASK
        self.kind = {0: "func", CODE_KIND_GENERATOR: "generator",
                     CODE_KIND_COROUTINE: "coroutine",
                     CODE_KIND_ASYNCGEN: "asyncgen"}[kind]
        self.is_class = False
        self.is_module = False

    def __repr__(self):
        return f"<code {self.kind} {self.qualname!r} line {self.line} args={self.arg_names}>"


class Blob:
    def __init__(self, data, pos, end):
        self.d = data
        self.pos = pos
        self.end = end
        self.last = None

    # -- primitives ------------------------------------------------------
    def u8(self):
        v = self.d[self.pos]
        self.pos += 1
        return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.pos)[0]
        self.pos += 2
        return v

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.pos)[0]
        self.pos += 4
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.pos)[0]
        self.pos += 4
        return v

    def f64(self):
        v = struct.unpack_from("<d", self.d, self.pos)[0]
        self.pos += 8
        return v

    def varint(self):
        result = 0
        factor = 1
        while True:
            v = self.d[self.pos]
            self.pos += 1
            result += (v & 127) * factor
            if v < 128:
                return result
            factor <<= 7

    def cstring(self):
        i = self.d.index(0, self.pos, self.end)
        s = self.d[self.pos:i]
        self.pos = i + 1
        return s

    # -- values ----------------------------------------------------------
    def value(self):
        c = self.u8()
        v = self._value(c)
        if c != TAG_PREVIOUS:
            self.last = v
        return v

    def _value(self, c):
        if c == TAG_PREVIOUS:
            return self.last
        if c == TAG_NONE:
            return None
        if c == TAG_TRUE:
            return True
        if c == TAG_FALSE:
            return False
        if c == TAG_TUPLE or c == TAG_LIST or c == TAG_SET or c == TAG_FROZENSET:
            n = self.varint()
            items = tuple(self.value() for _ in range(n))
            return items
        if c == TAG_DICT or c == TAG_FROZENDICT:
            n = self.varint()
            keys = [self.value() for _ in range(n)]
            vals = [self.value() for _ in range(n)]
            return dict(zip(keys, vals))
        if c == TAG_LONG_POS_SMALL:
            return self.varint()
        if c == TAG_LONG_NEG_SMALL:
            return -self.varint()
        if c in (TAG_LONG_POS_LARGE, TAG_LONG_NEG_LARGE):
            n = self.varint()
            result = 0
            for _ in range(n):
                result = (result << 31) + self.varint()
            return -result if c == TAG_LONG_NEG_LARGE else result
        if c == TAG_INT_POSITIVE:
            return self.varint()
        if c == TAG_INT_NEGATIVE:
            return -self.varint()
        if c == TAG_FLOAT:
            return self.f64()
        if c == TAG_FLOAT_SPECIAL:
            return FLOAT_SPECIALS[self.u8()]
        if c == TAG_COMPLEX:
            return complex(self.f64(), self.f64())
        if c == TAG_COMPLEX_SPECIAL:
            return complex(self.value(), self.value())
        if c == TAG_TEXT_EMPTY:
            return ""
        if c == TAG_TEXT_SINGLE:
            s = self.d[self.pos:self.pos + 1]
            self.pos += 1
            return s.decode("utf-8", "replace")
        if c == TAG_TEXT_UTF8_LEN:
            n = self.varint()
            s = self.d[self.pos:self.pos + n]
            self.pos += n
            return s.decode("utf-8", "surrogatepass")
        if c == TAG_TEXT_UTF8_Z or c == TAG_ATTRIBUTE_NAME:
            return self.cstring().decode("utf-8", "surrogatepass")
        if c == TAG_BYTES_LEN:
            n = self.varint()
            s = self.d[self.pos:self.pos + n]
            self.pos += n
            return s
        if c == TAG_BYTES_Z:
            return self.cstring()
        if c == TAG_BYTES_SINGLE:
            s = self.d[self.pos:self.pos + 1]
            self.pos += 1
            return s
        if c == TAG_BYTEARRAY:
            n = self.varint()
            s = self.d[self.pos:self.pos + n]
            self.pos += n
            return bytearray(s)
        if c == TAG_SLICE:
            return slice(self.value(), self.value(), self.value())
        if c == TAG_RANGE:
            return range(self.value(), self.value(), self.value())
        if c == TAG_BUILTIN_ANON:
            return f"<type {ANON_NAMES.get(self.u8(), '?')}>"
        if c == TAG_BUILTIN_SPECIAL:
            return f"<{SPECIAL_NAMES.get(self.u8(), '?')}>"
        if c == TAG_BUILTIN_NAMED or c == TAG_BUILTIN_EXCEPTION:
            return f"<builtin {self.cstring().decode()}>"
        if c == TAG_BLOB_DATA:
            n = self.varint()
            s = self.d[self.pos:self.pos + n]
            self.pos += n
            return s
        if c == TAG_GENERIC_ALIAS:
            return (self.value(), self.value())
        if c == TAG_UNION_TYPE:
            return ("union", self.value())
        if c in (TAG_CODE_OBJECT, TAG_MODULE_CODE, TAG_CLASS_CODE, TAG_GENEXPR_CODE):
            return self.code_object(c)
        raise ValueError(f"unknown tag {c!r} ({c}) at {self.pos - 1:#x}")

    def _advance(self, n):
        self.pos += n
        return False
    def code_object(self, c):
        is_module = c == TAG_MODULE_CODE
        is_class = c == TAG_CLASS_CODE
        is_genexpr = c == TAG_GENEXPR_CODE
        flags = self.varint()
        if is_module:
            name, line, arg_names, arg_count = "<module>", 1, (), 0
        else:
            name = "<genexpr>" if is_genexpr else self.value()
            line = self.varint() + 1
            arg_names = self.value()
            if is_class:
                arg_count = 0
            elif is_genexpr:
                arg_count = 1
            else:
                arg_count = self.varint()
        qualname = name
        if flags & CODE_FLAG_QUALNAME:
            qualname = self.value()
        if flags & CODE_FLAG_FREE_VARS:
            self.value()
        kw_only = pos_only = 0
        if flags & CODE_FLAG_KW_ONLY:
            kw_only = self.varint() + 1
        if flags & CODE_FLAG_POS_ONLY:
            pos_only = self.varint() + 1
        co = CodeObject(name, qualname, line, arg_names, arg_count, flags)
        co.kw_only, co.pos_only = kw_only, pos_only
        co.is_class, co.is_module = is_class, is_module
        return co


def find_directory(blob, name_re):
    """Return {(name, data_off, size)} for every module blob entry.

    The directory is split over several regions; walking from each candidate
    offset yields the same aligned entries, so entries seen at least twice are
    the real ones (a mis-aligned first entry is only seen once).
    """
    walks = []
    for m in name_re.finditer(blob):
        pos = m.start()
        entries = []
        while True:
            mm = name_re.match(blob, pos)
            if not mm:
                break
            name = mm.group()[:-1]
            end = mm.end()
            if end + 4 > len(blob):
                break
            size = struct.unpack_from("<I", blob, end)[0]
            if size == 0 or end + 4 + size > len(blob):
                break
            entries.append((name.decode(), end + 4, size))
            pos = end + 4 + size
        if len(entries) >= 8:
            walks.append(entries)

    counts = {}
    for entries in walks:
        for name, off, size in entries:
            counts[(name, off, size)] = counts.get((name, off, size), 0) + 1
    return sorted(set(k for k, n in counts.items() if n >= 2), key=lambda k: k[1]), len(walks)


def walk_values(blob, start, end):
    b = Blob(blob, start, end)
    count = b.u16()
    out = []
    for _ in range(count):
        out.append(b.value())
    return out, b.pos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dll")
    ap.add_argument("--json", default=None, help="write the full structure here")
    ap.add_argument("--dump-strings", default=None)
    args = ap.parse_args()

    data = open(args.dll, "rb").read()
    name_re = re.compile(rb"[A-Za-z_][A-Za-z0-9_.]{0,60}\x00")

    # Restrict the scan to .rdata (where the constant blob is linked in).
    base = 0
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsize = struct.unpack_from("<H", data, pe + 20)[0]
    sec = pe + 24 + optsize
    span = data
    for i in range(nsec):
        o = sec + i * 40
        sname = data[o:o + 8].rstrip(b"\0").decode(errors="replace")
        if sname == ".rdata":
            vsize, vaddr, size, raw = struct.unpack_from("<IIII", data, o + 8)
            base, span = raw, data[raw:raw + size]
            print(f"# scanning .rdata raw={base:#x} size={size:#x}", file=sys.stderr)
            break

    entries, nwalks = find_directory(span, name_re)
    entries = [(n, o + base, s) for n, o, s in entries]
    print(f"# discovered {len(entries)} module blobs from {nwalks} walks", file=sys.stderr)

    modules = {}
    for name, off, size in entries:
        end = off + size
        try:
            values, used = walk_values(data, off, end)
        except Exception as exc:  # noqa: BLE001
            print(f"!! {name}: {exc}", file=sys.stderr)
            continue
        modules[name] = {"values": values, "used": used, "end": end,
                         "size": size, "clean": used == end}

    clean = sum(1 for m in modules.values() if m["clean"])
    print(f"# decoded {len(modules)} modules, {clean} ended exactly at their blob end",
          file=sys.stderr)

    if args.json:
        def jsonable(o):
            if isinstance(o, CodeObject):
                return {"__code__": o.kind, "name": o.name, "qualname": o.qualname,
                        "line": o.line,
                        "args": jsonable(o.arg_names),
                        "arg_count": o.arg_count, "flags": o.flags,
                        "kw_only": o.kw_only, "pos_only": o.pos_only,
                        "class": o.is_class, "module": o.is_module}
            if isinstance(o, bytes):
                return {"__bytes__": o[:4096].decode("utf-8", "replace"), "len": len(o)}
            if isinstance(o, bytearray):
                return {"__bytearray__": bytes(o[:4096]).decode("utf-8", "replace"), "len": len(o)}
            if isinstance(o, dict):
                return {str(k): jsonable(v) for k, v in o.items()}
            if isinstance(o, (tuple, list, set, frozenset)):
                return [jsonable(v) for v in o]
            if isinstance(o, (slice, range)):
                return repr(o)
            if isinstance(o, (str, int, float, bool)) or o is None:
                return o
            return repr(o)

        with open(args.json, "w") as fh:
            json.dump({k: jsonable(v["values"]) for k, v in modules.items()}, fh, indent=1)
        print(f"# wrote {args.json}", file=sys.stderr)

    if args.dump_strings:
        seen = set()
        with open(args.dump_strings, "w") as fh:
            def rec(module, v):
                if isinstance(v, CodeObject):
                    fh.write(f"### [{module}] {v.kind} {v.qualname} : line {v.line} args={v.arg_names} "
                             f"kw_only={v.kw_only} pos_only={v.pos_only} flags={v.flags:#x}\n")
                    return
                if isinstance(v, str):
                    key = (module, v)
                    if key not in seen and v:
                        seen.add(key)
                        fh.write(f"[{module}] {v}\n")
                    return
                if isinstance(v, dict):
                    for kk, vv in v.items():
                        rec(module, kk)
                        rec(module, vv)
                    return
                if isinstance(v, (tuple, list, set, frozenset)):
                    for i in v:
                        rec(module, i)
                    return
            for mod, info in modules.items():
                for v in info["values"]:
                    rec(mod, v)
        print(f"# wrote {args.dump_strings}", file=sys.stderr)


if __name__ == "__main__":
    main()
