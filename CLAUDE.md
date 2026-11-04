# CLAUDE.md

Guidance for working in this repository.

## What this is

A Python CLI that fetches Counter-Strike 2 item definitions from Valve's game
files (mirrored by the SteamDatabase/GameTracking-CS2 GitHub repo), parses them
into typed objects, and emits either a market-hash-name-keyed JSON blob or rows
in a PostgreSQL database. The JSON is the input for the sibling project
`surveillance_backend` (a FastAPI market tracker), which reads the same
`paintkits` / `collections` / `paintkit_variants` tables this tool writes.

## Running

```bash
python -m cs_parser -t all -o output.json          # parse everything to JSON (pretty by default)
python -m cs_parser -t skins -o skins.json         # one category
python -m cs_parser -t skins --db                  # write skins to PostgreSQL instead of JSON
python -m cs_parser -t skins --db --db-url postgresql://user:pass@host:5432/cs
python -m cs_parser -t all -v                       # verbose (DEBUG logging)
```

`-t/--type` choices: `all, skins, stickers, patches, graffities, musickits,
agents, containers, container_keys, pins, passes, keychains`.

Every run calls `update_files()`, which makes 3 live HTTP requests to raw
GitHub for `items_game.txt`, `csgo_english.txt`, and `pak01_dir.txt`. There is
no caching — the tool needs network access and is subject to GitHub's mirror
being up to date.

`--db` only supports the `skins` data (`save_skins_to_db` in `db.py`); other
categories are JSON-only.

### Note on packaging

`pyproject.toml` is stale relative to the real layout: it declares
`where = ["src"]` and entry point `cs_parser.cli:main`, but the actual package
lives at repo root (`cs_parser/`) and its entry point is `cs_parser/__main__.py`
(`main`). There is no `cs_parser/cli.py` in the live tree (only an old copy
under `build/lib/`). **Run via `python -m cs_parser`, not the `cs-parser`
console script**, unless you fix the packaging first.

## Architecture

Three layers, each wrapping the one below:

1. **`ItemsManager`** (`items_manager.py`) — the heavy lifter.
   - `update_files()`: downloads the 3 files, VDF-parses `items_game.txt`,
     builds a lowercased translation-token dict from `csgo_english.txt`, and
     regex-extracts the set of skin CDN codenames from `pak01_dir.txt`.
   - `__preprocess()`: mutates the raw VDF in place — deletes bulky unused
     sections, merges duplicate root keys, **swaps index-keyed maps to
     name-keyed** (`items`, `sticker_kits`, `paint_kits`, `music_definitions`,
     `attributes`, `keychain_definitions`), and strips references to
     nonexistent prefabs.
   - `parse()`: turns each VDF section into `structs/` objects, resolving
     cross-references (prefab inheritance trees, quality/rarity, attribute
     defaults, lootlist ↔ collection ↔ crate linkage). `parse_lootlists()` is
     the most intricate: it inlines sublists, gathers seasonal/revolving loot
     lists, computes alias sets, and attaches items + containers.
   - Lookups are linear `get_*(codename)` scans over lists (O(n) each); fine for
     the data size, but the skins loop is inherently O(items × paintkits).

2. **`ItemsParser`** (`items_parser.py`) — presentation/business logic on top of
   a manager. The `get_<category>()` methods produce the final
   market-hash-name-keyed dicts. `get_skins()` is the core: it pairs every item
   with every paintkit, filters to combinations that actually exist
   (`skin_exists`), computes wear-range `Variant`s, and applies StatTrak™ /
   Souvenir / ★ (Star) prefixes based on prefab trees and collection membership.
   Hardcoded correction tables live in `__init__` (`souvenir_collections`,
   `blank_collections`, `nonexisting_containers`, `tinted_graffities_limited`)
   to patch known gaps/quirks in Valve's data.

3. **`__main__.py`** — argparse CLI; dispatches to the right `get_*` method(s)
   and writes JSON, or routes `--db` to `save_skins_to_db`.

### Structs (`cs_parser/structs/`)

Plain classes extending `Base` (which provides `codename`, `asdict()`, `__eq__`
by codename, JSON `__repr__`). `asdict()` on each struct is what defines the
JSON output shape — change output by editing these. Key ones: `Item`,
`Paintkit`, `Prefab` (has a nested `prefabs` inheritance chain), `Collection`,
`Lootlist`, `Stickerkit`, `Musicdef`, `Keychain`, `Variant` (one wear/finish
row), plus value types `Rarity`, `Quality`, `Color`, `GraffitiTint`,
`Attribute`.

### Database (`cs_parser/db.py`)

SQLModel schema: `paintkits`, `collections`, `paintkit_collections`,
`paintkit_variants`. Each table's string PK is supplemented with a serial `id`
column appended via `_tbl.append_column(...)` **outside the ORM mapper** (so
`merge()` never touches it but `create_all()` still emits it as an identity
column) — keep that pattern if you add tables. Enums: `RarityEnum`,
`WearKindEnum`, `ItemKindEnum`, `VariantKindEnum`. `save_skins_to_db()` uses
`session.merge()` (upsert-by-PK) and **skips Souvenir variants** (only Normal /
Stattrak / Star are mapped). This schema is mirrored — with slight divergence —
in `surveillance_backend/app/models/shared.py`; changing one usually means
changing the other.

## Conventions & gotchas

- "codename" throughout means the internal Valve identifier (e.g.
  `weapon_deagle`, `hy_ddpat_urb`); "name_tag" is a `#Token` that resolves to a
  human name via `get_market_hash_name()` / the `tokens` dict. Final dict keys
  are market hash names (e.g. `Desert Eagle | Urban DDPAT`).
- VDF parsing uses the `vdf` library with `VDFDict`; preprocessing relies on
  its duplicate-key APIs (`get_all_for`, `remove_all_for`) and positional key
  tuples like `item_data[(0, "prefab")]`. Be careful editing preprocessing —
  order matters (`__swap_keys` must run before code that indexes by name).
- Output files (`*.json`) are gitignored; the committed `output.json` /
  `output-containers.json` are large sample snapshots, not build artifacts to
  regenerate on every change.
- No test suite and no linter config are present. Verify changes by running the
  parser and diffing the JSON output.
- Windows dev environment; a `.venv` exists at repo root
  (`.venv/Scripts/python.exe`).
