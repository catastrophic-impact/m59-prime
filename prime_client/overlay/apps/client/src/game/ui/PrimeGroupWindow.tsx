// Ours (Meridian 59 Prime): the group window, on the left under our portrait: you, your groupmates and each one's companion, with
// health and mana; click a row to target them (when they are here), Invite your target, Leave, an invitation to accept; for your
// own companion, its stance. Looks like the rest of the game's stone and gold. The server is prime_server's primegroups.kod.

import { useState } from "react";
import { COMPANION_STANCES, GRP, type GroupMember } from "@shards/world";
import { primeGroup, usePrimeGroup } from "../primeGroup.ts";
import "./primeGroup.css";

const pct = (v: number, max: number) => (max > 0 ? Math.max(0, Math.min(100, Math.round((100 * v) / max))) : 0);

export function PrimeGroupWindow({
  command,
  target,
  targetName,
  onSelect,
  inRoom,
  onAttack,
}: {
  /** Send our companions at the selected target (or the next object clicked) */
  onAttack: () => void;
  /** A `group ...` or `companion ...` command line (UC_SHARDS) */
  command: (line: string) => void;
  /** The object we have targeted, and its name when it is a player */
  target: number | null;
  targetName: string | null;
  onSelect: (id: number) => void;
  /** Is this object in our room (can it be targeted)? */
  inRoom: (id: number) => boolean;
}) {
  const store = usePrimeGroup();
  const [open, setOpen] = useState(true);
  const g = store.state;
  const invite = store.invite;
  if (!g && !invite) return null;

  const row = (m: GroupMember) => {
    const here = !(m.flags & GRP.OFF_ROOM) && inRoom(m.id);
    const cls = ["pg-row", m.flags & GRP.COMPANION ? "comp" : "", m.flags & GRP.DEAD ? "dead" : "", here ? "" : "away", m.id === target ? "target" : ""].join(" ");
    return (
      <div key={`${m.id}-${m.name}`} className={cls} onClick={() => here && onSelect(m.id)} title={here ? "Target" : "Not here"}>
        <div className="pg-name">
          {m.flags & GRP.LEADER ? <b className="pg-star" title="Leader">★</b> : null}
          {m.flags & GRP.COMPANION ? <span className="pg-tag" title="Companion">⚔</span> : null}
          {m.name}
        </div>
        <i className="pg-bar pg-hp" style={{ ["--pct" as string]: `${pct(m.hp, m.maxHp)}%` }} title={`Health ${m.hp} / ${m.maxHp}`} />
        {m.maxMana > 0 ? <i className="pg-bar pg-mana" style={{ ["--pct" as string]: `${pct(m.mana, m.maxMana)}%` }} title={`Mana ${m.mana} / ${m.maxMana}`} /> : null}
      </div>
    );
  };

  // our own companion's row comes right after ours
  const ownCompanion = !!g && !!g.members[1] && !!(g.members[1].flags & GRP.COMPANION);
  return (
    <div className="pg-window" role="group" aria-label="Group">
      <div className="pg-title" onClick={() => setOpen(!open)}>
        <span>{g?.inGroup ? "Group" : "Party"}</span>
        <span className="pg-fold">{open ? "▾" : "▸"}</span>
      </div>
      {invite && (
        <div className="pg-invite">
          <span>{invite} invites you to a group.</span>
          <div className="pg-buttons">
            <button type="button" onClick={() => { command("group accept"); primeGroup.answered(); }}>Accept</button>
            <button type="button" onClick={() => { command("group decline"); primeGroup.answered(); }}>Decline</button>
          </div>
        </div>
      )}
      {open && g && (
        <>
          <div className="pg-rows">{g.members.map(row)}</div>
          <div className="pg-buttons">
            <button type="button" disabled={!targetName || (g.inGroup && !g.leader)} onClick={() => targetName && command(`group invite ${targetName}`)} title={targetName ? `Invite ${targetName}` : "Target a player to invite them"}>
              Invite
            </button>
            {g.inGroup && (
              <button type="button" onClick={() => command("group leave")}>
                Leave
              </button>
            )}
          </div>
          {ownCompanion && (
            <div className="pg-buttons pg-stances" title="Your companion's stance">
              {COMPANION_STANCES.map((st) => (
                <button key={st.id} type="button" onClick={() => command(`companion ${st.word}`)}>
                  {st.label}
                </button>
              ))}
              <button type="button" onClick={onAttack} title="Your companions attack your target (also a hotbar slot: right-click a slot, Companions)">
                Attack
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
