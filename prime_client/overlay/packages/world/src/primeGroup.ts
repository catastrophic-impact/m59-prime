// Ours (Meridian 59 Prime): our groups, as our server tells us (UC_PRIME_GROUP, prime_server kod/object/prime/primegroups.kod),
// and the commands we send back (UC_SHARDS "group ...").

import { objId, type ByteReader } from "@shards/protocol";

/** A row's flags (GRP_* in prime.khd) */
export const GRP = { LEADER: 1, COMPANION: 2, SELF: 4, OFF_ROOM: 8, DEAD: 16 } as const;

export interface GroupMember {
  /** The object's id (target it when it is in our room) */
  id: number;
  flags: number;
  name: string;
  hp: number;
  maxHp: number;
  mana: number;
  maxMana: number;
}

export interface GroupState {
  /** In a group of players (else just us and our companion) */
  inGroup: boolean;
  /** We lead it */
  leader: boolean;
  /** Most members, companions counted */
  max: number;
  /** Us first, then the others, each player followed by their companion */
  members: GroupMember[];
}

/** One companion bot (primebots.kod): its place in the list is its number for the `bot ...` commands */
export interface BotInfo {
  id: number;
  name: string;
  /** COMPANION_WARRIOR 4, MONK 5, PALADIN 6, ELEMENTALIST 7 */
  kind: number;
  /** COMP_FOLLOW 1, DEFEND 2, STAY 3, PASSIVE 4 */
  stance: number;
  /** Not in our room (waiting for us to a place that has it) */
  away: boolean;
  hp: number;
  maxHp: number;
  mana: number;
  maxMana: number;
  /** Its look as places in the creator's lists, and the clothes colours it may wear (as in the Companion tab) */
  look: BotLook;
  palette: number[];
}

export interface BotLook {
  gender: number;
  hair: number;
  eyes: number;
  nose: number;
  mouth: number;
  beard: number;
  hairColour: number;
  skin: number;
  colour1: number;
  colour2: number;
}

export interface BotsState {
  /** The server allows bots */
  enabled: boolean;
  /** Most bots at once (the group's seats may allow fewer) */
  max: number;
  /** Seconds until another may be summoned, when this was sent */
  wait: number;
  /** When this was received (ms), for the countdown */
  at: number;
  bots: BotInfo[];
}

/** An ability the admin tools can give (a spell or a skill): its number is for the `padmin ability` commands */
export interface AdminAbility {
  /** 0 spell, 1 skill */
  kind: number;
  num: number;
  name: string;
  /** SS_* of the school (0 for a skill with none) and its level */
  school: number;
  level: number;
}

/** One ability of the character picked on the admin Character tab */
export interface AdminKnown {
  kind: number;
  num: number;
  name: string;
  percent: number;
}

export interface AdminChar {
  id: number;
  name: string;
  /** CLASS_* (0 none) */
  cls: number;
  baseHp: number;
  hp: number;
}

/** The health (percent) of each attackable monster in our room */
export type GroupEvent =
  | { type: "adminList"; list: number; total: number; start: number; strings: string[]; abilities: AdminAbility[] }
  | { type: "adminChar"; char: AdminChar }
  | { type: "adminKnown"; total: number; start: number; known: AdminKnown[] }
  | { type: "bots"; state: BotsState } | { type: "state"; state: GroupState } | { type: "invite"; from: string } | { type: "health"; mobs: [number, number][] } | { type: "combat"; id: number; amount: number; heal: boolean };

export function readPrimeGroup(r: ByteReader): GroupEvent | null {
  const kind = r.u8();
  if (kind === 6) {
    const sub = r.u8();
    if (sub === 1) {
      const list = r.u8();
      const total = r.u16();
      const start = r.u16();
      const strings: string[] = [];
      const abilities: AdminAbility[] = [];
      for (let n = r.u8(); n > 0; n--) {
        if (list === 3) {
          const k = r.u8();
          const num = r.u16();
          const name = r.string();
          abilities.push({ kind: k, num, name, school: r.u8(), level: r.u8() });
        } else {
          strings.push(r.string());
        }
      }
      return { type: "adminList", list, total, start, strings, abilities };
    }
    if (sub === 2) {
      const id = objId(r.u32());
      const name = r.string();
      return { type: "adminChar", char: { id, name, cls: r.u8(), baseHp: r.u16(), hp: r.u16() } };
    }
    if (sub === 3) {
      const total = r.u16();
      const start = r.u16();
      const known: AdminKnown[] = [];
      for (let n = r.u8(); n > 0; n--) {
        const k = r.u8();
        const num = r.u16();
        const name = r.string();
        known.push({ kind: k, num, name, percent: r.u8() });
      }
      return { type: "adminKnown", total, start, known };
    }
    return null;
  }
  if (kind === 5) {
    const enabled = r.u8() !== 0;
    const max = r.u8();
    const wait = r.u16();
    const bots: BotInfo[] = [];
    for (let n = r.u8(); n > 0; n--) {
      const id = objId(r.u32());
      const name = r.string();
      const bk = r.u8();
      const stance = r.u8();
      const away = (r.u8() & 1) !== 0;
      const hp = r.u16(), maxHp = r.u16(), mana = r.u16(), maxMana = r.u16();
      const look: BotLook = { gender: r.u8(), hair: r.u8(), eyes: r.u8(), nose: r.u8(), mouth: r.u8(), beard: r.u8(), hairColour: r.u8(), skin: r.u8(), colour1: r.u8(), colour2: r.u8() };
      const palette: number[] = [];
      for (let k = r.u8(); k > 0; k--) palette.push(r.u8());
      bots.push({ id, name, kind: bk, stance, away, hp, maxHp, mana, maxMana, look, palette });
    }
    return { type: "bots", state: { enabled, max, wait, at: Date.now(), bots } };
  }
  if (kind === 2) return { type: "invite", from: r.string() };
  if (kind === 4) return { type: "combat", id: objId(r.u32()), amount: r.u16(), heal: r.u8() !== 0 };
  if (kind === 3) {
    const mobs: [number, number][] = [];
    for (let n = r.u8(); n > 0; n--) mobs.push([objId(r.u32()), r.u8()]);
    return { type: "health", mobs };
  }
  if (kind !== 1) return null;
  if (kind !== 1) return null;
  const inGroup = r.u8() !== 0;
  const leader = r.u8() !== 0;
  const max = r.u8();
  const members: GroupMember[] = [];
  for (let n = r.u8(); n > 0; n--) {
    const id = objId(r.u32());
    const flags = r.u8();
    const name = r.string();
    members.push({ id, flags, name, hp: r.u16(), maxHp: r.u16(), mana: r.u16(), maxMana: r.u16() });
  }
  return { type: "state", state: { inGroup, leader, max, members } };
}
