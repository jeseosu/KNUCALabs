"""Предмети: опис з JSON та кешований доступ до них."""
from dataclasses import dataclass, field
from functools import lru_cache

from game.config import load_json

STACKABLE_KINDS = {"consumable", "material"}


@lru_cache(maxsize=1)
def _data() -> dict:
    return load_json("items.json")


def rarity_defs() -> dict:
    return _data()["rarities"]


def slot_names() -> dict:
    return _data()["slots"]


def starting_kit(class_id: str) -> dict:
    return _data()["starting_kits"].get(class_id, {})


def all_item_ids() -> list[str]:
    return list(_data()["items"])


@dataclass(frozen=True, eq=False)
class Item:
    """Незмінний опис предмета. Один і той самий об'єкт використовується скрізь."""
    id: str
    name: str
    kind: str                      # weapon / armor / consumable / material
    rarity: str = "common"
    value: int = 0
    desc: str = ""
    slot: str | None = None        # куди одягається (для зброї та броні)
    level_req: int = 1
    classes: tuple = ()            # порожньо = підходить усім
    stats: dict = field(default_factory=dict)    # attack / defense / crit
    effect: dict = field(default_factory=dict)   # heal / mana

    @property
    def stackable(self) -> bool:
        return self.kind in STACKABLE_KINDS

    @property
    def equippable(self) -> bool:
        return self.slot is not None

    @property
    def color(self) -> str:
        return rarity_defs()[self.rarity]["color"]

    @property
    def rarity_name(self) -> str:
        return rarity_defs()[self.rarity]["name"]

    @property
    def rank(self) -> int:
        """Номер рідкості: 0 - звичайний ... 4 - легендарний."""
        return list(rarity_defs()).index(self.rarity)

    @property
    def score(self) -> float:
        """Груба «цінність» екіпіровки для порівняння."""
        s = self.stats
        return s.get("attack", 0) + s.get("defense", 0) + s.get("crit", 0) * 100


@lru_cache(maxsize=None)
def get_item(item_id: str) -> Item:
    raw = _data()["items"].get(item_id)
    if raw is None:
        raise KeyError(f"Невідомий предмет: {item_id}")
    return Item(
        id=item_id,
        name=raw["name"],
        kind=raw["kind"],
        rarity=raw.get("rarity", "common"),
        value=raw.get("value", 0),
        desc=raw.get("desc", ""),
        slot=raw.get("slot"),
        level_req=raw.get("level_req", 1),
        classes=tuple(raw.get("classes", ())),
        stats=raw.get("stats", {}),
        effect=raw.get("effect", {}),
    )