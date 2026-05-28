/**
 * Narramancy — Foundry VTT Module
 *
 * Imports pre-generated flavor text as rollable tables and triggers
 * whispered narration when tokens act in combat.
 */

import { registerSettings } from "./settings.js";

const MODULE_ID = "narramancy";

Hooks.once("init", () => {
  console.log("Narramancy | Initializing module");
  registerSettings();
});

Hooks.once("ready", () => {
  if (!game.user.isGM) return;
  console.log("Narramancy | Module ready");

  // Lazy-load the trigger engine and importer once the game is ready.
  // This avoids importing them before game data is available.
  import("./trigger-engine.js")
    .then((mod) => mod.registerTriggerHooks())
    .catch((err) => console.error("Narramancy | Failed to load trigger engine:", err));
});
