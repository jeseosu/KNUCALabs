"""Процедурна генерація світу: біоми, ліси, озера, гори, місто, входи в підземелля, хатини."""
import math
import random

from game.world import zones
from game.world.dungeon import dungeon_defs
from game.world.tilemap import Building, TileMap

BIOMES = tuple(zones.BIOME_BASE)

# біом -> (символ, щільність)
GRASS = {"green": ('"', 0.85), "swamp": ('"', 0.7)}
FORESTS = {"green": ("T", 0.55), "desert": ("Y", 0.12), "snow": ("A", 0.6), "swamp": ("T", 0.45)}
LAKES = {b: ("~", 1.0) for b in BIOMES}
MOUNTAINS = {b: ("^", 1.0) for b in BIOMES}
# поодинокі "дерева" на базовому тайлі: тайл -> (символ, шанс)
SINGLES = {".": ("T", 0.03), ":": ("Y", 0.012), ";": ("A", 0.03), "&": ("T", 0.03)}


def _blob(grid, rng, cx, cy, rx, ry, char, density=1.0):
    """Малює неправильну еліптичну пляму (ліс, озеро, гори)."""
    height, width = len(grid), len(grid[0])
    for y in range(cy - ry, cy + ry + 1):
        for x in range(cx - rx, cx + rx + 1):
            if not (0 <= x < width and 0 <= y < height):
                continue
            dist = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if dist <= 1 + rng.uniform(-0.3, 0.3) and rng.random() <= density:
                grid[y][x] = char


def _scatter(grid, rng, biome, cx, cy, count, rx, ry, table, min_dist=0):
    """Розкидає плями по світу; символ залежить від біому в центрі плями."""
    height, width = len(grid), len(grid[0])
    for _ in range(count):
        x, y = rng.randrange(width), rng.randrange(height)
        if min_dist and math.hypot(x - cx, (y - cy) * 2) < min_dist:
            continue
        entry = table.get(biome(x, y))
        if entry is None:
            continue
        char, density = entry
        _blob(grid, rng, x, y, rng.randint(*rx), rng.randint(*ry), char, density)


# ---------- місто ----------
def _build_town(grid, cx: int, cy: int):
    """Місто з огорожею, воротами, вулицями та вісьмома будівлями."""
    x0, x1 = cx - zones.TOWN_HALF_W, cx + zones.TOWN_HALF_W
    y0, y1 = cy - zones.TOWN_HALF_H, cy + zones.TOWN_HALF_H

    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            edge = x in (x0, x1) or y in (y0, y1)
            grid[y][x] = "#" if edge else "."

    for x in range(x0 + 1, x1):          # головні вулиці
        grid[cy][x] = "="
    for y in range(y0 + 1, y1):
        grid[y][cx] = "="
    for gx, gy in ((x0, cy), (x1, cy), (cx, y0), (cx, y1)):    # ворота
        grid[gy][gx] = "="

    w, h = zones.BUILDING_W, zones.BUILDING_H
    buildings: list[Building] = []
    for kind, name, dx, side in zones.TOWN_LAYOUT:
        x = cx + dx
        y = cy - 8 if side == "north" else cy + 4
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                edge = xx in (x, x + w - 1) or yy in (y, y + h - 1)
                grid[yy][xx] = "#" if edge else "_"

        door_x = x + w // 2
        if side == "north":                       # двері знизу, дивляться на вулицю
            door_y, label_y = y + h - 1, y
            for py in range(door_y + 1, cy):
                grid[py][door_x] = "="
        else:                                     # двері зверху
            door_y, label_y = y, y + h - 1
            for py in range(cy + 1, door_y):
                grid[py][door_x] = "="
        grid[door_y][door_x] = "+"

        label_x = x + (w - len(name)) // 2
        buildings.append(Building(kind, name, x, y, w, h,
                                  door=(door_x, door_y),
                                  spot=(door_x, y + h // 2),
                                  label_pos=(label_x, label_y)))

    grid[cy - 2][cx - 3] = "o"       # два фонтани на площі
    grid[cy + 2][cx + 3] = "o"
    return (x0, y0, x1, y1), buildings


# ---------- входи в підземелля ----------
def _place_dungeons(grid, rng, cx: int, cy: int, biome, base_at):
    """Кам'яна арка з порталом '>' та стежкою до головної дороги.
    Деякі підземелля прив'язані до біому (поле "biome" у dungeons.json)."""
    height, width = len(grid), len(grid[0])
    portals: dict[tuple[int, int], str] = {}
    entrances: dict[str, tuple[int, int]] = {}
    placed: list[tuple[int, int]] = []

    for dungeon_id, cfg in dungeon_defs().items():
        lo, hi = cfg["distance"]
        want = cfg.get("biome")
        best, best_gap = (cx + 30, cy - 12), 10 ** 9

        for _ in range(3000):
            x = rng.randint(6, width - 7)
            y = rng.randint(4, height - 5)
            if abs(x - cx) < zones.TOWN_HALF_W + 4:        # не в смузі міста
                continue
            if abs(y - cy) < 5:                            # не на головній дорозі
                continue
            # різні стовпці: стежки та арки не перетинаються
            if any(abs(x - px) < 9 for px, _ in placed):
                continue
            if want and biome(x, y) != want:
                continue
            dist = math.hypot(x - cx, (y - cy) * 2)
            gap = 0 if lo <= dist <= hi else min(abs(dist - lo), abs(dist - hi))
            if gap < best_gap:
                best, best_gap = (x, y), gap
            if gap == 0:
                break

        x, y = best
        d = 1 if y < cy else -1                 # арка відкрита в бік головної дороги

        for dy in range(-3, 4):                 # розчищаємо територію
            for dx in range(-4, 5):
                grid[y + dy][x + dx] = base_at(x + dx, y + dy)
        for dy in (-1, 0, 1):                   # стіни арки 3x3
            for dx in (-1, 0, 1):
                grid[y + dy][x + dx] = "#"
        grid[y][x] = ">"
        grid[y + d][x] = "="

        yy = y + d                              # стежка до головної дороги
        while yy != cy:
            grid[yy][x] = "="
            yy += d

        placed.append((x, y))
        portals[(x, y)] = dungeon_id
        entrances[dungeon_id] = (x, y + d)
    return portals, entrances


# ---------- хатини ----------
def _place_huts(grid, rng, town_rect, count: int, base_at):
    height, width = len(grid), len(grid[0])
    x0, y0, x1, y1 = town_rect
    forbid = {"=", "#", ">", "_", "+", "o", "~"}
    huts: list[tuple[int, int, int, int]] = []

    for _ in range(4000):
        if len(huts) >= count:
            break
        w, h = rng.randint(6, 9), rng.randint(5, 6)
        x = rng.randint(3, width - w - 4)
        y = rng.randint(3, height - h - 5)

        if not (x + w < x0 - 3 or x > x1 + 3 or y + h < y0 - 3 or y > y1 + 3):
            continue                                        # надто близько до міста
        area = [(xx, yy) for yy in range(y - 1, y + h + 2)
                for xx in range(x - 1, x + w + 1)]
        if any(grid[yy][xx] in forbid for xx, yy in area):
            continue

        for xx, yy in area:                                 # розчищаємо підхід
            grid[yy][xx] = base_at(xx, yy)
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                edge = xx in (x, x + w - 1) or yy in (y, y + h - 1)
                grid[yy][xx] = "#" if edge else "_"
        door_x = x + w // 2
        grid[y + h - 1][door_x] = "+"
        grid[y + h][door_x] = "="
        huts.append((x, y, w, h))
    return huts


# ---------- головна функція ----------
def generate_overworld(width: int, height: int, seed: int | None = None) -> TileMap:
    rng = random.Random(seed)
    cx, cy = width // 2, height // 2
    phase = (rng.uniform(0, 6.28), rng.uniform(0, 6.28))

    def biome(x: int, y: int) -> str:
        return zones.biome_of(x, y, cx, cy, phase)

    def base_at(x: int, y: int) -> str:
        return zones.BIOME_BASE[biome(x, y)]

    # 1. земля за біомами
    grid = [[base_at(x, y) for x in range(width)] for y in range(height)]

    # 2. рослинність, озера, гори (кількість залежить від площі світу)
    scale = (width * height) / (120 * 60)
    _scatter(grid, rng, biome, cx, cy, int(35 * scale), (3, 8), (2, 5), GRASS)
    _scatter(grid, rng, biome, cx, cy, int(25 * scale), (3, 9), (2, 6), FORESTS)
    for y in range(height):                                 # поодинокі дерева, кактуси, ялини
        for x in range(width):
            single = SINGLES.get(grid[y][x])
            if single and rng.random() < single[1]:
                grid[y][x] = single[0]
    _scatter(grid, rng, biome, cx, cy, int(7 * scale), (3, 7), (2, 4), LAKES)
    _scatter(grid, rng, biome, cx, cy, int(11 * scale), (3, 7), (2, 4), MOUNTAINS, min_dist=34)

    # 3. головні дороги через усю карту
    for x in range(width):
        grid[cy][x] = "="
    for y in range(height):
        grid[y][cx] = "="

    # 4. місто, входи в підземелля, хатини
    town_rect, buildings = _build_town(grid, cx, cy)
    portals, entrances = _place_dungeons(grid, rng, cx, cy, biome, base_at)
    huts = _place_huts(grid, rng, town_rect, count=int(7 * scale), base_at=base_at)

    for x in range(width):                                  # межі світу
        grid[0][x] = grid[height - 1][x] = "#"
    for y in range(height):
        grid[y][0] = grid[y][width - 1] = "#"

    tilemap = TileMap(grid, spawn=(cx, cy), name="Світ Ельдорії")
    tilemap.biome_phase = phase
    tilemap.safe_rects = [town_rect]
    tilemap.buildings = buildings
    tilemap.portals = portals
    tilemap.entrances = entrances
    tilemap.huts = huts
    return tilemap