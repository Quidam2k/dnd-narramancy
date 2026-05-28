/**
 * Narramancy — JSON Importer
 *
 * Handles importing a creature JSON file:
 *   1. Parse and validate the JSON
 *   2. Create a Folder for the creature's tables
 *   3. Create RollTable documents inside that folder
 *   4. Store trigger config in module settings
 */

import { slugify, tableName } from "./utils.js";
import { getCreatureData, setCreatureData } from "./settings.js";

const MODULE_ID = "narramancy";

/**
 * Import a Narramancy JSON file. Called from the import dialog.
 *
 * @param {File} file - The uploaded JSON file
 * @returns {Promise<{name: string, tableCount: number, triggerCount: number}>}
 */
export async function importCreatureFile(file) {
  const text = await file.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch (e) {
    throw new Error(`Invalid JSON: ${e.message}`);
  }

  return importCreatureData(data);
}

/**
 * Import creature data from a parsed JSON object.
 * Handles both v1 (single creature) and v2 (multi-creature) formats.
 *
 * @param {Object} data - Parsed Narramancy JSON (v1 or v2)
 * @returns {Promise<Object>} v1: {name, tableCount, triggerCount}, v2: {creatures: [...], totalTables, totalTriggers}
 */
export async function importCreatureData(data) {
  // v2 multi-creature format
  if (data.formatVersion === 2 && Array.isArray(data.creatures)) {
    const results = [];
    let totalTables = 0;
    let totalTriggers = 0;

    for (const entry of data.creatures) {
      const result = await _importSingleCreature(entry);
      results.push(result);
      totalTables += result.tableCount;
      totalTriggers += result.triggerCount;
    }

    ui.notifications.info(
      `Narramancy: Imported ${results.length} creatures (${totalTables} tables, ${totalTriggers} triggers)`
    );

    return {
      creatures: results.map((r) => ({
        name: r.name,
        tableCount: r.tableCount,
        triggerCount: r.triggerCount,
      })),
      totalTables,
      totalTriggers,
    };
  }

  // v1 single-creature format
  if (data.formatVersion === 1) {
    return _importSingleCreature(data);
  }

  throw new Error(
    `Unsupported format version: ${data.formatVersion}. Expected 1 or 2.`
  );
}

/**
 * Import a single creature entry.
 *
 * @param {Object} entry - Creature entry with {creature, tables, triggers, whisper}
 * @returns {Promise<{name: string, tableCount: number, triggerCount: number}>}
 */
async function _importSingleCreature(entry) {
  if (!entry.creature?.name) {
    throw new Error("Missing creature.name in JSON.");
  }
  if (!Array.isArray(entry.tables) || entry.tables.length === 0) {
    throw new Error(`No tables found for creature "${entry.creature.name}".`);
  }

  const creatureName = entry.creature.name;
  const slug = slugify(creatureName);

  // Check for existing creature — offer to replace
  const creatures = getCreatureData();
  if (creatures[slug]) {
    const replace = await Dialog.confirm({
      title: game.i18n.localize("NARRAMANCY.import.title"),
      content: game.i18n.format("NARRAMANCY.import.replace", {
        name: creatureName,
      }),
    });
    if (!replace) {
      throw new Error("Import cancelled by user.");
    }
    await deleteCreature(slug);
  }

  // Create folder for this creature's tables
  let folder;
  try {
    folder = await Folder.create({
      name: creatureName,
      type: "RollTable",
      color: "#7b2d8e",
    });
  } catch (err) {
    throw new Error(`Failed to create folder for "${creatureName}": ${err.message}`);
  }

  // Create each RollTable
  let tableCount = 0;
  const tableIdMap = {}; // "ability|category" -> RollTable ID

  for (const tableData of entry.tables) {
    if (
      !tableData.ability ||
      !tableData.category ||
      !Array.isArray(tableData.entries) ||
      tableData.entries.length === 0
    ) {
      console.warn("Narramancy | Skipping invalid table entry:", tableData);
      continue;
    }

    const fullName = tableName(
      creatureName,
      tableData.ability,
      tableData.category
    );
    const n = tableData.entries.length;

    // Build table results — each entry gets equal weight
    const results = tableData.entries.map((text, i) => ({
      text: text,
      type: CONST.TABLE_RESULT_TYPES.TEXT,
      range: [i + 1, i + 1],
      weight: 1,
    }));

    try {
      const rollTable = await RollTable.create({
        name: fullName,
        description: tableData.description || "",
        formula: `1d${n}`,
        replacement: true,
        displayRoll: false,
        folder: folder.id,
        results: results,
      });

      const tableKey = `${tableData.ability}|${tableData.category}`;
      tableIdMap[tableKey] = rollTable.id;
      tableCount++;
    } catch (err) {
      console.error(`Narramancy | Failed to create table "${fullName}":`, err);
    }
  }

  // Store creature config in settings
  const triggerCount = Array.isArray(entry.triggers) ? entry.triggers.length : 0;

  creatures[slug] = {
    name: creatureName,
    slug: slug,
    tokenPattern: entry.creature.tokenPattern || `*${creatureName}*`,
    whisper: entry.whisper || "gm",
    cr: entry.creature.cr || "",
    type: entry.creature.type || "",
    triggers: entry.triggers || [],
    tableIdMap: tableIdMap,
    folderId: folder.id,
    tableCount: tableCount,
    triggerCount: triggerCount,
    importedAt: new Date().toISOString().split("T")[0],
  };

  await setCreatureData(creatures);

  ui.notifications.info(
    game.i18n.format("NARRAMANCY.import.success", {
      name: creatureName,
      tableCount: tableCount,
      triggerCount: triggerCount,
    })
  );

  return { name: creatureName, tableCount, triggerCount };
}

/**
 * Delete a creature and all its associated tables/folder.
 *
 * @param {string} slug - Creature slug
 */
export async function deleteCreature(slug) {
  const creatures = getCreatureData();
  const creature = creatures[slug];
  if (!creature) return;

  // Delete all tables in the folder
  if (creature.folderId) {
    const folder = game.folders.get(creature.folderId);
    if (folder) {
      const tables = game.tables.filter(
        (t) => t.folder?.id === creature.folderId
      );
      for (const table of tables) {
        await table.delete();
      }
      await folder.delete();
    }
  }

  delete creatures[slug];
  await setCreatureData(creatures);
}
