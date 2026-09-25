# Note: "Signature Look & Motion" — a new flavor input

*From the DnD session-processing side, 2026-09-25 (Todd's call). A note for a future Narramancy session, not a commitment.*

## What's new

Every PC context file in the DnD workspace now ends with a player-facing section, `## Signature Look & Motion`. It records how the character's magic, weapons, features and body language **look and move**, and it's harvested from play every session.

Where the files live (the canonical root file is always the most recent one):

- AoA: `Q:/DnD/Absence of Alternatives/AoA_<Char>.md`
- Undermountain: `Q:/DnD/Undermountain/Active_Campaign/Campaign_Notes/Undermountain_<Char>.md`
- WBtW: `Q:/DnD/Order of the Hourglass - Wild Beyond the Witchlight/WBtW_<Char>.md`
- Dated snapshots such as `[Campaign]_[Char]_YYYY.MM.DD.md` sit in session folders. Use them for history, not for intake.

Shape of the section:

- Sub-groups (only the ones that apply): **Magic** · **Weapons & Gear** · **Features & Movement** · **Body Language & Presence**
- **Used a lot, barely described:** 3-5 abilities the character uses often but that have little visual description, each phrased as an invitation to the player
- Entries carry `<!-- src:MM.DD Lxxx -->` provenance comments. Strip them.

Backfill starts with the next processed sessions, so expect the section to be thin or missing on some files for a while.

## Why not just Narramancy Notes?

The existing Narramancy Notes input (the Foundry Tidy5e notes tab, `pc_parser.py::_extract_narramancy_notes`) depends on the player writing it. In the moment, most players don't know their own visual style. This section picks it up from what they actually **do** at the table, so nobody has to write anything. Both are inputs, and Narramancy Notes stays.

## Intake

1. As well as the Foundry JSON, find the **most recent** context file for the character.
2. `Signature Look & Motion` is the key section. Feed it into the flavor generation.
3. Use the rest of the file for **lookups**, not as wholesale tone: when a flavor line wants a specific object or history ("grandfather's staff", "boots from the dragon"), look it up there.
4. `generator.py` currently labels `--context` as "use ONLY for tone and personality". That framing fits the rest of the file but not this section, where concrete visual detail is exactly what we want. It needs revisiting.
5. Keep flavor lines short and punchy. The section gives you material; it doesn't change how long a whisper should be.

## The legend is the weighting

Every section opens with a one-line key. The markers can be combined:

| Marker | Meaning | Weight |
|---|---|---|
| plain | our synthesis from play | use freely |
| *italic* | the player's own words at the table | **honor first** — player-owned |
| **bold** | an explicit "Claude, note that…" call-out | **honor first** — the player asked for it |
| ~~struck~~ + new text | a superseded look (drift) | **never generate from the struck part** |

Struck lines are meant to be dropped at the 3rd fold-in after they're struck. That rule is **proposed, pending Todd's confirmation**, so a parser should handle struck lines whether they're there or not.

## Ideas for Narramancy (yours to decide)

### 1. Edge notes (general-purpose, not only tactical)

Small, ignorable text in the corner of a whisper or card, in a small font. It can ground the player or DM in a canon fact ("his grandfather's staff"), carry a reminder, or anything else that helps. Hovering shows a tooltip with a little more, and it's only there when you go looking.

- **Rule: don't overload.** The flavor line stays the focus. An edge note is a hint, not a second paragraph.
- Related: `docs/plan-reminders-layer.md` covers tactical reminders. This would add **lore** as a new category there, and the edge-note presentation could serve both.

### 2. Absent-player coverage

When a player is away and someone else (another player or the DM) runs their PC, temporarily turn on that PC's Narramancy for whoever is driving. It expires automatically when the owning player rejoins.
