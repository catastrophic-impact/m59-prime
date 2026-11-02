// Ours (Meridian 59 Prime): the companion bots section of the Companion window: temporary class companions beside the faction one.
// A list of the bots we have (select one for its numbers, stance and Dismiss), and a list of classes to summon from.
// The server (prime_server primebots.kod) sends the state about every second (UC_PRIME_GROUP kind 5); commands go as `bot ...` lines.

import { useEffect, useState } from "react";
import { Button } from "./kit.tsx";
import { PanelSection } from "./FriendsPanel.tsx";
import { usePrimeGroup } from "../primeGroup.ts";
import type { BotInfo } from "@shards/world";

const CLASSES: readonly { id: string; kind: number; label: string; info: string }[] = [
  { id: "warrior", kind: 4, label: "Warrior", info: "Plate and shield; keeps the monsters on itself." },
  { id: "monk", kind: 5, label: "Monk", info: "Fights with its hands; heals, blesses and shields the group, and focuses to get its mana back." },
  { id: "paladin", kind: 6, label: "Paladin", info: "Fights in front with a spirit sword or hammer (each hit returns mana); heals and buffs the group." },
  { id: "elementalist", kind: 7, label: "Elementalist", info: "Casts fire and ice; the group's mana battery (gives mana to players who run low), heals a little." },
];

const STANCES: readonly { id: string; value: number; label: string }[] = [
  { id: "follow", value: 1, label: "Follow" },
  { id: "defend", value: 2, label: "Defend" },
  { id: "stay", value: 3, label: "Stay" },
  { id: "passive", value: 4, label: "Passive" },
];

const pct = (n: number, max: number) => (max > 0 ? Math.max(0, Math.min(100, Math.round((100 * n) / max))) : 0);

function Bar({ value, max, color }: { value: number; max: number; color: string }) {
  return (
    <span style={{ display: "inline-block", width: 90, height: 8, background: "#333", border: "1px solid #666", verticalAlign: "middle" }}>
      <span style={{ display: "block", width: `${pct(value, max)}%`, height: "100%", background: color }} />
    </span>
  );
}

export function PrimeBots({ command, onLooks }: { command: (line: string) => void; onLooks: (bot: BotInfo, number: number) => void }) {
  const store = usePrimeGroup();
  const state = store.bots;
  const bots = state?.bots ?? [];
  const [picked, setPicked] = useState<number | null>(null);
  const [kind, setKind] = useState<string>("warrior");
  const [, setTick] = useState(0);
  useEffect(() => {
    // the wait before the next summon counts down here
    const t = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const selected = bots.find((b) => b.id === picked) ?? bots[0] ?? null;
  const number = selected ? bots.indexOf(selected) + 1 : 0;
  const wait = state ? Math.max(0, state.wait - Math.floor((Date.now() - state.at) / 1000)) : 0;
  const enabled = state ? state.enabled : true;
  const max = state?.max ?? 4;
  const full = bots.length >= max;

  return (
    <PanelSection title="Companion bots">
      {!enabled ? (
        <p className="panel-note">Companion bots are turned off on this server.</p>
      ) : (
        <>
          <p className="panel-note">
            Temporary class companions: they fight at your side and vanish when you log off or they fall. {bots.length} of {max}.
          </p>
          {bots.length > 0 && (
            <ul className="companion-bots" role="listbox" aria-label="Your bots" style={{ listStyle: "none", padding: 0, margin: "0 0 6px" }}>
              {bots.map((b) => (
                <li
                  key={b.id}
                  role="option"
                  aria-selected={b === selected}
                  onClick={() => setPicked(b.id)}
                  style={{ cursor: "pointer", padding: "2px 4px", background: b === selected ? "rgba(120,160,255,0.25)" : undefined }}
                >
                  {bots.indexOf(b) + 1}. {b.name} <span style={{ opacity: 0.7 }}>({CLASSES.find((c) => c.kind === b.kind)?.label ?? "bot"})</span>
                  {b.away ? <span style={{ opacity: 0.6 }}> away</span> : null} <Bar value={b.hp} max={b.maxHp} color="#c33" />{" "}
                  <Bar value={b.mana} max={b.maxMana} color="#38c" />
                </li>
              ))}
            </ul>
          )}
          {selected && (
            <div className="companion-bot-info">
              <p className="panel-note">
                {selected.name}, {CLASSES.find((c) => c.kind === selected.kind)?.label ?? "bot"}: health {selected.hp}/{selected.maxHp}, mana {selected.mana}/{selected.maxMana}.
              </p>
              <div className="panel-row wrap">
                {STANCES.map((s) => (
                  <Button key={s.id} disabled={selected.stance === s.value} onClick={() => command(`bot stance ${s.id} ${number}`)}>
                    {s.label}
                  </Button>
                ))}
                <Button onClick={() => onLooks(selected, number)}>Appearance…</Button>
                <Button onClick={() => command(`bot dismiss ${number}`)}>Dismiss</Button>
              </div>
            </div>
          )}
          <p className="panel-note">Summon a bot:</p>
          <select className="companion-kinds" size={4} value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Bot class" style={{ width: "100%" }}>
            {CLASSES.map((c) => (
              <option key={c.id} value={c.id} title={c.info}>
                {c.label}
              </option>
            ))}
          </select>
          <p className="panel-note">{CLASSES.find((c) => c.id === kind)?.info}</p>
          <div className="panel-row wrap">
            <Button disabled={full || wait > 0} onClick={() => command(`bot call ${kind}`)}>
              Summon Companion
            </Button>
            {bots.length > 1 && <Button onClick={() => command("bot dismiss all")}>Dismiss all</Button>}
          </div>
          {wait > 0 && <p className="panel-note">You can summon another in {wait} seconds.</p>}
        </>
      )}
    </PanelSection>
  );
}
