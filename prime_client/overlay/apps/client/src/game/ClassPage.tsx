// Prime (ours, overlay file): the class page of the character creator. A character picks a class (look, name and class only);
// the server fixes the stats and the first abilities. The class travels as a pseudo skill number 1000 + class
// (kod/object/prime/primeclasses.kod NewCharClass).

import { Fixed, FlowPage, FlowText, Select, Spacer, Text, type Rect } from "./ui/kit.tsx";
import type { ReactNode } from "react";

export type ClassId = 1 | 2 | 3 | 4;

/** The classes of the creator. The server fixes the real stats (shown nowhere); `stats` is only a valid placeholder the creator sends. */
export const CLASSES: readonly { id: ClassId; label: string; stats: number[]; info: string }[] = [
  {
    id: 1, label: "Warrior", stats: [35, 35, 35, 35, 35, 35],
    info:
      "Front-line fighter and shield defender.\n\n" +
      "Starts with Slash, Glow and Block. Trained by the priestess of Kraanan: Fencing, Second Wind, Dodge, Hammer Wielding, " +
      "Super Strength, Parry, Axe Wielding, Bless, Magic Shield, Scimitar Wielding, Free Action, Disarm, Armor of Gort, Resist Magic, Deflect, Anti-Magic Aura.\n\n" +
      "Warriors build the most threat with every attack. Any weapon or armor can be used, but only trained weapons do full damage.",
  },
  {
    id: 2, label: "Monk", stats: [35, 35, 35, 35, 35, 35],
    info:
      "Unarmed fighter and healer: fists, touch spells and quick feet.\n\n" +
      "Starts with Punch, Minor Heal and Mana Focus. Trained: Holy Touch, Brawling, Dodge, Bless, Hospice, Block, Holy Blaze, Dazzle, Magic Shield, " +
      "Night Vision, Major Heal, Rescue, Purify, Truce, Purge.\n\n" +
      "Monks excel at hand-to-hand combat: their fists are a real weapon. They may use any weapon or armor, but only trained weapons do full damage.",
  },
  {
    id: 3, label: "Paladin", stats: [35, 35, 35, 35, 35, 35],
    info:
      "A tank that heals: less armor than a warrior, less damage than a warrior, less healing than a monk.\n\n" +
      "Starts with Slash, Minor Heal and Block. Trained: Fencing, Spiritual Sword, Dodge, Bless, Hospice, Forces of Light, Hammer Wielding, Spiritual Hammer, " +
      "Magic Shield, Super Strength, Glow, Parry, Purify, Major Heal, Armor of Gort.\n\n" +
      "Paladins may use any weapon or armor; swords and hammers are their trained weapons.",
  },
  {
    id: 4, label: "Elementalist", stats: [35, 35, 35, 35, 35, 35],
    info:
      "A caster of fire, ice and mana. Faren is the god of the elementalist.\n\n" +
      "Starts with Touch of Flame, Minor Heal and Mana Focus. Trained by the priestess of Faren: Illuminate, Icy Fingers, Dodge, Fireball, Ice Shard, Mana Shield, " +
      "Winds, Mystic Touch, Magic Shield, Ice Nova, Firewall, Explosive Frost.\n\n" +
      "Ice Shard can slow what it hits and Ice Nova freezes everything around you. Elementalists rely almost entirely on magic.",
  },
];

export const CLASS_CREATE_BASE = 1000;

export function ClassPage({ at, cls, onChange, children }: { at: Rect; cls: ClassId; onChange: (c: ClassId) => void; children: ReactNode }) {
  const cur = CLASSES.find((c) => c.id === cls) ?? CLASSES[0];
  return (
    <FlowPage at={at}>
      <FlowText x={2} w={312} top={4} minH={20}>
        Choose your class. Your first abilities come with it, and a class cannot be changed later.
      </FlowText>
      <Fixed y={30} h={20}>
        <Text at={[2, 32, 30, 8]}>Class</Text>
        <Select at={[34, 30, 90, 14]} value={String(cls) as "1" | "2" | "3" | "4"} options={CLASSES.map((c) => ({ key: String(c.id) as "1" | "2" | "3" | "4", label: c.label }))} onChange={(v) => onChange(Number(v) as ClassId)} />
      </Fixed>
      <FlowText x={2} w={312} top={6} minH={140}>
        <div style={{ whiteSpace: "pre-line" }}>{cur.info}</div>
      </FlowText>
      <Spacer />
      <Fixed y={212} h={16}>
        {children}
      </Fixed>
    </FlowPage>
  );
}
