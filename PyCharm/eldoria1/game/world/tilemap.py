"""Тайли, будівлі та карта світу."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Tile:
    char: str
    name: str
    walkable: bool
    color: str
    blocked_msg: str = ""   # що написати, якщо не пройти
    enter_msg: str = ""     # що написати, коли заходимо


TILES: dict[str, Tile] = {t.char: t for t in (
    Tile(".", "трава", True, "grass"),
    Tile('"', "висока трава", True, "tallgrass",
         enter_msg="Ти заходиш у високу траву. Тут щось шарудить..."),
    Tile("T", "дерево", False, "tree", blocked_msg="Дерево стоїть на шляху."),
    Tile("~", "вода", False, "water", blocked_msg="Вода надто глибока, щоб перейти."),
    Tile("#", "стіна", False, "wall", blocked_msg="Суцільна стіна."),
    Tile("+", "двері", True, "door", enter_msg="Двері скрипнули, коли ти їх відчинив."),
    Tile("=", "стежка", True, "path"),
    Tile("_", "підлога", True, "floor"),
    Tile(",", "кам'яна підлога", True, "floor"),
    Tile("o", "фонтан", False, "water", blocked_msg="Фонтан тихо дзюрчить."),
    # портали непрохідні: на них реагує рушій (вікно підтвердження)
    Tile(">", "вхід у підземелля", False, "ui"),
    Tile("<", "вихід нагору", False, "ui"),
    # --- біоми (етап 5) ---
    Tile(":", "пісок", True, "sand"),
    Tile(";", "сніг", True, "snow"),
    Tile("&", "болото", True, "swamp",
         enter_msg="Ноги грузнуть у багнюці. Тхне гниллям."),
    Tile("^", "гори", False, "mountain", blocked_msg="Круті скелі. Туди не піднятись."),
    Tile("Y", "кактус", False, "cactus", blocked_msg="Колючий кактус."),
    Tile("A", "ялина", False, "pine", blocked_msg="Ялина стоїть на шляху."),
)}

# крізь ці тайли не пролетить магія чи стріла, і за ними нічого не видно
SIGHT_BLOCKERS = {"#", "T", "A", "^"}


@dataclass(frozen=True)
class Building:
    """Будівля міста. Координати використовують NPC."""
    kind: str                    # blacksmith, shop, tavern, guild, ...
    name: str                    # текст вивіски
    x: int
    y: int
    w: int
    h: int
    door: tuple[int, int]
    spot: tuple[int, int]        # де всередині стоїть NPC
    label_pos: tuple[int, int]   # де малювати вивіску


class TileMap:
    def __init__(self, grid: list[list[str]], spawn: tuple[int, int],
                 name: str = "Світ Ельдорії", kind: str = "overworld"):
        self.grid = grid
        self.height = len(grid)
        self.width = len(grid[0])
        self.spawn = spawn
        self.name = name
        self.kind = kind                       # "overworld" або "dungeon"
        self.hint = ""                         # підказка для повідомлення про вхід
        self.vision: int | None = None         # свій радіус огляду (підземелля)
        self.biome_phase: tuple[float, float] = (0.0, 0.0)   # для визначення біому
        self.portals: dict[tuple[int, int], str] = {}      # клітинка -> id підземелля / "exit"
        self.entrances: dict[str, tuple[int, int]] = {}    # id підземелля -> де з'являємось при виході
        self.buildings: list[Building] = []
        self.safe_rects: list[tuple[int, int, int, int]] = []   # (x0, y0, x1, y1)
        self.huts: list[tuple[int, int, int, int]] = []         # (x, y, w, h)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def tile_at(self, x: int, y: int) -> Tile | None:
        if not self.in_bounds(x, y):
            return None
        return TILES.get(self.grid[y][x])

    def is_walkable(self, x: int, y: int) -> bool:
        tile = self.tile_at(x, y)
        return tile is not None and tile.walkable

    def is_safe(self, x: int, y: int) -> bool:
        """Безпечна зона (місто): монстри сюди не заходять і не атакують."""
        return any(x0 <= x <= x1 and y0 <= y <= y1
                   for x0, y0, x1, y1 in self.safe_rects)

    def building(self, kind: str) -> Building | None:
        for b in self.buildings:
            if b.kind == kind:
                return b
        return None

    def set_tile(self, x: int, y: int, char: str) -> None:
        if self.in_bounds(x, y):
            self.grid[y][x] = char

    def line_points(self, x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
        """Алгоритм Брезенхема: клітинки від (x0,y0) до (x1,y1), без початкової."""
        points = []
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while (x, y) != (x1, y1):
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
            points.append((x, y))
        return points

    def line_clear(self, x0: int, y0: int, x1: int, y1: int) -> bool:
        """Чи немає стіни/дерева між двома точками (кінцева клітинка не рахується)."""
        path = self.line_points(x0, y0, x1, y1)[:-1]
        return all(self.grid[y][x] not in SIGHT_BLOCKERS for x, y in path)