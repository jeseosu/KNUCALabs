"""Здобич: золото, випадкові предмети та купки здобичі на землі."""
from dataclasses import dataclass, field
from functools import lru_cache

from game.config import PILE_LIFETIME, load_json
from game.items.item import Item, all_item_ids, get_item, rarity_defs


@lru_cache(maxsize=1)
def loot_defs() -> dict:
    return load_json("loot.json")


@lru_cache(maxsize=1)
def _gear_items() -> tuple[Item, ...]:
    """Усі предмети, які можна одягнути (пул для випадкового дропу)."""
    items = (get_item(item_id) for item_id in all_item_ids())
    return tuple(item for item in items if item.equippable)


@dataclass
class LootPile:
    """Купка здобичі на землі. Підбирається, коли стаєш на неї."""
    x: int
    y: int
    gold: int = 0
    items: list[tuple[Item, int]] = field(default_factory=list)
    born: int = 0

    @property
    def is_empty(self) -> bool:
        return self.gold == 0 and not self.items

    @property
    def glyph(self) -> str:
        return "%" if self.items else "$"

    @property
    def color(self) -> str:
        if not self.items:
            return "gold"
        best = max((item for item, _ in self.items), key=lambda it: it.rank)
        return best.color

    def add_item(self, item: Item, count: int = 1) -> None:
        if item.stackable:
            for i, (other, other_count) in enumerate(self.items):
                if other.id == item.id:
                    self.items[i] = (other, other_count + count)
                    return
        self.items.append((item, count))


def roll_gear(level: int, player_class: str, rng, min_rank: int = 0) -> Item | None:
    """Випадкова екіпіровка: спершу обираємо рідкість, потім сам предмет.
    min_rank: мінімальна рідкість (0 звичайний ... 4 легендарний), для босів."""
    cfg = loot_defs()["gear"]
    low, high = cfg["level_window"]
    pool = [it for it in _gear_items() if level + low <= it.level_req <= level + high]
    if not pool:
        return None
    if min_rank:
        better = [it for it in pool if it.rank >= min_rank]
        if better:
            pool = better

    by_rarity: dict[str, list[Item]] = {}
    for item in pool:
        by_rarity.setdefault(item.rarity, []).append(item)

    rarities = rarity_defs()
    names = list(by_rarity)
    rarity = rng.choices(names, weights=[rarities[n]["weight"] for n in names])[0]

    candidates = by_rarity[rarity]
    # зброя чужого класу випадає рідше
    weights = [1.0 if (not it.classes or player_class in it.classes)
               else cfg["off_class_weight"] for it in candidates]
    return rng.choices(candidates, weights=weights)[0]


def roll_loot(monster, player, rng) -> tuple[int, list[tuple[Item, int]]]:
    """Кидає кубики здобичі. Повертає (золото, список (предмет, кількість))."""
    table = loot_defs()["monsters"].get(monster.monster_id)
    if table is None:
        return 0, []

    gold = rng.randint(*table["gold"]) if table.get("gold") else 0
    items: list[tuple[Item, int]] = []
    for item_id, chance in table.get("drops", []):
        if rng.random() < chance:
            items.append((get_item(item_id), 1))

    for _ in range(table.get("gear_rolls", 1)):       # боси кидають кілька разів
        if rng.random() < table.get("gear_chance", 0):
            gear = roll_gear(monster.level, player.class_id, rng,
                             table.get("gear_min_rank", 0))
            if gear:
                items.append((gear, 1))
    return gold, items


def drop_loot(state, monster) -> None:
    """Створює купку здобичі на місці смерті монстра."""
    gold, items = roll_loot(monster, state.player, state.rng)
    if gold == 0 and not items:
        return

    pos = (monster.x, monster.y)
    pile = state.piles.get(pos)
    if pile is None:
        pile = LootPile(monster.x, monster.y, born=state.turn)
        state.piles[pos] = pile
    pile.gold += gold
    for item, count in items:
        pile.add_item(item, count)

    if any(item.rank >= 2 for item, _ in items):
        state.log("Щось рідкісне блищить на землі!")


def pick_up(state, x: int, y: int) -> bool:
    """Підбирає здобич на клітинці. Повертає True, якщо щось узято."""
    pile = state.piles.get((x, y))
    if pile is None:
        return False

    player = state.player
    taken: list[str] = []

    if pile.gold:
        player.gold += pile.gold
        taken.append(f"{pile.gold} золота")
        pile.gold = 0

    remaining: list[tuple[Item, int]] = []
    for item, count in pile.items:
        added = player.inventory.add(item, count)
        if added:
            taken.append(item.name + (f" x{added}" if added > 1 else ""))
        if added < count:
            remaining.append((item, count - added))
    pile.items = remaining

    if taken:
        state.log("Ти підбираєш: " + ", ".join(taken) + ".")
    if remaining:
        state.log("Рюкзак повний! Частину здобичі залишено на землі.")
    if pile.is_empty:
        del state.piles[(x, y)]
    return bool(taken)


def expire_piles(state) -> None:
    """Стара здобич зникає, щоб світ не засмічувався."""
    old = [pos for pos, pile in state.piles.items()
           if state.turn - pile.born > PILE_LIFETIME]
    for pos in old:
        del state.piles[pos]