// Ours (Meridian 59 Prime): what our client knows of our group, from UC_PRIME_GROUP (kept from logon, before the game view
// is there to listen). One store for the session; PrimeGroupWindow.tsx shows it.

import { useEffect, useState } from "react";
import type { AdminAbility, AdminChar, AdminKnown, BotsState, GroupEvent, GroupState } from "@shards/world";

class PrimeGroupStore {
  state: GroupState | null = null;
  /** Our companion bots, and the rules for summoning them */
  bots: BotsState | null = null;
  /** The admin tools' lists (every item, every creature, every ability), and the character picked on the Character tab */
  adminItems: string[] = [];
  adminMonsters: string[] = [];
  adminAbilities: AdminAbility[] = [];
  adminChar: AdminChar | null = null;
  adminKnown: AdminKnown[] = [];
  /** Who invited us, until we answer */
  invite: string | null = null;
  /** Health (percent) of the attackable monsters in our room, by object id */
  mobHealth = new Map<number, number>();
  /** Set by the game view: float a number over an object */
  numberHandler: ((id: number, amount: number, heal: boolean) => void) | null = null;
  version = 0;
  private listeners = new Set<() => void>();

  onChange(fn: () => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  handle(e: GroupEvent): void {
    if (e.type === "adminList") {
      // pieces arrive in order; the first one starts the list again
      if (e.list === 3) this.adminAbilities = [...(e.start === 0 ? [] : this.adminAbilities), ...e.abilities];
      else if (e.list === 1) this.adminItems = [...(e.start === 0 ? [] : this.adminItems), ...e.strings];
      else this.adminMonsters = [...(e.start === 0 ? [] : this.adminMonsters), ...e.strings];
    } else if (e.type === "adminChar") {
      this.adminChar = e.char;
      this.adminKnown = [];
    } else if (e.type === "adminKnown") {
      this.adminKnown = [...(e.start === 0 ? [] : this.adminKnown), ...e.known];
    } else if (e.type === "bots") this.bots = e.state;
    else if (e.type === "state") this.state = e.state;
    else if (e.type === "invite") this.invite = e.from;
    else if (e.type === "health") this.mobHealth = new Map(e.mobs);
    else {
      this.numberHandler?.(e.id, e.amount, e.heal);
      return;
    }
    this.version++;
    for (const fn of this.listeners) fn();
  }

  /** On the character list (login, switching character): nothing of the last character's group is ours any more */
  reset(): void {
    this.state = null;
    this.bots = null;
    this.adminChar = null;
    this.adminKnown = [];
    this.invite = null;
    this.mobHealth = new Map();
    this.version++;
    for (const fn of this.listeners) fn();
  }

  answered(): void {
    this.invite = null;
    this.version++;
    for (const fn of this.listeners) fn();
  }
}

export const primeGroup = new PrimeGroupStore();

/** Re-renders on every change */
export function usePrimeGroup(): PrimeGroupStore {
  const [, setV] = useState(0);
  useEffect(() => primeGroup.onChange(() => setV((n) => n + 1)), []);
  return primeGroup;
}

/** The health bar's percent for a monster, player or bot (all: every one; else a damaged one, or the one we have targeted), or undefined for none */
export function primeMobBar(id: number, target: number | null, all = false): number | undefined {
  const pct = primeGroup.mobHealth.get(id);
  return pct !== undefined && (all || pct < 100 || id === target) ? pct : undefined;
}

/** Set by the game view from the server's preferences: "attack innocents" is off (the safety is on) */
export const primeSafety = { on: true };

/**
 * Ours (Meridian 59 Prime): is this object a friend: someone in our group (or their companion), ourselves, or, with the safety
 * on, an innocent player (white name)? A friend is shown green when selected, and is never attacked by a click.
 */
export function primeFriendly(o: { id: number; info: { flags: number; nameColor: number } }, selfId?: number): boolean {
  if (o.id === selfId) return true;
  if (primeGroup.state?.members.some((m) => m.id === o.id)) return true;
  return primeSafety.on && (o.info.flags & 0x4) !== 0 && (o.info.nameColor & 0xffffff) === 0xffffff;
}
