"""Крафт: рецепти з recipes.json, перевірки та створення предметів."""
from functools import lru_cache

from game.config import load_json
from game.items.item import get_item


@lru_cache(maxsize=1)
def _data() -> dict:
    return load_json("recipes.json")


def recipes() -> list[dict]:
    return _data()["recipes"]


def stations() -> dict[str, str]:
    return _data()["stations"]


def station_title(station: str) -> str:
    return stations().get(station, station)


def recipes_for(station: str, class_id: str) -> list[dict]:
    """Рецепти станції; зброя й броня чужого класу не показуються."""
    result = []
    for recipe in recipes():
        if recipe["station"] != station:
            continue
        item = get_item(recipe["output"][0])
        if item.classes and class_id not in item.classes:
            continue
        result.append(recipe)
    return result


def can_craft(state, recipe: dict) -> tuple[bool, str]:
    p = state.player
    if p.level < recipe.get("level_req", 1):
        return False, f"Потрібен {recipe['level_req']} рівень."
    for item_id, need in recipe["inputs"]:
        if p.inventory.count(item_id) < need:
            return False, "Не вистачає матеріалів."
    if p.gold < recipe.get("gold", 0):
        return False, "Не вистачає золота."
    return True, ""


def craft(state, recipe: dict) -> tuple[bool, str]:
    ok, reason = can_craft(state, recipe)
    if not ok:
        return False, reason

    p, inv = state.player, state.player.inventory
    out_id, out_count = recipe["output"]
    out_item = get_item(out_id)

    for item_id, need in recipe["inputs"]:
        inv.remove_by_id(item_id, need)
    if inv.free_space_for(out_item) < out_count:      # відкат, якщо немає місця
        for item_id, need in recipe["inputs"]:
            inv.add(get_item(item_id), need)
        return False, "Рюкзак повний!"

    p.gold -= recipe.get("gold", 0)
    inv.add(out_item, out_count)
    suffix = f" x{out_count}" if out_count > 1 else ""
    return True, f"Створено: {out_item.name}{suffix}."