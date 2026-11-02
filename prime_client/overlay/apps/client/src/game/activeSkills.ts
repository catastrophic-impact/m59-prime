// Prime (ours, overlay file): skills the player USES (the others work by themselves). A quick slot may hold one; using it sends
// the UC_SHARDS_OBJECT line "skill <number>" about the target (kod/object/prime/primeclasses.kod ObjectVerb).

/** English skill name (lower case) -> the server's skill number (SKID_*) */
export const ACTIVE_SKILLS: Readonly<Record<string, number>> = {
  "shield slam": 407,
};

export const activeSkillNumber = (englishName: string): number | undefined => ACTIVE_SKILLS[englishName.toLowerCase()];
