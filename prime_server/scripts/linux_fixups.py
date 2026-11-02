#!/usr/bin/env python3
"""Linux is case-sensitive, the upstream was built on Windows: make every `include X.lkod` find its file, and rename files whose names break the shell (far'nohl.kod)."""
import os, re, sys
root = sys.argv[1]
# 1. file names with an apostrophe break the makefiles' shell commands
for dp, dn, fn in os.walk(root):
    for f in fn:
        if "'" in f:
            new = f.replace("'", "")
            os.rename(os.path.join(dp, f), os.path.join(dp, new))
            for mk in ("makefile",):
                p = os.path.join(dp, mk)
                if os.path.exists(p):
                    s = open(p).read(); open(p, "w").write(s.replace(f[:-4] + ".bof", new[:-4] + ".bof"))
            print("renamed", os.path.join(dp, f))
# 2. .lkod includes with the wrong case
names = {}
for dp, dn, fn in os.walk(root):
    for f in fn: names.setdefault((dp, f.lower()), f)
n = 0
for dp, dn, fn in os.walk(root):
    for f in fn:
        if not f.endswith(".kod"): continue
        for m in re.finditer(r"include\s+([A-Za-z0-9_\-\.]+\.lkod)", open(os.path.join(dp, f), errors="ignore").read()):
            want = m.group(1)
            if os.path.lexists(os.path.join(dp, want)): continue
            real = names.get((dp, want.lower()))
            if real: os.symlink(real, os.path.join(dp, want)); n += 1
            else: print("MISSING include", dp, f, want)
print("case links:", n)
