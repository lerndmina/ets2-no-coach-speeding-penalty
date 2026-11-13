"""Minimal read-only reader for SCS HashFS v2 archives (.scs).

Usage:
  hashfs.py ARCHIVE info
  hashfs.py ARCHIVE ls [DIR]            list a directory ("" = root)
  hashfs.py ARCHIVE tree                list every reachable path
  hashfs.py ARCHIVE cat PATH            dump one file to stdout
  hashfs.py ARCHIVE extract PATH... -o OUTDIR
"""
import struct, sys, zlib, os

M = (1 << 64) - 1
K0, K1, K2, K3 = 0xc3a5c85c97cb3127, 0xb492b66fbe98f273, 0x9ae16a3b2f90404f, 0xc949d7c7509e6557
KMUL = 0x9ddfea08eb382d69

def f64(s, i): return struct.unpack_from("<Q", s, i)[0]
def f32(s, i): return struct.unpack_from("<I", s, i)[0]
def rot(v, n): return v if n == 0 else ((v >> n) | (v << (64 - n))) & M
def smix(v): return v ^ (v >> 47)

# CityHash64 v1.0.x (what SCS HashFS uses; differs from 1.1 for every length)
def h16(u, v):
    a = ((u ^ v) * KMUL) & M; a ^= a >> 47
    b = ((v ^ a) * KMUL) & M; b ^= b >> 47
    return (b * KMUL) & M

def h0to16(s, n):
    if n > 8:
        a = f64(s, 0); b = f64(s, n - 8)
        return h16(a, rot((b + n) & M, n)) ^ b
    if n >= 4:
        return h16((n + (f32(s, 0) << 3)) & M, f32(s, n - 4))
    if n > 0:
        y = (s[0] + (s[n >> 1] << 8)) & 0xFFFFFFFF
        z = (n + (s[n - 1] << 2)) & 0xFFFFFFFF
        return (smix(((y * K2) ^ (z * K3)) & M) * K2) & M
    return K2

def h17to32(s, n):
    a = (f64(s, 0) * K1) & M; b = f64(s, 8)
    c = (f64(s, n - 8) * K2) & M; d = (f64(s, n - 16) * K0) & M
    return h16((rot((a - b) & M, 43) + rot(c, 30) + d) & M,
               (a + rot(b ^ K3, 20) - c + n) & M)

def h33to64(s, n):
    z = f64(s, 24)
    a = (f64(s, 0) + (n + f64(s, n - 16)) * K0) & M
    b = rot((a + z) & M, 52); c = rot(a, 37)
    a = (a + f64(s, 8)) & M; c = (c + rot(a, 7)) & M
    a = (a + f64(s, 16)) & M
    vf = (a + z) & M; vs = (b + rot(a, 31) + c) & M
    a = (f64(s, 16) + f64(s, n - 32)) & M; z = f64(s, n - 8)
    b = rot((a + z) & M, 52); c = rot(a, 37)
    a = (a + f64(s, n - 24)) & M; c = (c + rot(a, 7)) & M
    a = (a + f64(s, n - 16)) & M
    wf = (a + z) & M; ws = (b + rot(a, 31) + c) & M
    r = smix(((vf + ws) * K2 + (wf + vs) * K0) & M)
    return (smix((r * K0 + vs) & M) * K2) & M

def weak(s, i, a, b):
    w, x, y, z = f64(s, i), f64(s, i + 8), f64(s, i + 16), f64(s, i + 24)
    a = (a + w) & M; b = rot((b + a + z) & M, 21); c = a
    a = (a + x + y) & M; b = (b + rot(a, 44)) & M
    return ((a + z) & M, (b + c) & M)

def city64(s):
    n = len(s)
    if n <= 16: return h0to16(s, n)
    if n <= 32: return h17to32(s, n)
    if n <= 64: return h33to64(s, n)
    x = f64(s, 0); y = f64(s, n - 16) ^ K1; z = f64(s, n - 56) ^ K0
    v = weak(s, n - 64, n, y); w = weak(s, n - 32, (n * K1) & M, K0)
    z = (z + smix(v[1]) * K1) & M
    x = (rot((z + x) & M, 39) * K1) & M
    y = (rot(y, 33) * K1) & M
    left = (n - 1) & ~63; i = 0
    while True:
        x = (rot((x + y + v[0] + f64(s, i + 16)) & M, 37) * K1) & M
        y = (rot((y + v[1] + f64(s, i + 48)) & M, 42) * K1) & M
        x ^= w[1]; y ^= v[0]
        z = rot(z ^ w[0], 33)
        v = weak(s, i, (v[1] * K1) & M, (x + w[0]) & M)
        w = weak(s, i + 32, (z + w[1]) & M, y)
        z, x = x, z
        i += 64; left -= 64
        if left == 0: break
    return h16((h16(v[0], w[0]) + smix(y) * K1 + z) & M, (h16(v[1], w[1]) + x) & M)


class HashFS:
    def __init__(self, path):
        self.f = open(path, "rb")
        hdr = self.f.read(64)
        magic, ver, self.salt, method, ecount, esize, mcount, msize, estart, mstart = \
            struct.unpack_from("<IHH4sIIIIQQ", hdr, 0)
        if magic != 0x23534353 or ver != 2 or method != b"CITY":
            raise SystemExit(f"unsupported archive: magic={magic:x} ver={ver} method={method}")
        self.f.seek(estart); et = zlib.decompress(self.f.read(esize))
        self.f.seek(mstart); self.meta = zlib.decompress(self.f.read(msize))
        self.entries = {}
        for i in range(ecount):
            h, midx, mcnt, flags = struct.unpack_from("<QIHH", et, i * 16)
            self.entries[h] = (midx, mcnt, flags)
        self.info = dict(entries=ecount, meta_words=mcount, salt=self.salt)

    def hash(self, path):
        p = path.strip("/").lower().encode()
        if self.salt:
            p = str(self.salt).encode() + p
        return city64(p)

    def _main(self, h):
        midx, mcnt, flags = self.entries[h]
        for k in range(mcnt):
            word = f32(self.meta, (midx + k) * 4)
            idx, typ = word & 0xFFFFFF, word >> 24
            if typ in (0x80, 0x81):  # plain file / directory
                o = idx * 4
                csz_raw, size, _unk, block = struct.unpack_from("<IIII", self.meta, o)
                return dict(type=typ, csize=csz_raw & 0x0FFFFFFF, comp=csz_raw >> 28,
                            size=size & 0x0FFFFFFF, offset=block * 16)
        raise KeyError(f"no plain/dir metadata for {h:016x} (types not supported)")

    def read_hash(self, h):
        m = self._main(h)
        self.f.seek(m["offset"]); data = self.f.read(m["csize"])
        if m["comp"] == 1:
            data = zlib.decompress(data)
        elif m["comp"] != 0:
            raise ValueError(f"unsupported compression {m['comp']}")
        return m["type"], data

    def read(self, path):
        return self.read_hash(self.hash(path))[1]

    def listdir(self, path):
        typ, data = self.read_hash(self.hash(path))
        if typ != 0x81:
            raise NotADirectoryError(path)
        n = f32(data, 0); lens = data[4:4 + n]; pos = 4 + n; names = []
        for L in lens:
            names.append(data[pos:pos + L].decode("utf-8", "replace")); pos += L
        return names

    def walk(self, path=""):
        for name in self.listdir(path):
            if name.startswith("/"):
                sub = (path + name) if path else name[1:]
                if self.hash(sub) not in self.entries:
                    print(f"UNRESOLVED_DIR {sub} (len {len(sub)})", file=sys.stderr); continue
                yield from self.walk(sub)
            else:
                yield f"{path}/{name}" if path else name

def main():
    fs = HashFS(sys.argv[1]); cmd = sys.argv[2]
    if cmd == "info":
        print(fs.info, "root_present=", fs.hash("") in fs.entries)
    elif cmd == "ls":
        print("\n".join(fs.listdir(sys.argv[3] if len(sys.argv) > 3 else "")))
    elif cmd == "tree":
        for p in fs.walk(): print(p)
    elif cmd == "cat":
        sys.stdout.buffer.write(fs.read(sys.argv[3]))
    elif cmd == "extract":
        args = sys.argv[3:]; out = args[args.index("-o") + 1]; paths = args[:args.index("-o")]
        for p in paths:
            dst = os.path.join(out, p); os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as g: g.write(fs.read(p))
            print(dst)

if __name__ == "__main__":
    main()
