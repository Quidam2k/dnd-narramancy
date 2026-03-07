/**
 * Utility functions for Flavor Forge module.
 */

/**
 * Test if a token name matches a wildcard pattern.
 * Pattern uses * as wildcard (e.g., "*Drow Elite Warrior*" matches "Fierce Drow Elite Warrior").
 * Matching is case-insensitive.
 *
 * @param {string} pattern - Wildcard pattern (e.g., "*Goblin*")
 * @param {string} name - Token name to test
 * @returns {boolean}
 */
export function wildcardMatch(pattern, name) {
  // Escape regex special chars except *, then replace * with .*
  const escaped = pattern.replace(/([.+?^${}()|[\]\\])/g, "\\$1");
  const regexStr = "^" + escaped.replace(/\*/g, ".*") + "$";
  return new RegExp(regexStr, "i").test(name);
}

/**
 * Create a URL-safe slug from a creature name.
 * @param {string} name
 * @returns {string}
 */
export function slugify(name) {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/**
 * Build the full Foundry table name from creature name, ability, and category.
 * @param {string} creatureName
 * @param {string} ability
 * @param {string} category - "attempts", "successes", or "failures"
 * @returns {string}
 */
export function tableName(creatureName, ability, category) {
  const label = category.charAt(0).toUpperCase() + category.slice(1);
  return `${creatureName} - ${ability} - ${label}`;
}

/**
 * Resolve a table key ("Shortsword|attempts") to a full Foundry table name.
 * @param {string} creatureName
 * @param {string} tableKey - "ability|category"
 * @returns {string}
 */
export function resolveTableKey(creatureName, tableKey) {
  const [ability, category] = tableKey.split("|");
  return tableName(creatureName, ability, category);
}
