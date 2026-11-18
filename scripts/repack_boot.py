#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Repack an AOSP header-v0/v1/v2 boot.img with a new kernel, keeping everything else."""
import struct, sys, hashlib

def parse(d):
    assert d[:8] == b"ANDROID!", "not an android boot image"
    f = {}
    (f["kernel_size"], f["kernel_addr"], f["ramdisk_size"], f["ramdisk_addr"],
     f["second_size"], f["second_addr"], f["tags_addr"], f["page_size"],
     f["header_version"], f["os_version"]) = struct.unpack_from("<10I", d, 8)
    f["name"] = d[48:64]
    f["cmdline"] = d[64:64+512]
    f["id"] = d[576:608]
    if f["header_version"] >= 1:
        f["extra_cmdline"] = d[608:608+1024]
    if f["header_version"] >= 2:
        f["dtb_size"], f["dtb_addr"] = struct.unpack_from("<II", d, 1648)
    return f

def pad(n, page):
    return (page - (n % page)) % page

def build(orig, kernel, ramdisk=None, second=None):
    f = parse(orig)
    p = f["page_size"]
    rd = ramdisk if ramdisk is not None else orig[p + f["kernel_size"] + pad(f["kernel_size"], p):
                                                     p + f["kernel_size"] + pad(f["kernel_size"], p) + f["ramdisk_size"]]
    sec = second if second is not None else orig[p + f["kernel_size"] + pad(f["kernel_size"], p)
                                                  + f["ramdisk_size"] + pad(f["ramdisk_size"], p):
                                                  p + f["kernel_size"] + pad(f["kernel_size"], p)
                                                  + f["ramdisk_size"] + pad(f["ramdisk_size"], p) + f["second_size"]]
    hdr = bytearray(p)
    hdr[0:8] = b"ANDROID!"
    struct.pack_into("<10I", hdr, 8, len(kernel), f["kernel_addr"], len(rd), f["ramdisk_addr"],
                     len(sec), f["second_addr"], f["tags_addr"], p, f["header_version"], f["os_version"])
    hdr[48:64] = f["name"]
    hdr[64:64+512] = f["cmdline"]
    if f["header_version"] >= 1:
        hdr[608:608+1024] = f["extra_cmdline"]
    if f["header_version"] >= 2:
        struct.pack_into("<II", hdr, 1648, f["dtb_size"], f["dtb_addr"])
    sha = hashlib.sha1()
    for part in (kernel, rd, sec):
        sha.update(part); sha.update(struct.pack("<I", len(part)))
    hdr[576:596] = sha.digest()   # v0 id[] is 32 bytes: SHA1 (20) + zero pad
    out = bytearray(hdr)
    for part in (kernel, rd, sec):
        out += part + b"\0" * pad(len(part), p)
    if f["header_version"] >= 2 and f["dtb_size"]:
        dtb = orig[p + f["kernel_size"] + pad(f["kernel_size"], p) + f["ramdisk_size"] + pad(f["ramdisk_size"], p)
                   + f["second_size"] + pad(f["second_size"], p):
                   p + f["kernel_size"] + pad(f["kernel_size"], p) + f["ramdisk_size"] + pad(f["ramdisk_size"], p)
                   + f["second_size"] + pad(f["second_size"], p) + f["dtb_size"]]
        out += dtb + b"\0" * pad(len(dtb), p)
    return bytes(out), f

if __name__ == "__main__":
    orig = open(sys.argv[1], "rb").read()
    kernel = open(sys.argv[2], "rb").read()
    out, f = build(orig, kernel)
    open(sys.argv[3], "wb").write(out)
    print("page=%d hdr=%d kernel=%d->%d total=%d" % (f["page_size"], f["header_version"], f["kernel_size"], len(kernel), len(out)))
