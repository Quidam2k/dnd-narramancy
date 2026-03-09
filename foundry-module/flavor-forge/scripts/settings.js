/**
 * Module settings registration for Flavor Forge.
 */

const MODULE_ID = "flavor-forge";

/**
 * Register all module settings. Called during Hooks.once("init").
 */
export function registerSettings() {
  // Hidden setting: stores all imported creature data
  game.settings.register(MODULE_ID, "creatureData", {
    scope: "world",
    config: false,
    type: Object,
    default: {},
  });

  // Master enable/disable switch
  game.settings.register(MODULE_ID, "enabled", {
    name: game.i18n.localize("FLAVOR_FORGE.settings.enabled.name"),
    hint: game.i18n.localize("FLAVOR_FORGE.settings.enabled.hint"),
    scope: "world",
    config: true,
    type: Boolean,
    default: true,
  });

  // Default whisper target
  game.settings.register(MODULE_ID, "defaultWhisper", {
    name: game.i18n.localize("FLAVOR_FORGE.settings.defaultWhisper.name"),
    hint: game.i18n.localize("FLAVOR_FORGE.settings.defaultWhisper.hint"),
    scope: "world",
    config: true,
    type: String,
    default: "gm",
    choices: {
      gm: game.i18n.localize("FLAVOR_FORGE.whisper.gm"),
      owner: game.i18n.localize("FLAVOR_FORGE.whisper.owner"),
      "gm+owner": game.i18n.localize("FLAVOR_FORGE.whisper.gmOwner"),
      public: game.i18n.localize("FLAVOR_FORGE.whisper.public"),
    },
  });

  // Import button in module settings
  game.settings.registerMenu(MODULE_ID, "importCreature", {
    name: game.i18n.localize("FLAVOR_FORGE.import.title"),
    label: game.i18n.localize("FLAVOR_FORGE.import.button"),
    icon: "fas fa-file-import",
    type: FlavorForgeImportMenu,
    restricted: true,
  });

  // Manage creatures button
  game.settings.registerMenu(MODULE_ID, "manageCreatures", {
    name: game.i18n.localize("FLAVOR_FORGE.manage.title"),
    label: game.i18n.localize("FLAVOR_FORGE.manage.title"),
    icon: "fas fa-dragon",
    type: FlavorForgeManageMenu,
    restricted: true,
  });
}

/**
 * Get all stored creature data.
 * @returns {Object}
 */
export function getCreatureData() {
  return game.settings.get(MODULE_ID, "creatureData");
}

/**
 * Save creature data (full object replacement).
 * @param {Object} data
 */
export async function setCreatureData(data) {
  await game.settings.set(MODULE_ID, "creatureData", data);
}

/**
 * Check if triggers are globally enabled.
 * @returns {boolean}
 */
export function isEnabled() {
  return game.settings.get(MODULE_ID, "enabled");
}

/**
 * FormApplication for importing creature JSON files.
 */
class FlavorForgeImportMenu extends FormApplication {
  static get defaultOptions() {
    return foundry.utils.mergeObject(super.defaultOptions, {
      id: "flavor-forge-import",
      title: game.i18n.localize("FLAVOR_FORGE.import.title"),
      template: `modules/${MODULE_ID}/templates/import-dialog.hbs`,
      width: 400,
    });
  }

  getData() {
    return {};
  }

  async _updateObject(event, formData) {
    const fileInput = this.element.find("#ff-import-file")[0];
    if (!fileInput?.files?.length) {
      ui.notifications.warn("No file selected.");
      return;
    }

    try {
      const { importCreatureFile } = await import("./importer.js");
      const result = await importCreatureFile(fileInput.files[0]);
      // Success notification is handled inside importCreatureFile
    } catch (err) {
      ui.notifications.error(
        game.i18n.format("FLAVOR_FORGE.import.error", { error: err.message })
      );
    }
  }
}

/**
 * Placeholder FormApplication for the creature manager.
 */
class FlavorForgeManageMenu extends FormApplication {
  static get defaultOptions() {
    return foundry.utils.mergeObject(super.defaultOptions, {
      id: "flavor-forge-manage",
      title: game.i18n.localize("FLAVOR_FORGE.manage.title"),
      template: `modules/${MODULE_ID}/templates/creature-list.hbs`,
      width: 500,
      height: "auto",
    });
  }

  getData() {
    const creatures = getCreatureData();
    return {
      creatures: Object.values(creatures),
      isEmpty: Object.keys(creatures).length === 0,
    };
  }

  async _updateObject(event, formData) {
    // Handled by button click handlers
  }

  activateListeners(html) {
    super.activateListeners(html);

    html.find(".ff-delete-creature").click(async (ev) => {
      const slug = ev.currentTarget.dataset.slug;
      const creatures = getCreatureData();
      const creature = creatures[slug];
      if (!creature) return;

      const confirm = await Dialog.confirm({
        title: game.i18n.localize("FLAVOR_FORGE.manage.title"),
        content: game.i18n.format("FLAVOR_FORGE.manage.delete", {
          name: creature.name,
        }),
      });
      if (!confirm) return;

      // Delete the folder and its tables
      try {
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
      } catch (err) {
        console.error(`Flavor Forge | Error deleting tables/folder for ${creature.name}:`, err);
        ui.notifications.error(`Error cleaning up tables for ${creature.name}. Check console.`);
      }

      // Remove from settings regardless — don't leave orphaned config
      delete creatures[slug];
      await setCreatureData(creatures);
      ui.notifications.info(`Deleted ${creature.name}`);
      this.render();
    });
  }
}
