/**
 * Flavor Forge — JSON Importer
 *
 * Handles importing a creature JSON file:
 *   1. Parse and validate the JSON
 *   2. Create a Folder for the creature's tables
 *   3. Create RollTable documents inside that folder
 *   4. Store trigger config in module settings
 */

import { slugify, tableName } from "./utils.js";
import { getCreatureData, setCreatureData } from "./settings.js";

const MODULE_ID = "flavor-forge";

/**
 * Import a Flavor Forge JSON file. Called from the import dialog.
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
 *
 * @param {Object} data - Parsed Flavor Forge JSON
 * @returns {Promise<{name: string, tableCount: number, triggerCount: number}>}
 */
export async function importCreatureData(data) {
  // Validate format
  if (!data.formatVersion || data.formatVersion !== 1) {
    throw new Error(
      `Unsupported format version: ${data.formatVersion}. Expected 1.`
    );
  }
  if (!data.creature?.name) {
    throw new Error("Missing creature.name in JSON.");
  }
  if (!Array.isArray(data.tables) || data.tables.length === 0) {
    throw new Error("No tables found in JSON.");
  }

  const creatureName = data.creature.name;
  const slug = slugify(creatureName);

  // Check for existing creature — offer to replace
  const creatures = getCreatureData();
  if (creatures[slug]) {
    const replace = await Dialog.confirm({
      title: game.i18n.localize("FLAVOR_FORGE.import.title"),
      content: game.i18n.format("FLAVOR_FORGE.import.replace", {
        name: creatureName,
      }),
    });
    if (!replace) {
      throw new Error("Import cancelled by user.");
    }
    await deleteCreature(slug);
  }

  // Create folder for this creature's tables
  const folder = await Folder.create({
    name: creatureName,
    type: "RollTable",
    color: "#7b2d8e",
  });

  // Create each RollTable
  let tableCount = 0;
  const tableIdMap = {}; // "ability|category" -> RollTable ID

  for (const tableData of data.tables) {
    if (
      !tableData.ability ||
      !tableData.category ||
      !Array.isArray(tableData.entries) ||
      tableData.entries.length === 0
    ) {
      console.warn("Flavor Forge | Skipping invalid table entry:", tableData);
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
  }

  // Store creature config in settings
  const triggerCount = Array.isArray(data.triggers) ? data.triggers.length : 0;

  creatures[slug] = {
    name: creatureName,
    slug: slug,
    tokenPattern: data.creature.tokenPattern || `*${creatureName}*`,
    whisper: data.whisper || "gm",
    cr: data.creature.cr || "",
    type: data.creature.type || "",
    triggers: data.triggers || [],
    tableIdMap: tableIdMap,
    folderId: folder.id,
    tableCount: tableCount,
    triggerCount: triggerCount,
    importedAt: new Date().toISOString().split("T")[0],
  };

  await setCreatureData(creatures);

  ui.notifications.info(
    game.i18n.format("FLAVOR_FORGE.import.success", {
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
