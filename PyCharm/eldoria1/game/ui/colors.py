"""Кольорові пари curses. Викликати init_colors() один раз після старту curses."""
import curses

# назва: (колір тексту, колір фону, додатковий атрибут)
_SPEC = {
    "default":   (curses.COLOR_WHITE,   -1, 0),
    "ui":        (curses.COLOR_CYAN,    -1, 0),
    "title":     (curses.COLOR_YELLOW,  -1, curses.A_BOLD),
    "gold":      (curses.COLOR_YELLOW,  -1, curses.A_BOLD),

    # тайли світу
    "grass":     (curses.COLOR_GREEN,   -1, 0),
    "tallgrass": (curses.COLOR_GREEN,   -1, curses.A_BOLD),
    "tree":      (curses.COLOR_GREEN,   -1, curses.A_DIM),
    "water":     (curses.COLOR_BLUE,    -1, curses.A_BOLD),
    "wall":      (curses.COLOR_WHITE,   -1, curses.A_BOLD),
    "floor":     (curses.COLOR_YELLOW,  -1, curses.A_DIM),
    "door":      (curses.COLOR_YELLOW,  -1, curses.A_BOLD),
    "path":      (curses.COLOR_YELLOW,  -1, 0),
    "sand":      (curses.COLOR_YELLOW,  -1, curses.A_DIM),
    "snow":      (curses.COLOR_WHITE,   -1, curses.A_BOLD),
    "swamp":     (curses.COLOR_GREEN,   -1, curses.A_DIM | curses.A_UNDERLINE),
    "pine":      (curses.COLOR_CYAN,    -1, curses.A_DIM),
    "cactus":    (curses.COLOR_GREEN,   -1, curses.A_BOLD),
    "mountain":  (curses.COLOR_WHITE,   -1, 0),

    # ГРАВЕЦЬ: фіолетовий. Можна змінити на COLOR_CYAN, COLOR_RED, COLOR_BLUE...
    "player":    (curses.COLOR_MAGENTA, -1, curses.A_BOLD),

    # NPC та маркери квестів
    "npc":         (curses.COLOR_CYAN,   -1, curses.A_BOLD),
    "quest_new":   (curses.COLOR_YELLOW, -1, curses.A_BOLD | curses.A_REVERSE),
    "quest_done":  (curses.COLOR_GREEN,  -1, curses.A_BOLD | curses.A_REVERSE),

    "hp_good":   (curses.COLOR_GREEN,   -1, curses.A_BOLD),
    "hp_mid":    (curses.COLOR_YELLOW,  -1, curses.A_BOLD),
    "hp_bad":    (curses.COLOR_RED,     -1, curses.A_BOLD),
    "mp":        (curses.COLOR_BLUE,    -1, curses.A_BOLD),
    "xp":        (curses.COLOR_MAGENTA, -1, curses.A_BOLD),
    "log_new":   (curses.COLOR_WHITE,   -1, curses.A_BOLD),
    "log_old":   (curses.COLOR_WHITE,   -1, curses.A_DIM),

    # монстри (назви беруться з monsters.json)
    "mob_white":  (curses.COLOR_WHITE,  -1, 0),
    "mob_cyan":   (curses.COLOR_CYAN,   -1, curses.A_BOLD),
    "mob_yellow": (curses.COLOR_YELLOW, -1, curses.A_BOLD),
    "mob_green":  (curses.COLOR_GREEN,  -1, curses.A_BOLD),
    "mob_red":    (curses.COLOR_RED,    -1, curses.A_BOLD),
    "mob_boss":   (curses.COLOR_RED,    -1, curses.A_BOLD | curses.A_REVERSE),

    # ефекти вмінь
    "fx_fire":   (curses.COLOR_RED,     -1, curses.A_BOLD),
    "fx_arrow":  (curses.COLOR_YELLOW,  -1, curses.A_BOLD),

    # рідкість предметів (назви беруться з items.json)
    "rar_common":    (curses.COLOR_WHITE,   -1, 0),
    "rar_uncommon":  (curses.COLOR_GREEN,   -1, curses.A_BOLD),
    "rar_rare":      (curses.COLOR_CYAN,    -1, curses.A_BOLD),
    "rar_epic":      (curses.COLOR_MAGENTA, -1, curses.A_BOLD),
    "rar_legendary": (curses.COLOR_YELLOW,  -1, curses.A_BOLD | curses.A_UNDERLINE),
}

_attrs: dict[str, int] = {}


def init_colors() -> None:
    if not curses.has_colors():
        return
    curses.start_color()
    curses.use_default_colors()

    pair_ids: dict[tuple[int, int], int] = {}   # одна пара на комбінацію (fg, bg)
    for name, (fg, bg, extra) in _SPEC.items():
        key = (fg, bg)
        if key not in pair_ids:
            pair_ids[key] = len(pair_ids) + 1
            curses.init_pair(pair_ids[key], fg, bg)
        _attrs[name] = curses.color_pair(pair_ids[key]) | extra


def attr(name: str) -> int:
    """Повертає curses-атрибут за назвою (0, якщо кольорів немає)."""
    return _attrs.get(name, 0)