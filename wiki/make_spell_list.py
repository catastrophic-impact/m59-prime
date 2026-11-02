import re,os,sys
root=os.path.join(os.environ.get("PRIME_WORK", os.path.expanduser("~/boxes/m59-box/src/prime_work")), "build/tree/kod")
khd=open(root+"/include/blakston.khd").read()
schools={int(n):k for k,n in re.findall(r"^\s*SS_(\w+)\s*=\s*(\d+)",khd,re.M)}
classes={}
for d,_,fs in os.walk(root+"/object/passive/spell"):
    for f in fs:
        if not f.endswith(".kod"): continue
        t=open(os.path.join(d,f),errors="replace").read()
        m=re.search(r"^(\w+)\s+is\s+(\w+)\s*$",t,re.M)
        if not m: continue
        cv=re.search(r"^classvars:(.*?)^properties:",t,re.M|re.S)
        cv=cv.group(1) if cv else ""
        def g(k):
            x=re.search(r"\b"+k+r"\s*=\s*([^\s/]+)",cv); return x.group(1) if x else None
        rs={}
        rp=os.path.join(d,f)
        if os.path.exists(rp):
            rt=open(rp,errors="replace").read()
            rt=rt.split("classvars:")[0]
            for k,body in re.findall(r"^\s*(\w+)\s*=\s*((?:\\?\s*\n?\s*\"[^\"]*\"\s*)+)",rt,re.M):
                rs[k]=" ".join(re.findall(r'"([^"]*)"',body))
        classes[m.group(1)]=dict(parent=m.group(2),school=g("viSchool"),level=g("viSpell_level"),num=g("viSpell_num"),mana=g("viMana"),name=g("vrName"),rs=rs,file=f,desc=g("vrDesc"))
def res(c,k):
    while c:
        x=classes.get(c)
        if not x: return None
        if k in x: return x[k]
        c=x["parent"]
def inh(c,k):
    while c in classes:
        if classes[c][k] is not None: return classes[c][k]
        c=classes[c]["parent"]
out={}
for c,x in classes.items():
    num=x["num"]
    if not num or not num.startswith("SID_"): continue
    sch=inh(c,"school"); lvl=inh(c,"level"); mana=inh(c,"mana"); nm=x["name"]
    name=x["rs"].get(nm) if nm else None
    name=name.title() if name else re.sub(r"(?<=[a-z])(?=[A-Z])"," ",c)
    s=sch
    if s and s.startswith("SS_"): s=s[3:]
    elif s and s.lstrip("-").isdigit(): s=schools.get(int(s),s)
    desc=x["rs"].get(x["desc"]) if x["desc"] else ""
    out.setdefault(s or "NO SCHOOL",[]).append((int(lvl) if lvl and lvl.isdigit() else 99,name,mana,num,desc))
order=["SHALILLE","QOR","KRAANAN","FAREN","RIIJA","JALA","CRAFTING"]
names={"SHALILLE":"Shal'ille (holy)","QOR":"Qor (dark)","KRAANAN":"Kraanan (warrior / battle)","FAREN":"Faren (nature)","RIIJA":"Riija (illusion / mind)","JALA":"Jala (bard / song)","CRAFTING":"Crafting (removed)"}
L=["MERIDIAN 59 PRIME - SPELLS BY SCHOOL AND LEVEL","=================================================",
"Generated from the server code (kod) on 2026-10-22. Edit freely: this is a working list.","Format: Name (mana cost, internal id). Levels 1-6 per school (7+ / 99 = no level / special).","Prime classes: Warrior learns Create Weapon, Magic Shield, Resist Magic, Bless; Priest learns Shal'ille spells (see class tables in primeclasses.kod).","Each entry: name, mana cost, and the first lines of the in-game description (reagent needs are in the full text in the kod files).",""]
for s in order+[k for k in out if k not in order and k!="DM_COMMAND"]:
    if s not in out: continue
    L.append(names.get(s,s).upper()); L.append("-"*len(L[-1]))
    for lvl in sorted({e[0] for e in out[s]}):
        L.append(("Level %d"%lvl) if lvl<99 else "Level ? (not set)")
        for e in sorted([e for e in out[s] if e[0]==lvl],key=lambda e:e[1].lower()):
            L.append("  - %s  (mana %s)"%(e[1],e[2] or "?"))
            if e[4]:
                d=re.sub(r"\s+"," ",e[4]).strip(); d=re.split(r"(?<=[.!?]) ",d); L.append("      "+" ".join(d[:2])[:240])
        L.append("")
L.append("ADMIN / DM SPELLS (not learnable by players)"); L.append("-"*44)
L.append(", ".join(sorted(e[1] for e in out.get("DM_COMMAND",[]))))
open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"spells_by_school.txt"),"w").write("\n".join(L))
print(sum(len(v) for v in out.values()),"spells"); print({k:len(v) for k,v in out.items()})
