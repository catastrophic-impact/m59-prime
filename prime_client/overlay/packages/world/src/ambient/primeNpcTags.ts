// Prime (ours, overlay file): the wandering townsfolk are drawn by this client only, so they get a name tag in a colour of their own
// (soft teal) that no real player or monster uses: you can tell a crowd member from a person at a glance.

import type { ObjectInfo } from "@shards/protocol";

/** nameColor (0xRRGGBB) of an ambient NPC's tag */
export const NPC_TAG_COLOR = 0x78c8be;
const LOCAL_NAME_BASE = 0x7e000000;
const OF_DISPLAY_NAME = 0x1;

const names: string[] = [];
const byName = new Map<string, number>();

/** A local "resource number" that stands for a name (the name label asks the session for strings by number) */
export function localNameRes(name: string): number {
  let res = byName.get(name);
  if (res === undefined) {
    res = LOCAL_NAME_BASE + names.length;
    names.push(name);
    byName.set(name, res);
  }
  return res;
}

/** The name behind a local name number, or undefined for an ordinary server resource */
export function localNameOf(res: number): string | undefined {
  return res >= LOCAL_NAME_BASE && res < LOCAL_NAME_BASE + names.length ? names[res - LOCAL_NAME_BASE] : undefined;
}

/** Give an ambient person a name tag in the NPC colour */
export function tagAmbient(info: ObjectInfo, name: string): void {
  info.nameRes = localNameRes(name);
  info.flags |= OF_DISPLAY_NAME;
  info.nameColor = NPC_TAG_COLOR;
}
