import logging
import re

from cs_parser.db import RarityEnum

from .items_manager import ItemsManager
from .structs import *

class ItemsParser:
    def __init__(self) -> None:
        super().__init__()
        self.items_manager = ItemsManager()
        self.logger = logging.getLogger("ItemsParser")
        self.manual_changes()

        self.nonexisting_containers = {
            "crate_sticker_pack_broken_fang":           "Broken Fang Sticker Collection",
            "crate_patch_pack02":                       "Metal Skill Group Patch Collection",
            "crate_patch_pack03":                       "Operation Riptide Patch Collection",
            "crate_sticker_pack_op_riptide_capsule":    "Operation Riptide Sticker Collection",
            "crate_sticker_pack_recoil":                "Recoil Sticker Collection",
            "crate_sticker_pack_riptide_surfshop":      "Riptide Surf Shop Sticker Collection",
            "crate_sticker_pack_shattered_web":         "Shattered Web Sticker Collection",
        }
        self.tinted_graffities_limited = {
            "spray_std_heart": ["Bazooka Pink", "Blood Red", "Brick Red", "Desert Amber", "Dust Brown", "Monster Purple", "Princess Pink", "Tiger Orange", "Tracer Yellow", "War Pig Pink"],
            "spray_std2_lightbulb": ["Shark White", "Tracer Yellow"],
            "spray_std_piggles": ["Bazooka Pink", "Blood Red", "Brick Red", "Desert Amber", "Dust Brown", "Monster Purple", "Princess Pink", "Tiger Orange", "Tracer Yellow", "War Pig Pink"],
            "spray_std_hl_smiley": ["Battle Green", "Bazooka Pink", "Blood Red", "Brick Red", "Cash Green", "Desert Amber", "Dust Brown", "Frog Green", "Jungle Green", "Princess Pink", "Tiger Orange", "Tracer Yellow", "War Pig Pink"],
            "spray_std_moly": ["Bazooka Pink", "Blood Red", "Brick Red", "Desert Amber", "Dust Brown", "Monster Purple", "Princess Pink", "Tiger Orange", "Tracer Yellow", "War Pig Pink"],
            "spray_std_necklace_dollar": ["Battle Green", "Blood Red", "Cash Green", "Desert Amber", "Dust Brown", "Frog Green", "Jungle Green", "Monarch Blue", "Monster Purple", "Shark White", "Tiger Orange", "Tracer Yellow", "War Pig Pink", "Wire Blue"],
            "spray_std_salty": ["Shark White"],
            "spray_std_emo_happy": ["Battle Green", "Bazooka Pink", "Blood Red", "Brick Red", "Cash Green", "Desert Amber", "Dust Brown", "Frog Green", "Jungle Green", "Princess Pink", "Tiger Orange", "Tracer Yellow", "War Pig Pink"],
            "spray_std_dollar": ["Battle Green", "Cash Green", "Frog Green", "Jungle Green"]
        }

    # manual changes to items data done before parsing
    def manual_changes(self):
        pass

    def update_files(self):
        self.items_manager.update_files()
        self.manual_changes()

    # -------------------------------------- PUBLIC HELPERS -------------------------------------- #

    def get_lootlist_by_item_codename(self, codename: str) -> Lootlist | None:
        for lootlist in self.items_manager.lootlists:
            if codename in lootlist.items:
                return lootlist

        return None

    def get_collection_by_item_codename(self, codename: str) -> Collection | None:
        for collection in self.items_manager.collections:
            collection_items = map(lambda x: x.lower(), collection.items)
            if codename in collection_items:
                return collection

    # -------------------------------------- GETTERS -------------------------------------- #

    def get_skins(self):
        # One-off StatTrak containers that carry no keyed/volatile marker and
        # can't be detected structurally (the 2019 X-Ray P250 Package, prefab
        # plain "weapon_case_base"). Hardcoded like the knife case.
        special_stattrak_crates = {"crate_xray_p250"}

        def crate_produces_stattrak(crate: Item) -> bool:
            if crate.codename in special_stattrak_crates:
                return True
            # A crate produces StatTrak if it is a case you open, of which there
            # are two kinds:
            #   1. Keyed weapon cases: prefab "weapon_case" (a key via
            #      associated_items + tool.restriction).
            #   2. Self-opening volatile "Terminal" cases (e.g. Sealed Genesis
            #      Terminal): prefab is multi-token
            #      ("volatile_pricing weapon_case_selfopening_collection") so it
            #      doesn't resolve — identify these by the "volatile container"
            #      attribute instead.
            # This excludes the non-volatile self-opening store promo (Anubis
            # Collection Package), which hands out a collection for free with
            # neither a key nor the volatile marker, so it produces no StatTrak.
            if crate.prefab is not None:
                crate_prefabs = {crate.prefab.codename} | set(self.items_manager.get_prefab_tree(crate.prefab))
                if "weapon_case" in crate_prefabs:
                    return True
            return "volatile container" in crate.attributes

        def has_stattrak(item: Item, paintkit: Paintkit) -> bool:
            prefab_tree = self.items_manager.get_prefab_tree(item.prefab)
            if item.prefab is not None:
                prefab_tree = prefab_tree + [item.prefab.codename]

            # Gloves can never be StatTrak.
            if "hands_paintable" in prefab_tree:
                return False

            # Every knife can be StatTrak. (Knives are the rare items of keyed
            # cases but aren't linked to them in the game files, so they can't
            # be detected via the container discriminator below — hardcode them.)
            if "melee_unusual" in prefab_tree:
                return True

            # Regular weapon skins are StatTrak only when they drop from a case.
            # Check both the skin's collection crates and any loot-list
            # containers — the collection path catches skins whose loot-list
            # linkage is incomplete (e.g. PP-Bizon | Judgement of Anubis, from
            # Chroma 3 / set_community_12).
            target = f"[{paintkit.codename}]{item.codename}"
            for collection in self.items_manager.collections:
                if target in {i.lower() for i in collection.items}:
                    if any(crate_produces_stattrak(c) for c in collection.crates):
                        return True
            for lootlist in self.items_manager.lootlists:
                if target in lootlist.items:
                    if any(crate_produces_stattrak(c) for c in lootlist.containers):
                        return True

            return False

        def has_star_prefix(item: Item) -> bool:
            prefab_tree = self.items_manager.get_prefab_tree(item.prefab) + [item.prefab.codename]

            # gloves
            if "hands_paintable" in prefab_tree:
                return True

            # knives
            if "melee_unusual" in prefab_tree:
                return True

            return False

        def get_wear_variants(item: Item, paintkit: Paintkit) -> list[Variant]:
            wear_ranges = {
                "Factory New": [0.00, 0.07],
                "Minimal Wear": [0.07, 0.15],
                "Field-Tested": [0.15, 0.38],
                "Well-Worn": [0.38, 0.45],
                "Battle-Scarred": [0.45, 1.00]
            }

            item_name = self.items_manager.get_market_hash_name(item.name_tag)
            if paintkit.codename == "default":
                return [item_name]

            wear_remap_min = self.items_manager.get_paintkit("default").wear_remap_min
            wear_remap_max = self.items_manager.get_paintkit("default").wear_remap_max
            if paintkit.wear_remap_min is not None:
                wear_remap_min = paintkit.wear_remap_min
            if paintkit.wear_remap_max is not None:
                wear_remap_max = paintkit.wear_remap_max

            paintkit_name = get_paintkitname_fixed(paintkit)

            results = []
            for wear_name in wear_ranges:
                if float(wear_remap_min) < wear_ranges[wear_name][1] and float(wear_remap_max) > wear_ranges[wear_name][0]:
                    #fullname = f"{item_name} | {paintkit_name} ({wear_name})"
                    variant = Variant(f"{item_name} | {paintkit_name} ({wear_name})", 
                                      max(float(wear_remap_min), float(wear_ranges[wear_name][0])), 
                                      min(float(wear_remap_max), float(wear_ranges[wear_name][1])),
                                      wear_name, "Normal")
                    results.append(variant)

            return results

        @staticmethod
        def get_paintkitname_fixed(paintkit):
            paintkit_name = self.items_manager.get_market_hash_name(paintkit.name_tag)
            # fix doppler names
            doppler_tags = ["PaintKit_am_marbleized_Tag", "PaintKit_am_marbleized_g_Tag"]
            if paintkit.name_tag.lstrip("#") in doppler_tags:
                if "_sapphire_marbleized" in paintkit.codename:
                    paintkit_name = f"{paintkit_name} Sapphire"
                if "_blackpearl_marbleized" in paintkit.codename:
                    paintkit_name = f"{paintkit_name} Black Pearl"
                if "_ruby_marbleized" in paintkit.codename:
                    paintkit_name = f"{paintkit_name} Ruby"
                if "_emerald_marbleized" in paintkit.codename:
                    paintkit_name = f"{paintkit_name} Emerald"
                if "_phase" in paintkit.codename:
                    paintkit_name = f"{paintkit_name} Phase {paintkit.codename.split('_phase')[1][0]}"
            return paintkit_name

        def is_customizable(item: Item) -> bool:
            prefab_tree = self.items_manager.get_prefab_tree(item.prefab)
            for key in ["melee_unusual", "hands_paintable", "primary"]:
                if key in prefab_tree and item.baseitem != "1":
                    return True

            return False

        def find_rarity_group(loot_lists: dict, lootlist_key: str, crate_key: str, paintkit_codename: str) -> str | None:
            client_loot_lists = loot_lists[lootlist_key]
            if crate_key not in client_loot_lists and f"{crate_key}_lootlist" not in client_loot_lists:
                return None
            loot_list_entry = client_loot_lists.get(crate_key) or client_loot_lists.get(f"{crate_key}_lootlist")
            for sub_key, sub_value in loot_list_entry.items():
                if isinstance(sub_value, dict):
                    if any(item_key[1:item_key.index(']')] == paintkit_codename for item_key in client_loot_lists[sub_key]):
                        return sub_key
            for rarity in [r.value for r in RarityEnum]:
                rarity_key = f"{crate_key}_{rarity}"
                if rarity_key in client_loot_lists:
                    if any(item_key[1:item_key.index(']')] == paintkit_codename for item_key in client_loot_lists[rarity_key]):
                        return rarity
            return None

        results = {}
        self.logger.debug("Parsing skins...")
        for item in self.items_manager.items:
            for paintkit in self.items_manager.paintkits:
                skin_codename = f"{item.codename}_{paintkit.codename}"

                if paintkit.codename == "default":
                    skin_codename = item.codename
                    if not is_customizable(item):
                        continue

                if not self.items_manager.skin_exists(skin_codename):
                    continue

                lootlist = self.get_lootlist_by_item_codename(f"[{paintkit.codename}]{item.codename}")
                collection = self.get_collection_by_item_codename(f"[{paintkit.codename}]{item.codename}")

                # Skip unreleased "phantom" skins that have no source in the
                # current game data (no collection and no loot list) — a texture
                # exists so skin_exists() passes, but they were never in a case
                # or collection. Gold items (knives/gloves) are exempt: they are
                # legitimate case rare-items that never appear in a collection.
                if collection is None and lootlist is None and not has_star_prefix(item):
                    continue

                retrieved_collection_rarity = None
                for alias in (lootlist.aliases if lootlist is not None else set()) | ({collection.codename} if collection is not None else set()):
                    collection_rarity = find_rarity_group(self.items_manager.items_game, "client_loot_lists", alias, paintkit.codename) if collection is not None else None
                    if collection_rarity is not None:
                        retrieved_collection_rarity = collection_rarity
                        break

                variants = get_wear_variants(item, paintkit)

                # StatTrak and Souvenir are independent, distinct variant sets,
                # each derived from the base (Normal) wear variants. A skin may
                # have both, but there is never a combined "Souvenir StatTrak".
                base_variants = list(variants)

                if has_stattrak(item, paintkit):
                    variants += [Variant(f"StatTrak™ {variant.full_name}", variant.wear_from, variant.wear_to, variant.wear_name, "Stattrak")
                                 for variant
                                 in base_variants]

                # Every non-gold (regular weapon) skin can be Souvenir; gold
                # items (knives/gloves, i.e. has_star_prefix) never are. The
                # "default" (vanilla) paintkit yields no wear variants to derive.
                if paintkit.codename != "default" and not has_star_prefix(item):
                    variants += [Variant(f"Souvenir {variant.full_name}", variant.wear_from, variant.wear_to, variant.wear_name, "Souvenir")
                                 for variant
                                 in base_variants]

                if has_star_prefix(item):
                    # ★ is only a name decoration; the underlying kind
                    # (Normal / Stattrak / Souvenir) is preserved.
                    variants = [Variant(f"★ {variant.full_name}", variant.wear_from, variant.wear_to, variant.wear_name, variant.kind)
                                 for variant
                                 in variants]

                # self.logger.debug("Variants are: %s", variants)
                item_name = self.items_manager.get_market_hash_name(item.name_tag)
                paintkit_name = get_paintkitname_fixed(paintkit)

                results[f"{item_name} | {paintkit_name}"] = {
                        "item": item.asdict(),
                        "paintkit": paintkit.asdict(),
                        "collection_rarity": retrieved_collection_rarity,
                        "collection": None if collection is None else collection.asdict(),
                        "lootlist": None if lootlist is None else lootlist.asdict(), 
                        "variants": None if variants is None else [variant.asdict() for variant in variants]
                    }

        return results

    def get_stickers(self):
        results = {}
        for stickerkit in self.items_manager.stickerkits:
            if stickerkit.name_tag.startswith("#StickerKit"):
                sticker_name = self.items_manager.get_market_hash_name(stickerkit.name_tag)
                market_hash_name = f"Sticker | {sticker_name}"
                results[market_hash_name] = {"stickerkit": stickerkit.asdict()}

        return results

    def get_patches(self):
        results = {}
        for stickerkit in self.items_manager.stickerkits:
            if stickerkit.name_tag.startswith("#PatchKit"):
                sticker_name = self.items_manager.get_market_hash_name(stickerkit.name_tag)
                market_hash_name = f"Patch | {sticker_name}"
                results[market_hash_name] = {"stickerkit": stickerkit.asdict()}

        return results

    def get_graffities(self):
        def get_variants(stickerkit: Stickerkit) -> list[str]:
            variants = []
            stickerkit_name = self.items_manager.get_market_hash_name(stickerkit.name_tag)
            if not stickerkit.name_tag.startswith("#SprayKit_std"):
                return [f"Sealed Graffiti | {stickerkit_name}"]

            if stickerkit.codename in self.tinted_graffities_limited:
                for tint_name in self.tinted_graffities_limited[stickerkit.codename]:
                    variants.append(f"Sealed Graffiti | {stickerkit_name} ({tint_name})")

            else:
                for graffiti_tint in self.items_manager.graffiti_tints:
                    tint_name = self.items_manager.get_market_hash_name(graffiti_tint.name_tag)
                    variants.append(f"Sealed Graffiti | {stickerkit_name} ({tint_name})")

            return variants

        results = {}
        for stickerkit in self.items_manager.stickerkits:
            if stickerkit.name_tag.startswith("#SprayKit"):
                variants = get_variants(stickerkit)
                for variant in variants:
                    results[variant] = {"stickerkit": stickerkit.asdict()}

        return results

    def get_musickits(self):
        results = {}
        lootlist_regex = r'\[(.*?)\](.*?)$'
        for lootlist in self.items_manager.lootlists:
            for lootlist_item in lootlist.items:
                if lootlist.codename == "crate_musickit_radicals_stattrak_capsule_lootlist":
                    pass
                match = re.search(lootlist_regex, lootlist_item)
                if match is not None:
                    item_cdn, itemtype_cdn = match.groups()
                    if itemtype_cdn == "musickit":
                        item = self.items_manager.get_item(itemtype_cdn)
                        musicdef = self.items_manager.get_musicdef(item_cdn)

                        item_name = self.items_manager.get_market_hash_name(item.name_tag)
                        musicdef_name = self.items_manager.get_market_hash_name(musicdef.name_tag)

                        market_hash_name = f"{item_name} | {musicdef_name}"
                        results[market_hash_name] = {"item": item.asdict(), "musicdef": musicdef.asdict()}
                        for alias in lootlist.aliases:
                            if "stattrak" in alias:
                                market_hash_name = f"StatTrak™ {market_hash_name}"
                                results[market_hash_name] = {"item": item.asdict(), "musicdef": musicdef.asdict()}
                                break

        return results

    def get_keychains(self):
        results = {}
        lootlist_regex = r'\[(.*?)\](.*?)$'
        for lootlist in self.items_manager.lootlists:
            for lootlist_item in lootlist.items:
                match = re.search(lootlist_regex, lootlist_item)
                if match is not None:
                    item_cdn, itemtype_cdn = match.groups()
                    if itemtype_cdn == "keychain":
                        item = self.items_manager.get_item(itemtype_cdn)
                        keychain = self.items_manager.get_keychain(item_cdn)

                        item_name = self.items_manager.get_market_hash_name(item.name_tag)
                        keychain_name = self.items_manager.get_market_hash_name(keychain.name_tag)

                        market_hash_name = f"{item_name} | {keychain_name}"
                        results[market_hash_name] = {"item": item.asdict(), "keychain": keychain.asdict()}

        return results

    def get_agents(self):
        results = {}
        for item in self.items_manager.items:
            if item.prefab is not None:
                if item.prefab.codename == "customplayertradable":
                    item_name = self.items_manager.get_market_hash_name(item.name_tag)
                    results[item_name] = {"item": item.asdict()}

        return results

    def get_containers(self):
        results = {}
        for lootlist in self.items_manager.lootlists:
            for container in lootlist.containers:
                if container.codename in self.nonexisting_containers:
                    continue
                container_name = self.items_manager.get_market_hash_name(container.name_tag)
                results[container_name] = {"lootlist": lootlist.asdict_cont(), "container": container.asdict()}

        return results

    def get_container_keys(self):
        results = {}
        for item in self.items_manager.items:
            if item.prefab is None:
                continue
            if item.prefab.codename == "weapon_case_key" and "restriction" in item.tool:
                item_name = self.items_manager.get_market_hash_name(item.name_tag)
                results[item_name] = {"item": item.asdict()}

        return results

    def get_pins(self):
        results = {}
        for item in self.items_manager.items:
            if item.prefab is None:
                continue
            if item.prefab.codename == "commodity_pin":
                item_name = self.items_manager.get_market_hash_name(item.name_tag)
                results[item_name] = {"item": item.asdict()}

        return results

    def get_passes(self):
        results = {}
        for item in self.items_manager.items:
            if item.prefab is None:
                continue

            prefab_tree = self.items_manager.get_prefab_tree(item.prefab)
            if "season_pass" in prefab_tree:
                item_name = self.items_manager.get_market_hash_name(item.name_tag)
                results[item_name] = {"item": item.asdict()}

            if "fan_token" in prefab_tree:
                if item.codename.endswith("_pack"):
                    continue
                if item.codename.endswith("_charge"):
                    continue
                item_name = self.items_manager.get_market_hash_name(item.name_tag)
                results[item_name] = {"item": item.asdict()}

        return results