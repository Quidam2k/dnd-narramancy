/**
 * Narramancy — Trigger Engine
 *
 * Listens to dnd5e 3.x hooks, matches token names against imported creature
 * patterns, rolls the appropriate table, and whispers the result.
 *
 * Roll-aware dispatch: inspects d20 results for nat 1/20, compares to target
 * AC for barely-hits/misses, detects bloodied threshold, tracks shown entries
 * to avoid repeats within a combat.
 *
 * Hook signatures follow dnd5e 3.x (Foundry v11+/v12):
 *   dnd5e.rollAttack(rolls, data)      — data.subject is an AttackActivity
 *   dnd5e.rollDamage(rolls, data)      — data.subject is an Activity
 *   dnd5e.preUseItem(activity, config, messageConfig)
 *   dnd5e.rollSavingThrow(rolls, data) — data.ability (str), data.subject (Actor5e)
 *   dnd5e.rollSkill(rolls, data)       — data.skill (str), data.subject (Actor5e)
 *   dnd5e.rollDeathSave(rolls, data)   — data.subject (Actor5e)
 *   dnd5e.rollInitiative(actor, combatants)
 */

import { wildcardMatch } from "./utils.js";
import { getCreatureData, isEnabled } from "./settings.js";

const MODULE_ID = "narramancy";

/* ── No-Repeat Tracking ──────────────────────────────────── */

/** Map<string, Set<string>> keyed by "tokenPattern:tableKey" */
const shownEntries = new Map();

/** Map<string, boolean> keyed by actor ID — tracks if bloodied already fired */
const bloodiedFired = new Map();

/** Map<string, boolean> keyed by actor ID — tracks if death already fired */
const deathFired = new Map();

/**
 * Last damage source — tracks the most recent rollDamage so we can
 * attribute killing blows to the attacker when a target reaches 0 HP.
 * @type {{ actorId: string, tokenName: string, itemName: string } | null}
 */
let lastDamageSource = null;

/**
 * Extract the natural d20 result from a rolls array.
 * Walks through terms to find the actual Die with faces=20.
 * @param {Roll[]} rolls
 * @returns {number|null}
 */
function getNaturalD20(rolls) {
  if (!rolls?.[0]?.terms) return null;
  for (const term of rolls[0].terms) {
    if (term.faces === 20 && term.results?.length > 0) {
      return term.results[0].result;
    }
  }
  return null;
}

/**
 * Get the first targeted token's actor (from the user's targets).
 * @returns {Actor5e|null}
 */
function getTargetActor() {
  const targets = game.user.targets;
  if (!targets?.size) return null;
  return targets.first()?.actor ?? null;
}

/**
 * Get the AC of the first targeted token.
 * @returns {number|null}
 */
function getTargetAC() {
  return getTargetActor()?.system?.attributes?.ac?.value ?? null;
}

/**
 * Get the DEX modifier of the first targeted token.
 * @returns {number|null}
 */
function getTargetDexMod() {
  return getTargetActor()?.system?.abilities?.dex?.mod ?? null;
}

/**
 * Determine the best conditional hookType for an attack roll.
 *
 * Priority:
 *   1. Nat 20 → "attackRoll_crit"
 *   2. Nat 1  → "attackRoll_fumble"
 *   3. Hit, margin <= 2 → "attackRoll_barely_hits"
 *   4. Miss, margin <= 2 → "attackRoll_barely_misses"
 *   5. Otherwise → "attackRoll" (normal)
 *
 * @param {Roll[]} rolls
 * @returns {string}
 */
function classifyAttackRoll(rolls) {
  const nat = getNaturalD20(rolls);
  if (nat === 20) return "attackRoll_crit";
  if (nat === 1) return "attackRoll_fumble";

  const total = rolls?.[0]?.total;
  const ac = getTargetAC();
  if (total != null && ac != null) {
    const margin = total - ac;
    if (margin >= 0 && margin <= 2) return "attackRoll_barely_hits";
    if (margin < 0 && margin >= -2) return "attackRoll_barely_misses";

    // Miss: determine dodge vs armor deflection
    if (margin < 0) {
      const dexMod = getTargetDexMod();
      if (dexMod != null) {
        const touchAC = 10 + dexMod;
        // Roll didn't even beat their reflexes → they dodged
        if (total < touchAC) return "attackRoll_miss_dodge";
        // Roll beat their reflexes but not their armor → armor stopped it
        return "attackRoll_miss_armor";
      }
    }
  }

  return "attackRoll";
}

/**
 * Register all dnd5e hook listeners.
 * Called once from main.js when the game is ready.
 */
export function registerTriggerHooks() {
  console.log("Narramancy | Registering trigger hooks");

  // Attack rolls — dnd5e 3.x: (rolls, data) where data.subject is AttackActivity
  // Roll-aware: inspects d20 for nat 1/20, compares to target AC for margin
  Hooks.on("dnd5e.rollAttack", (rolls, data) => {
    const activity = data?.subject;
    const item = activity?.item;
    const actor = item?.parent ?? activity?.actor;
    if (item && actor) {
      const hookType = classifyAttackRoll(rolls);
      handleItemHook(hookType, actor, item.name);
    }
  });

  // Damage rolls — dnd5e 3.x: (rolls, data) where data.subject is Activity
  // Also stores last damage source for killing blow attribution.
  Hooks.on("dnd5e.rollDamage", (rolls, data) => {
    const activity = data?.subject;
    const item = activity?.item;
    const actor = item?.parent ?? activity?.actor;
    if (item && actor) {
      lastDamageSource = {
        actorId: actor.id,
        tokenName: getTokenName(actor),
        itemName: item.name,
      };
      handleItemHook("damageRoll", actor, item.name);
    }
  });

  // Item/feature use — dnd5e 3.x: (activity, config, messageConfig)
  // Activity-type dispatch for multi-phase spell support:
  //   utility/enchant/summon/transform/heal/ddbmacro/forward → spellCast
  //   save/damage → spellEffect
  //   attack → SKIP (handled by dnd5e.rollAttack)
  //   anything else → itemUse
  // Falls back to itemUse if no specific trigger matches.
  Hooks.on("dnd5e.preUseItem", (activity, config, messageConfig) => {
    const item = activity?.item;
    const actor = item?.parent;
    if (!item || !actor) return;

    const activityType = activity?.type ?? "";
    const castTypes = new Set(["utility", "enchant", "summon", "transform", "heal", "ddbmacro", "forward"]);
    const effectTypes = new Set(["save", "damage"]);
    const skipTypes = new Set(["attack", "check"]);

    let hookType;
    if (skipTypes.has(activityType)) {
      return; // Handled by rollAttack / rollCheck hooks
    } else if (castTypes.has(activityType)) {
      hookType = "spellCast";
    } else if (effectTypes.has(activityType)) {
      hookType = "spellEffect";
    } else {
      hookType = "itemUse";
    }

    // Try specific hookType first; fall back to itemUse for backwards compat
    const fired = handleItemHook(hookType, actor, item.name);
    if (!fired && hookType !== "itemUse") {
      handleItemHook("itemUse", actor, item.name);
    }
  });

  // Saving throws — dnd5e 3.x: (rolls, data) where data.ability and data.subject
  Hooks.on("dnd5e.rollSavingThrow", (rolls, data) => {
    const actor = data?.subject;
    const abilityId = data?.ability; // "str", "dex", etc.
    if (actor && abilityId) {
      handleActorHook("savingThrow", actor, { abilityId });
    }
  });

  // Skill checks — dnd5e 3.x: (rolls, data) where data.skill and data.subject
  Hooks.on("dnd5e.rollSkill", (rolls, data) => {
    const actor = data?.subject;
    const skillId = data?.skill; // "prc", "ste", etc.
    if (actor && skillId) {
      handleActorHook("skill", actor, { skillId });
    }
  });

  // Death saving throws — dnd5e 3.x: (rolls, data)
  Hooks.on("dnd5e.rollDeathSave", (rolls, data) => {
    const actor = data?.subject;
    if (actor) {
      handleActorHook("deathSave", actor, {});
    }
  });

  // Initiative — dnd5e 3.x: (actor, combatants)
  Hooks.on("dnd5e.rollInitiative", (actor, combatants) => {
    if (actor) {
      handleActorHook("initiative", actor, {});
    }
  });

  // Bloodied detection — fires when a creature crosses half HP
  Hooks.on("updateActor", (actor, change, options, userId) => {
    if (!isEnabled()) return;
    const newHP = foundry.utils.getProperty(change, "system.attributes.hp.value");
    if (newHP === undefined) return;

    const maxHP = actor.system.attributes.hp.max;
    const halfHP = Math.floor(maxHP / 2);
    // In Foundry v12, the actor object already reflects the NEW state after updateActor,
    // but the change object contains only the changed fields. We need the OLD HP.
    // Use options.dnd5e?.dhp (damage delta) if available, otherwise estimate.
    const dhp = options?.dnd5e?.dhp ?? options?.dhp;
    let oldHP;
    if (dhp !== undefined) {
      oldHP = newHP - dhp; // dhp is negative for damage
    } else {
      // Fallback: check if we stored it (not reliable, but better than nothing)
      oldHP = actor._prevHP ?? maxHP;
    }
    actor._prevHP = newHP;

    if (oldHP > halfHP && newHP <= halfHP && newHP > 0) {
      const actorId = actor.id;
      if (bloodiedFired.get(actorId)) return; // Already fired this combat
      bloodiedFired.set(actorId, true);
      handleBloodiedEvent(actor);
    }

    // Death detection — HP drops to 0
    if (oldHP > 0 && newHP <= 0) {
      const actorId = actor.id;
      if (!deathFired.get(actorId)) {
        deathFired.set(actorId, true);
        handleDeathEvent(actor);
        handleKillingBlowEvent(actor);
      }
    }
  });

  // Reset no-repeat tracking and bloodied/death flags when combat ends
  Hooks.on("deleteCombat", () => {
    shownEntries.clear();
    bloodiedFired.clear();
    deathFired.clear();
    lastDamageSource = null;
    console.log("Narramancy | Combat ended — reset tracking");
  });

  // MidiQOL integration (awareness-only for v1)
  registerMidiQOLHooks();

  console.log("Narramancy | Trigger hooks registered");
}

/**
 * Register MidiQOL hooks if the setting is enabled and midi-qol is active.
 * v1: logging only — infrastructure for future hookTypes like
 * concentrationCheck, concentrationBreak, templateEnter.
 */
function registerMidiQOLHooks() {
  try {
    const useMidi = game.settings.get(MODULE_ID, "useMidiQOL");
    if (!useMidi) return;
  } catch {
    return; // Setting not registered yet
  }

  const midiModule = game.modules.get("midi-qol");
  if (!midiModule?.active) {
    console.log("Narramancy | MidiQOL integration enabled but midi-qol not active");
    return;
  }

  Hooks.on("midi-qol.RollComplete", (workflow) => {
    console.log("Narramancy | MidiQOL RollComplete:", workflow?.item?.name);
  });

  console.log("Narramancy | MidiQOL hooks registered");
}

/**
 * Handle a hook that fires from an item (attack, damage, item use).
 * Returns true if a trigger matched and fired, false otherwise.
 *
 * @param {string} hookType
 * @param {Actor5e} actor
 * @param {string} itemName
 * @returns {boolean}
 */
function handleItemHook(hookType, actor, itemName) {
  if (!isEnabled()) return false;

  const tokenName = getTokenName(actor);
  if (!tokenName) return false;

  const creatures = getCreatureData();

  for (const creature of Object.values(creatures)) {
    if (!wildcardMatch(creature.tokenPattern, tokenName)) continue;

    // Find matching trigger — try conditional hookType first, fall back to base
    let trigger = creature.triggers.find(
      (t) =>
        t.hookType === hookType &&
        t.itemName &&
        itemName.toLowerCase() === t.itemName.toLowerCase()
    );

    // Fall back to base "attackRoll" if no conditional trigger exists
    if (!trigger && hookType.startsWith("attackRoll_")) {
      trigger = creature.triggers.find(
        (t) =>
          t.hookType === "attackRoll" &&
          t.itemName &&
          itemName.toLowerCase() === t.itemName.toLowerCase()
      );
    }

    if (trigger) {
      rollAndWhisper(creature, trigger, tokenName, actor);
      return true; // Matched and fired
    }
  }
  return false; // No match
}

/**
 * Handle a hook that fires from an actor (saves, skills, death save, initiative).
 *
 * @param {string} hookType
 * @param {Actor5e} actor
 * @param {Object} detail - { abilityId, skillId, etc. }
 */
function handleActorHook(hookType, actor, detail) {
  if (!isEnabled()) return;

  const tokenName = getTokenName(actor);
  if (!tokenName) return;

  const creatures = getCreatureData();

  for (const creature of Object.values(creatures)) {
    if (!wildcardMatch(creature.tokenPattern, tokenName)) continue;

    // Find matching trigger
    const trigger = creature.triggers.find((t) => {
      if (t.hookType !== hookType) return false;
      if (hookType === "savingThrow") return t.saveId === detail.abilityId;
      if (hookType === "skill") return t.skillId === detail.skillId;
      // death saves and initiative: any trigger of that type matches
      return true;
    });

    if (trigger) {
      rollAndWhisper(creature, trigger, tokenName, actor);
      return;
    }
  }
}

/**
 * Handle the bloodied event — creature just crossed half HP.
 *
 * @param {Actor5e} actor
 */
function handleBloodiedEvent(actor) {
  const tokenName = getTokenName(actor);
  if (!tokenName) return;

  const creatures = getCreatureData();

  for (const creature of Object.values(creatures)) {
    if (!wildcardMatch(creature.tokenPattern, tokenName)) continue;

    const trigger = creature.triggers.find((t) => t.hookType === "bloodied");
    if (trigger) {
      rollAndWhisper(creature, trigger, tokenName, actor);
      return;
    }
  }
}

/**
 * Handle the death event — creature HP dropped to 0.
 *
 * @param {Actor5e} actor
 */
function handleDeathEvent(actor) {
  const tokenName = getTokenName(actor);
  if (!tokenName) return;

  const creatures = getCreatureData();

  for (const creature of Object.values(creatures)) {
    if (!wildcardMatch(creature.tokenPattern, tokenName)) continue;

    const trigger = creature.triggers.find((t) => t.hookType === "death");
    if (trigger) {
      rollAndWhisper(creature, trigger, tokenName, actor);
      return;
    }
  }
}

/**
 * Handle the killing blow event — attribute to the ATTACKER when a creature dies.
 * Uses the last stored damage source to find matching killingBlow triggers
 * on the attacker's creature data.
 *
 * @param {Actor5e} dyingActor - The actor that just reached 0 HP
 */
function handleKillingBlowEvent(dyingActor) {
  if (!lastDamageSource) return;

  const { actorId, tokenName, itemName } = lastDamageSource;
  if (!tokenName || !itemName) return;

  const attackerActor = actorId ? game.actors.get(actorId) : null;
  const creatures = getCreatureData();

  for (const creature of Object.values(creatures)) {
    if (!wildcardMatch(creature.tokenPattern, tokenName)) continue;

    const trigger = creature.triggers.find(
      (t) =>
        t.hookType === "killingBlow" &&
        t.itemName &&
        itemName.toLowerCase() === t.itemName.toLowerCase()
    );

    if (trigger) {
      rollAndWhisper(creature, trigger, tokenName, attackerActor);
      return;
    }
  }
}

/**
 * Roll the table referenced by a trigger and send a whispered chat message.
 * Includes no-repeat tracking — avoids showing the same result twice in a combat.
 *
 * @param {Object} creature - Creature config from settings
 * @param {Object} trigger - Trigger config with .table key
 * @param {string} tokenName - Display name of the token
 * @param {Actor5e} [actor] - The acting actor (for player whisper flags)
 */
async function rollAndWhisper(creature, trigger, tokenName, actor) {
  const tableKey = trigger.table; // e.g., "Shortsword|attempts"
  const tableId = creature.tableIdMap?.[tableKey];

  if (!tableId) {
    console.warn(
      `Narramancy | No table ID found for key "${tableKey}" on creature "${creature.name}"`
    );
    return;
  }

  const table = game.tables.get(tableId);
  if (!table) {
    console.warn(
      `Narramancy | RollTable ${tableId} not found (deleted?)`
    );
    return;
  }

  // No-repeat tracking
  const trackingKey = `${creature.tokenPattern}:${tableKey}`;
  const seen = shownEntries.get(trackingKey) || new Set();
  const totalEntries = table.results.size;

  // Roll the table, re-rolling up to 3 times to avoid repeats
  let resultText = null;
  for (let attempt = 0; attempt < Math.min(3, totalEntries); attempt++) {
    let roll;
    try {
      roll = await table.roll({ displayChat: false });
    } catch (err) {
      console.error(`Narramancy | Error rolling table "${tableKey}":`, err);
      return;
    }
    const text = roll.results?.[0]?.text;
    if (!text) return;

    if (!seen.has(text) || seen.size >= totalEntries) {
      resultText = text;
      break;
    }
  }

  if (!resultText) return;

  seen.add(resultText);
  shownEntries.set(trackingKey, seen);

  // Build whisper recipients
  const whisperIds = getWhisperTargets(creature, actor);

  // Parse table key for context (e.g., "Shortsword|attempts" → ability + category)
  const [abilityName, category] = tableKey.includes("|")
    ? tableKey.split("|", 2)
    : [tableKey, ""];
  const categoryLabel = category
    ? category.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase())
    : "";
  const header = categoryLabel
    ? `<strong>${tokenName}</strong> — ${abilityName} (${categoryLabel})`
    : `<strong>${tokenName}</strong> — ${abilityName}`;

  // Send the flavor message
  try {
    await ChatMessage.create({
      content: `<div class="narramancy-msg"><div class="narramancy-header">${header}</div><em>${resultText}</em></div>`,
      whisper: whisperIds,
      speaker: { alias: tokenName },
    });
  } catch (err) {
    console.error(`Narramancy | Error sending chat message for "${tableKey}":`, err);
  }
}

/**
 * Get the best token name for an actor.
 *
 * @param {Actor5e} actor
 * @returns {string|null}
 */
function getTokenName(actor) {
  if (canvas.scene) {
    const tokens = actor.getActiveTokens();
    if (tokens.length > 0) {
      return tokens[0].name;
    }
  }
  return actor.prototypeToken?.name || actor.name;
}

/**
 * Resolve whisper setting to an array of user IDs.
 * Always includes GM. If the actor has player whisper flags enabled,
 * those players are added as additional recipients.
 *
 * @param {Object} creature
 * @param {Actor5e} [actor] - The acting actor (for player whisper flags)
 * @returns {string[]}
 */
function getWhisperTargets(creature, actor) {
  const whisper =
    creature.whisper ||
    game.settings.get(MODULE_ID, "defaultWhisper") ||
    "gm";

  const gmIds = ChatMessage.getWhisperRecipients("GM").map((u) => u.id);

  let baseIds;
  switch (whisper) {
    case "gm":
      baseIds = gmIds;
      break;
    case "owner":
      baseIds = [];
      break;
    case "gm+owner":
      baseIds = gmIds;
      break;
    case "public":
      baseIds = [];
      break;
    default:
      baseIds = gmIds;
  }

  // Add player whisper recipients from actor flags
  if (actor) {
    const gmDisabled = actor.getFlag(MODULE_ID, "gmDisabled");
    if (!gmDisabled) {
      const playerWhispers = actor.getFlag(MODULE_ID, "playerWhispers") || {};
      for (const [userId, enabled] of Object.entries(playerWhispers)) {
        if (enabled && !baseIds.includes(userId)) {
          baseIds.push(userId);
        }
      }
    }
  }

  return baseIds;
}
