"""Підземелля: генерація кімнат і коридорів, монстри, бос і скарби."""
import math
from dataclasses import dataclass
from functools import lru_cache

from game.config import load_json
from game.entities.monster import Monster
from game.items import loot
from game.items.item import get_item
from game.world.tilemap import TileMap

NEVER_EXPIRES = 10 ** 9     # "народилась" у далекому майбутньому: скарб не зникає


@lru_cache(maxsize=1)
def dungeon_defs() -> dict:
    return load_json("dungeons.json")


@dataclass
class Room:
    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2

    def overlaps(self, other: "Room", margin: int = 1) -> bool:
        return not (self.x + self.w + margin <= other.x or
                    other.x + other.w + margin <= self.x or
                    self.y + self.h + margin <= other.y or
                    other.y + other.h + margin <= self.y)

    def tiles(self) -> list[tuple[int, int]]:
        return [(x, y) for y in range(self.y, self.y + self.h)
                for x in range(self.x, self.x + self.w)]


# ---------- генерація плану ----------
def _carve_h(grid, x1: int, x2: int, y: int) -> None:
    for x in range(min(x1, x2), max(x1, x2) + 1):
        grid[y][x] = ","


def _carve_v(grid, y1: int, y2: int, x: int) -> None:
    for y in range(min(y1, y2), max(y1, y2) + 1):
        grid[y][x] = ","


def _corridor(grid, a: tuple[int, int], b: tuple[int, int], rng) -> None:
    """Коридор у формі літери L: або спершу горизонтально, або спершу вертикально."""
    (x1, y1), (x2, y2) = a, b
    if rng.random() < 0.5:
        _carve_h(grid, x1, x2, y1)
        _carve_v(grid, y1, y2, x2)
    else:
        _carve_v(grid, y1, y2, x1)
        _carve_h(grid, x1, x2, y2)


def _generate_layout(width: int, height: int, room_count: int, rng):
    """Повертає (сітка, список кімнат). Усі кімнати з'єднані між собою."""
    grid, rooms = [], []
    for _ in range(50):                      # кілька спроб, поки не вийде достатньо кімнат
        grid = [["#"] * width for _ in range(height)]
        rooms = []
        for _ in range(300):
            if len(rooms) >= room_count:
                break
            w, h = rng.randint(5, 12), rng.randint(4, 7)
            x = rng.randint(1, width - w - 2)
            y = rng.randint(1, height - h - 2)
            room = Room(x, y, w, h)
            if not any(room.overlaps(other) for other in rooms):
                rooms.append(room)
        if len(rooms) >= max(4, room_count - 3):
            break

    for room in rooms:
        for x, y in room.tiles():
            grid[y][x] = ","

    # кожну нову кімнату з'єднуємо з найближчою з попередніх: граф зв'язний
    for i in range(1, len(rooms)):
        a = rooms[i]
        b = min(rooms[:i], key=lambda r: math.dist(r.center, a.center))
        _corridor(grid, a.center, b.center, rng)
    for _ in range(2):                        # кілька зайвих коридорів - петлі
        a, b = rng.sample(rooms, 2)
        _corridor(grid, a.center, b.center, rng)
    return grid, rooms


# ---------- наповнення ----------
def build_level(state, dungeon_id: str):
    """Створює підземелля. Повертає (tilemap, entities, piles)."""
    cfg = dungeon_defs()[dungeon_id]
    rng = state.rng
    width, height = cfg["size"]

    grid, rooms = _generate_layout(width, height, cfg["rooms"], rng)
    start = rooms[0]
    # бос у найдальшій від входу кімнаті
    boss_room = max(rooms[1:], key=lambda r: math.dist(r.center, start.center))

    sx, sy = start.center
    grid[sy][sx] = "<"
    tilemap = TileMap(grid, spawn=(sx + 1, sy), name=cfg["name"], kind="dungeon")
    tilemap.vision = cfg.get("vision", 6)
    tilemap.hint = f"рекомендований рівень {cfg['level_hint']}"
    tilemap.portals[(sx, sy)] = "exit"

    entities: list = []
    piles: dict = {}
    taken = {(sx, sy), (sx + 1, sy)}

    def free_tile(room: Room):
        options = [t for t in room.tiles() if t not in taken]
        if not options:
            return None
        tile = rng.choice(options)
        taken.add(tile)
        return tile

    ids = [mid for mid, _ in cfg["monsters"]]
    weights = [w for _, w in cfg["monsters"]]

    for room in rooms:
        if room is start:
            continue

        if room is boss_room:
            bx, by = room.center
            taken.add((bx, by))
            entities.append(Monster(cfg["boss"], bx, by))
            for guard_id in cfg["guards"]:
                pos = free_tile(room)
                if pos:
                    entities.append(Monster(guard_id, *pos))
            continue

        count = rng.randint(*cfg["per_room"]) + (1 if len(room.tiles()) >= 50 else 0)
        for _ in range(count):
            pos = free_tile(room)
            if pos:
                entities.append(Monster(rng.choices(ids, weights=weights)[0], *pos))

        if rng.random() < cfg["treasure_chance"]:
            pos = free_tile(room)
            if pos:
                piles[pos] = _make_treasure(state, cfg, pos)

    return tilemap, entities, piles


def _make_treasure(state, cfg: dict, pos: tuple[int, int]) -> loot.LootPile:
    rng = state.rng
    pile = loot.LootPile(pos[0], pos[1], gold=rng.randint(*cfg["treasure_gold"]),
                         born=NEVER_EXPIRES)
    if rng.random() < 0.5:
        pile.add_item(get_item("health_potion"), 1)
    if rng.random() < 0.3:
        pile.add_item(get_item("mana_potion"), 1)
    if rng.random() < 0.35:
        gear = loot.roll_gear(cfg["level_hint"], state.player.class_id, rng)
        if gear:
            pile.add_item(gear, 1)
    return pile