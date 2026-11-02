// Ours (Meridian 59 Prime): the Items, Creatures and Character pages of the in-game admin console (AdminConsole.tsx). Their lists come from the
// running server (primeadmin.kod): every item, every creature, every spell and skill, and the abilities of one character. A line "padmin ..." goes to
// the server, which answers with the lists and the character, and only an Admin character is obeyed. The target is the player picked on the Players
// tab, else ourselves.

import { useEffect, useMemo, useState } from "react";
import type { GameSession } from "@shards/world";
import { Button, ListBox, Text, TextField } from "./kit.tsx";
import { usePrimeGroup } from "../primeGroup.ts";

const SCHOOLS = ["", "Shal'ille", "Qor", "Kraanan", "Faren", "Riija", "Jala", "Crafting"];
const CLASSES = ["no class", "Warrior", "Monk", "Paladin", "Elementalist", "Priest"];

export type PrimeAdminTab = "Items" | "Creatures" | "Character";

/** Entries (name and place in the server's list) matching what was typed, in alphabetical order */
function filtered(names: readonly string[], typed: string): { key: number; label: string }[] {
  const t = typed.trim().toLowerCase();
  const out: { key: number; label: string }[] = [];
  names.forEach((n, i) => {
    if (!t || n.toLowerCase().includes(t)) out.push({ key: i, label: n });
  });
  return out.sort((a, b) => a.label.localeCompare(b.label));
}

export function PrimeAdminPage({
  tab, session, me, targetId, targetName, y, setStatus, onDm,
}: {
  /** A DM command ("dm ..."), for the disguise */
  onDm: (text: string) => void;
  tab: PrimeAdminTab;
  session: GameSession;
  /** Our own object */
  me: number;
  /** The player picked on the Players tab, or null */
  targetId: number | null;
  targetName: string | undefined;
  /** Where the page starts (dialog units) */
  y: number;
  setStatus: (s: string) => void;
}) {
  const store = usePrimeGroup();
  const [find, setFind] = useState("");
  const [picked, setPicked] = useState<number | string | null>(null);
  const [count, setCount] = useState("1");
  const [gold, setGold] = useState("5000");
  const [hp, setHp] = useState("100");
  const [percent, setPercent] = useState("1");
  const [showAll, setShowAll] = useState(false);

  const other = targetId !== null && targetId !== me && targetName ? targetName : undefined;
  const to = other ? ` to ${other}` : "";
  const say = (line: string) => session.shardsCommand(line);

  // the lists, once per window; the character again whenever the target changes
  useEffect(() => {
    if (tab === "Items" && store.adminItems.length === 0) say("padmin list items");
    if (tab === "Creatures" && store.adminMonsters.length === 0) say("padmin list monsters");
    if (tab === "Character") {
      if (store.adminAbilities.length === 0) say("padmin list abilities");
      say(`padmin char${to}`);
    }
    setPicked(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, other]);

  const items = useMemo(() => filtered(store.adminItems, find), [store.adminItems, find]);
  const monsters = useMemo(() => filtered(store.adminMonsters, find), [store.adminMonsters, find]);

  const known = store.adminKnown;
  const knownKeys = useMemo(() => new Set(known.map((k) => `${k.kind}:${k.num}`)), [known]);
  const abilityRows = useMemo(() => {
    const t = find.trim().toLowerCase();
    if (!showAll) {
      return known
        .filter((k) => !t || k.name.toLowerCase().includes(t))
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((k) => ({ key: `${k.kind}:${k.num}`, label: `${k.name}  ${k.percent}%` }));
    }
    return store.adminAbilities
      .filter((a) => !t || a.name.toLowerCase().includes(t))
      .sort((a, b) => a.school - b.school || a.level - b.level || a.name.localeCompare(b.name))
      .map((a) => ({
        key: `${a.kind}:${a.num}`,
        label: `${a.name}  (${a.kind === 1 ? "skill" : `${SCHOOLS[a.school] ?? ""} ${a.level}`})${knownKeys.has(`${a.kind}:${a.num}`) ? "  - known" : ""}`,
      }));
  }, [showAll, known, store.adminAbilities, find, knownKeys]);

  const num = (s: string) => {
    const n = Number.parseInt(s, 10);
    return Number.isFinite(n) ? n : NaN;
  };

  const findBox = (
    <>
      <Text at={[3, y + 2, 20, 8]}>Find:</Text>
      <TextField at={[24, y, 140, 13]} value={find} maxLength={40} onChange={(v) => { setFind(v); setPicked(null); }} />
    </>
  );

  if (tab === "Items") {
    const give = (toOther: boolean) => {
      if (typeof picked !== "number") return setStatus("Pick an item first.");
      say(`padmin give item ${picked}${toOther ? to : ""}`);
      setStatus(toOther ? `Gave to ${other}.` : "Gave to you.");
    };
    const giveGold = (toOther: boolean) => {
      const n = num(gold);
      if (!(n > 0)) return setStatus("Type an amount of shillings.");
      say(`padmin give gold ${n}${toOther ? to : ""}`);
      setStatus(toOther ? `Gave shillings to ${other}.` : "Gave shillings to you.");
    };
    return (
      <>
        {findBox}
        <Text at={[170, y + 2, 168, 8]}>{store.adminItems.length ? `${items.length} of ${store.adminItems.length} items` : "Asking the server for the items..."}</Text>
        <ListBox at={[1, y + 16, 337, 100]} label="Items" items={items} selected={typeof picked === "number" ? picked : null} onSelect={setPicked} />
        <Button at={[1, y + 120, 64, 11]} onClick={() => give(false)}>
          Give to me
        </Button>
        <Button at={[69, y + 120, 130, 11]} disabled={!other} onClick={() => give(true)}>
          {other ? `Give to ${other}` : "Give to the picked player"}
        </Button>
        <Text at={[1, y + 140, 40, 8]}>Shillings:</Text>
        <TextField at={[42, y + 137, 56, 13]} value={gold} maxLength={9} onChange={setGold} />
        <Button at={[102, y + 138, 40, 11]} onClick={() => giveGold(false)}>
          To me
        </Button>
        <Button at={[146, y + 138, 100, 11]} disabled={!other} onClick={() => giveGold(true)}>
          {other ? `To ${other}` : "To the picked player"}
        </Button>
        <Text at={[1, y + 156, 337, 8]}>{other ? `Players tab pick: ${other}` : "No player picked on the Players tab: gives go to you."}</Text>
      </>
    );
  }

  if (tab === "Creatures") {
    const spawn = () => {
      if (typeof picked !== "number") return setStatus("Pick a creature first.");
      const n = num(count);
      say(`padmin spawn ${picked} ${n > 0 ? Math.min(n, 20) : 1}`);
    };
    const disguise = () => {
      if (typeof picked !== "number") return setStatus("Pick a creature first.");
      onDm(`disguise ${store.adminMonsters[picked]}`);
    };
    return (
      <>
        {findBox}
        <Text at={[170, y + 2, 168, 8]}>{store.adminMonsters.length ? `${monsters.length} of ${store.adminMonsters.length} creatures` : "Asking the server for the creatures..."}</Text>
        <ListBox at={[1, y + 16, 337, 118]} label="Creatures" items={monsters} selected={typeof picked === "number" ? picked : null} onSelect={setPicked} onActivate={spawn} />
        <Text at={[1, y + 140, 40, 8]}>How many:</Text>
        <TextField at={[44, y + 137, 30, 13]} value={count} maxLength={2} onChange={setCount} />
        <Button at={[80, y + 138, 70, 11]} onClick={spawn}>
          Spawn here
        </Button>
        <Button at={[154, y + 138, 70, 11]} onClick={disguise} title="Look like the picked creature (Plain on the Self tab undoes it)">
          Disguise as
        </Button>
        <Text at={[230, y + 140, 108, 8]}>Spawn: up to 20 at a time</Text>
      </>
    );
  }

  // Character
  const c = store.adminChar;
  const sel = typeof picked === "string" ? picked : null;
  const [selKind, selNum] = sel ? sel.split(":").map(Number) : [0, 0];
  const setAbility = () => {
    const p = num(percent);
    if (!sel) return setStatus("Pick an ability first.");
    if (!(p >= 1 && p <= 99)) return setStatus("Percent: 1 to 99.");
    say(`padmin ability set ${selKind} ${selNum} ${p}${to}`);
  };
  const removeAbility = () => {
    if (!sel) return setStatus("Pick an ability first.");
    say(`padmin ability remove ${selKind} ${selNum}${to}`);
  };
  const setHealth = () => {
    const n = num(hp);
    if (!(n >= 20)) return setStatus("Base health: 20 or more.");
    say(`padmin hp ${n}${to}`);
  };
  return (
    <>
      <Text at={[3, y + 1, 334, 8]}>
        {c ? `${c.name}${c.id === me ? " (you)" : ""}, ${CLASSES[c.cls] ?? "class " + c.cls}: base health ${c.baseHp}, health now ${c.hp}` : "Asking the server..."}
      </Text>
      <Text at={[3, y + 14, 48, 8]}>Base health:</Text>
      <TextField at={[52, y + 11, 36, 13]} value={hp} maxLength={4} onChange={setHp} />
      <Button at={[92, y + 12, 30, 11]} onClick={setHealth}>
        Set
      </Button>
      <Button at={[126, y + 12, 40, 11]} onClick={() => say(`padmin char${to}`)}>
        Reload
      </Button>
      <Text at={[1, y + 156, 337, 8]}>{other ? `For ${other} (picked on the Players tab). Base health tops out at 100 + stamina.` : "For yourself (pick a player on the Players tab for someone else). Base health tops out at 100 + stamina."}</Text>
      <Button at={[170, y + 12, 110, 11]} onClick={() => { setShowAll(!showAll); setPicked(null); }}>
        {showAll ? "Showing every ability" : "Showing what they know"}
      </Button>
      <Text at={[3, y + 30, 20, 8]}>Find:</Text>
      <TextField at={[24, y + 27, 140, 13]} value={find} maxLength={40} onChange={(v) => { setFind(v); setPicked(null); }} />
      <Text at={[170, y + 30, 168, 8]}>{showAll ? `${abilityRows.length} abilities` : `${abilityRows.length} known`}</Text>
      <ListBox at={[1, y + 43, 337, 92]} label="Abilities" items={abilityRows} selected={sel} onSelect={setPicked} />
      <Text at={[1, y + 142, 36, 8]}>Percent:</Text>
      <TextField at={[38, y + 139, 28, 13]} value={percent} maxLength={2} onChange={setPercent} />
      <Button at={[70, y + 140, 70, 11]} onClick={setAbility}>
        {showAll ? "Add / set" : "Set"}
      </Button>
      <Button at={[144, y + 140, 70, 11]} onClick={removeAbility}>
        Remove
      </Button>
    </>
  );
}
