"""Зони світу, біоми, план міста Ельдорія та скарби в хатинах."""
import math

from game.items import loot
from game.items.item import get_item

TOWN_NAME = "Ельдорія"
TOWN_HALF_W = 22          # місто 45 x 21 клітинок навколо центру світу
TOWN_HALF_H = 10
BUILDING_W = 9
BUILDING_H = 5
BIOME_START = 40          # ближче цієї відстані від міста лише зелені землі

# (тип, текст вивіски (до 7 літер), зсув по X від центру, ряд відносно головної вулиці)
TOWN_LAYOUT = [
    ("blacksmith", "Кузня",   -20, "north"),
    ("shop",       "Лавка",   -10, "north"),
    ("tavern",     "Таверна",   2, "north"),
    ("guild",      "Гільдія",  12, "north"),
    ("alchemist",  "Алхімік", -20, "south"),
    ("temple",     "Храм",    -10, "south"),
    ("auction",    "Аукціон",   2, "south"),
    ("elder",      "Мерія",    12, "south"),
]

# базовий тайл кожного біому
BIOME_BASE = {"green": ".", "desert": ":", "snow": ";", "swamp": "&"}

# (до якої відстані від міста, назва зони, підказка)
RINGS = [
    (35, "Околиці Ельдорії", "рівні 1-3"),
    (65, "Дикі землі", "рівні 3-6"),
    (100, "Темні пущі", "рівні 6-9"),
    (10 ** 9, "Край світу", "рівні 9+"),
]

BIOME_ZONES = {
    "green": RINGS,
    "desert": [(65, "Піщані рівнини", "рівні 4-6"),
               (110, "Червоні пустки", "рівні 6-9"),
               (10 ** 9, "Серце пустелі", "рівні 9+")],
    "snow": [(65, "Засніжені луки", "рівні 5-7"),
             (110, "Крижана тундра", "рівні 7-9"),
             (10 ** 9, "Вічна мерзлота", "рівні 9+")],
    "swamp": [(65, "Туманні болота", "рівні 3-6"),
              (110, "Гнилі трясовини", "рівні 6-9"),
              (10 ** 9, "Чорна твань", "рівні 9+")],
}


def danger_distance(tilemap, x: int, y: int) -> float:
    """Відстань від центру світу (по Y множимо на 2, бо клітинки вищі за ширину)."""
    sx, sy = tilemap.spawn
    return math.hypot(x - sx, (y - sy) * 2)


def biome_of(x: int, y: int, cx: int, cy: int, phase: tuple[float, float]) -> str:
    """Біом клітинки: сектори навколо міста з плавно викривленими межами.
    Схід - пустеля, південь - болота, північ - сніг, захід - зелені землі."""
    dx, dy = x - cx, (y - cy) * 2
    dist = math.hypot(dx, dy)
    raw = math.atan2(dy, dx)
    if dist < BIOME_START + 6 * math.sin(raw * 3 + phase[0]):
        return "green"
    angle = raw + 0.45 * math.sin(dist / 11 + phase[0]) + 0.35 * math.sin(x / 17 + y / 9 + phase[1])
    angle = (angle + math.pi) % (2 * math.pi) - math.pi
    if -math.pi / 4 <= angle < math.pi / 4:
        return "desert"
    if math.pi / 4 <= angle < 3 * math.pi / 4:
        return "swamp"
    if -3 * math.pi / 4 <= angle < -math.pi / 4:
        return "snow"
    return "green"


def biome_at(tilemap, x: int, y: int) -> str:
    cx, cy = tilemap.spawn
    return biome_of(x, y, cx, cy, tilemap.biome_phase)


def zone_info(tilemap, x: int, y: int) -> tuple[str, str]:
    """Повертає (назва зони, підказка) для клітинки."""
    if tilemap.kind == "dungeon":
        return tilemap.name, tilemap.hint
    if tilemap.is_safe(x, y):
        return TOWN_NAME, "безпечна зона"
    dist = danger_distance(tilemap, x, y)
    table = BIOME_ZONES.get(biome_at(tilemap, x, y), RINGS)
    for limit, name, hint in table:
        if dist < limit:
            return name, hint
    return table[-1][1], table[-1][2]


def populate_huts(state) -> None:
    """Кладе скарби в хатинки за межами міста: стимул досліджувати світ."""
    tilemap, rng, player = state.tilemap, state.rng, state.player
    for x, y, w, h in tilemap.huts:
        if rng.random() > 0.7:
            continue
        px, py = x + w // 2, y + h // 2
        level = max(1, int(danger_distance(tilemap, px, py) / 12))

        pile = loot.LootPile(px, py, gold=rng.randint(5 + level * 4, 15 + level * 10),
                             born=10 ** 9)          # скарб у хатині не зникає
        if rng.random() < 0.6:
            potion = ("health_potion_small" if level < 4
                      else "health_potion" if level < 8 else "health_potion_big")
            pile.add_item(get_item(potion), 1)
        if rng.random() < 0.3:
            gear = loot.roll_gear(level, player.class_id, rng)
            if gear:
                pile.add_item(gear, 1)
        state.piles[(px, py)] = pile