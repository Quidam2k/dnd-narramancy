/**
 * Narramancy — PC Exporter
 *
 * Exports a Foundry actor's data + any existing flavor tables as a combined
 * JSON file for use with the Narramancy Web UI.
 */

import { slugify } from "./utils.js";
import { getCreatureData } from "./settings.js";

/**
 * Export a single character actor to a combined Narramancy JSON file.
 * Triggers a browser download via saveDataToFile().
 *
 * @param {Actor} actor - Foundry Actor document (type "character")
 */
export async function exportCharacterToJSON(actor) {
  const actorData = actor.toObject();
  const slug = slugify(actor.name);
  const creatures = getCreatureData();
  const creatureConfig = creatures[slug];

  let existingTables = null;

  if (creatureConfig && creatureConfig.tableIdMap) {
    existingTables = reconstructFlavorJSON(actor.name, creatureConfig);
  }

  const exportData = {
    narramancyExport: 1,
    exportedAt: new Date().toISOString(),
    actor: actorData,
    existingTables: existingTables,
  };

  const jsonStr = JSON.stringify(exportData, null, 2);
  const filename = `${actor.name.replace(/[^a-zA-Z0-9 _-]/g, "")}-narramancy-export.json`;

  saveDataToFile(jsonStr, "text/json", filename);

  const tableCount = existingTables ? (existingTables.tables || []).length : 0;
  ui.notifications.info(
    game.i18n.format("NARRAMANCY.export.success", {
      name: actor.name,
      count: tableCount,
    })
  );
}

/**
 * Export all character-type actors. Each gets its own download.
 */
export async function exportAllCharacters() {
  const characters = game.actors.filter((a) => a.type === "character");
  if (characters.length === 0) {
    ui.notifications.warn(
      game.i18n.localize("NARRAMANCY.export.noCharacters")
    );
    return;
  }

  for (const actor of characters) {
    await exportCharacterToJSON(actor);
  }
}

/**
 * Reconstruct a narramancy JSON object from stored creature config
 * and Foundry RollTable documents.
 *
 * @param {string} creatureName
 * @param {Object} config - Creature config from settings (has tableIdMap, triggers, etc.)
 * @returns {Object} narramancy JSON with tables, triggers, creature keys
 */
function reconstructFlavorJSON(creatureName, config) {
  const tables = [];

  for (const [key, tableId] of Object.entries(config.tableIdMap || {})) {
    const rollTable = game.tables.get(tableId);
    if (!rollTable) continue;

    const [ability, category] = key.split("|");
    const entries = [];

    // Sort results by range to maintain original order
    const sortedResults = [...rollTable.results].sort(
      (a, b) => (a.range?.[0] ?? 0) - (b.range?.[0] ?? 0)
    );

    for (const result of sortedResults) {
      entries.push(result.text);
    }

    if (entries.length === 0) continue;

    tables.push({
      ability: ability,
      category: category,
      description: rollTable.description || "",
      entries: entries,
    });
  }

  return {
    formatVersion: 1,
    creature: {
      name: creatureName,
      tokenPattern: config.tokenPattern || `*${creatureName}*`,
      cr: config.cr || "",
      type: config.type || "",
    },
    tables: tables,
    triggers: config.triggers || [],
  };
}
