/**
 * Module settings registration for Narramancy.
 */

const MODULE_ID = "narramancy";

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
    name: game.i18n.localize("NARRAMANCY.settings.enabled.name"),
    hint: game.i18n.localize("NARRAMANCY.settings.enabled.hint"),
    scope: "world",
    config: true,
    type: Boolean,
    default: true,
  });

  // Default whisper target
  game.settings.register(MODULE_ID, "defaultWhisper", {
    name: game.i18n.localize("NARRAMANCY.settings.defaultWhisper.name"),
    hint: game.i18n.localize("NARRAMANCY.settings.defaultWhisper.hint"),
    scope: "world",
    config: true,
    type: String,
    default: "gm",
    choices: {
      gm: game.i18n.localize("NARRAMANCY.whisper.gm"),
      owner: game.i18n.localize("NARRAMANCY.whisper.owner"),
      "gm+owner": game.i18n.localize("NARRAMANCY.whisper.gmOwner"),
      public: game.i18n.localize("NARRAMANCY.whisper.public"),
    },
  });

  // MidiQOL integration toggle
  game.settings.register(MODULE_ID, "useMidiQOL", {
    name: game.i18n.localize("NARRAMANCY.settings.useMidiQOL.name"),
    hint: game.i18n.localize("NARRAMANCY.settings.useMidiQOL.hint"),
    scope: "world",
    config: true,
    type: Boolean,
    default: false,
  });

  // Import button in module settings
  game.settings.registerMenu(MODULE_ID, "importCreature", {
    name: game.i18n.localize("NARRAMANCY.import.title"),
    label: game.i18n.localize("NARRAMANCY.import.button"),
    icon: "fas fa-file-import",
    type: NarramancyImportMenu,
    restricted: true,
  });

  // Manage creatures button
  game.settings.registerMenu(MODULE_ID, "manageCreatures", {
    name: game.i18n.localize("NARRAMANCY.manage.title"),
    label: game.i18n.localize("NARRAMANCY.manage.title"),
    icon: "fas fa-dragon",
    type: NarramancyManageMenu,
    restricted: true,
  });

  // Whisper toggle settings (accessible to all users)
  game.settings.registerMenu(MODULE_ID, "whisperSettings", {
    name: game.i18n.localize("NARRAMANCY.whisper.menuName"),
    label: game.i18n.localize("NARRAMANCY.whisper.menuName"),
    hint: game.i18n.localize("NARRAMANCY.whisper.menuHint"),
    icon: "fas fa-comment-dots",
    type: NarramancyWhisperMenu,
    restricted: false,
  });

  // Export character button
  game.settings.registerMenu(MODULE_ID, "exportCharacter", {
    name: game.i18n.localize("NARRAMANCY.export.menuName"),
    label: game.i18n.localize("NARRAMANCY.export.menuName"),
    hint: game.i18n.localize("NARRAMANCY.export.menuHint"),
    icon: "fas fa-file-export",
    type: NarramancyExportMenu,
    restricted: false,
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
class NarramancyImportMenu extends FormApplication {
  static get defaultOptions() {
    return foundry.utils.mergeObject(super.defaultOptions, {
      id: "narramancy-import",
      title: game.i18n.localize("NARRAMANCY.import.title"),
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
        game.i18n.format("NARRAMANCY.import.error", { error: err.message })
      );
    }
  }
}

/**
 * Placeholder FormApplication for the creature manager.
 */
class NarramancyManageMenu extends FormApplication {
  static get defaultOptions() {
    return foundry.utils.mergeObject(super.defaultOptions, {
      id: "narramancy-manage",
      title: game.i18n.localize("NARRAMANCY.manage.title"),
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
        title: game.i18n.localize("NARRAMANCY.manage.title"),
        content: game.i18n.format("NARRAMANCY.manage.delete", {
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
        console.error(`Narramancy | Error deleting tables/folder for ${creature.name}:`, err);
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

/**
 * FormApplication for player whisper toggle settings.
 * Players see their own actors and can opt in to receive flavor whispers.
 * GM sees all actors with per-player toggles and a GM disable switch.
 */
class NarramancyWhisperMenu extends FormApplication {
  static get defaultOptions() {
    return foundry.utils.mergeObject(super.defaultOptions, {
      id: "narramancy-whisper-settings",
      title: game.i18n.localize("NARRAMANCY.whisper.title"),
      template: `modules/${MODULE_ID}/templates/whisper-settings.hbs`,
      width: 500,
      height: "auto",
    });
  }

  getData() {
    const isGM = game.user.isGM;
    const currentUserId = game.user.id;
    const players = game.users.filter((u) => !u.isGM && u.active);

    // Get character-type actors visible to the current user
    const characterActors = game.actors.filter(
      (a) => a.type === "character" && (isGM || a.isOwner)
    );

    const actors = characterActors.map((a) => {
      const flags = a.getFlag(MODULE_ID, "playerWhispers") || {};
      const gmDisabled = a.getFlag(MODULE_ID, "gmDisabled") || false;

      // For GM: show all players who own this actor
      const ownerPlayers = players.filter(
        (u) => a.ownership[u.id] >= CONST.DOCUMENT_OWNERSHIP_LEVELS.OWNER
      );

      return {
        id: a.id,
        name: a.name,
        gmDisabled,
        gmDisabledForAll: gmDisabled,
        myWhisper: !!flags[currentUserId],
        players: ownerPlayers.map((u) => ({
          userId: u.id,
          userName: u.name,
          enabled: !!flags[u.id],
        })),
      };
    });

    return {
      actors,
      isEmpty: actors.length === 0,
      isGM,
      currentUserId,
    };
  }

  async _updateObject(event, formData) {
    // Handled by click listeners
  }

  activateListeners(html) {
    super.activateListeners(html);

    // Player whisper toggle
    html.find(".ff-whisper-toggle").change(async (ev) => {
      const { actorId, userId } = ev.currentTarget.dataset;
      const checked = ev.currentTarget.checked;
      const actor = game.actors.get(actorId);
      if (!actor) return;

      const existing = actor.getFlag(MODULE_ID, "playerWhispers") || {};
      await actor.setFlag(MODULE_ID, "playerWhispers", {
        ...existing,
        [userId]: checked,
      });
      this.render();
    });

    // GM disable toggle
    html.find(".ff-gm-disable").change(async (ev) => {
      const actorId = ev.currentTarget.dataset.actorId;
      const checked = ev.currentTarget.checked;
      const actor = game.actors.get(actorId);
      if (!actor) return;

      await actor.setFlag(MODULE_ID, "gmDisabled", checked);
      this.render();
    });
  }
}

/**
 * FormApplication for exporting PC actors as Narramancy JSON.
 */
class NarramancyExportMenu extends FormApplication {
  static get defaultOptions() {
    return foundry.utils.mergeObject(super.defaultOptions, {
      id: "narramancy-export",
      title: game.i18n.localize("NARRAMANCY.export.title"),
      template: `modules/${MODULE_ID}/templates/export-dialog.hbs`,
      width: 450,
      height: "auto",
    });
  }

  getData() {
    const characters = game.actors
      .filter((a) => a.type === "character" && (game.user.isGM || a.isOwner))
      .map((a) => {
        // Extract class and level from class items
        const classItem = a.items.find((i) => i.type === "class");
        return {
          id: a.id,
          name: a.name,
          class: classItem?.name || "Unknown",
          level: classItem?.system?.levels ?? a.system?.details?.level ?? "?",
        };
      });

    return {
      characters: characters,
      isEmpty: characters.length === 0,
      isGM: game.user.isGM,
    };
  }

  async _updateObject(event, formData) {
    // Handled by button click handlers
  }

  activateListeners(html) {
    super.activateListeners(html);

    html.find(".ff-export-character").click(async (ev) => {
      const actorId = ev.currentTarget.dataset.id;
      const actor = game.actors.get(actorId);
      if (!actor) return;

      const { exportCharacterToJSON } = await import("./exporter.js");
      await exportCharacterToJSON(actor);
    });

    html.find(".ff-export-all").click(async () => {
      const { exportAllCharacters } = await import("./exporter.js");
      await exportAllCharacters();
    });
  }
}
