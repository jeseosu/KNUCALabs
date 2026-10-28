"""Малювання карти, HUD, журналу подій та спливаючих вікон."""
import curses

from game.config import (GAME_TITLE, HUD_WIDTH, LOG_HEIGHT,
                         MIN_TERM_HEIGHT, MIN_TERM_WIDTH)
from game.state import GameState
from game.ui import colors
from game.world import zones


def put(win, y: int, x: int, text: str, attr: int = 0) -> None:
    """Безпечний addstr: обрізає текст і ігнорує вихід за межі екрана."""
    height, width = win.getmaxyx()
    if y < 0 or y >= height or x < 0 or x >= width:
        return
    text = text[: width - x]
    if not text:
        return
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


def make_bar(current: int, maximum: int, width: int) -> str:
    ratio = 0 if maximum <= 0 else max(0.0, min(1.0, current / maximum))
    filled = round(ratio * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def hp_color(current: int, maximum: int) -> str:
    ratio = current / maximum if maximum else 0
    return "hp_good" if ratio > 0.6 else "hp_mid" if ratio > 0.3 else "hp_bad"


class Renderer:
    def __init__(self, stdscr):
        self.scr = stdscr

    def draw(self, state: GameState, popup: list[str] | None = None,
             overlay: list[tuple[int, int, str, str]] | None = None) -> None:
        """overlay - тимчасові символи ефектів: (x, y, символ, назва_кольору)."""
        self.scr.erase()
        height, width = self.scr.getmaxyx()

        if width < MIN_TERM_WIDTH or height < MIN_TERM_HEIGHT:
            put(self.scr, 0, 0, f"Збільш вікно терміналу до {MIN_TERM_WIDTH}x{MIN_TERM_HEIGHT}")
            put(self.scr, 1, 0, f"Зараз: {width}x{height}")
            self.scr.refresh()
            return

        view_w = width - HUD_WIDTH
        view_h = height - LOG_HEIGHT

        self._draw_map(state, view_w, view_h, overlay)
        self._draw_hud(state, view_w, view_h)
        self._draw_log(state, width, height, view_h)
        if popup:
            self._draw_popup(popup)
        self.scr.refresh()

    # ---------- карта ----------
    @staticmethod
    def _camera(state: GameState, view_w: int, view_h: int) -> tuple[int, int]:
        p, m = state.player, state.tilemap
        cam_x = max(0, min(p.x - view_w // 2, m.width - view_w))
        cam_y = max(0, min(p.y - view_h // 2, m.height - view_h))
        return cam_x, cam_y

    def _draw_map(self, state: GameState, view_w: int, view_h: int, overlay) -> None:
        tilemap = state.tilemap
        cam_x, cam_y = self._camera(state, view_w, view_h)
        fog = state.fog_enabled
        visible, explored = state.visible, state.explored
        memory_attr = colors.attr("log_old")      # тьмяний сірий для "запам'ятованого"

        for sy in range(view_h):
            my = cam_y + sy
            if my >= tilemap.height:
                break
            for sx in range(view_w):
                mx = cam_x + sx
                if mx >= tilemap.width:
                    break
                tile = tilemap.tile_at(mx, my)
                if tile is None:
                    continue
                if not fog or (mx, my) in visible:
                    put(self.scr, sy, sx, tile.char, colors.attr(tile.color))
                elif (mx, my) in explored:
                    put(self.scr, sy, sx, tile.char, memory_attr)
                # інакше - темрява, нічого не малюємо

        # вивіски будівель міста (малюються поверх стіни)
        for building in tilemap.buildings:
            lx, ly = building.label_pos
            for i, char in enumerate(building.name):
                sx, sy = lx + i - cam_x, ly - cam_y
                if not (0 <= sx < view_w and 0 <= sy < view_h):
                    continue
                if not fog or (lx + i, ly) in visible:
                    put(self.scr, sy, sx, char, colors.attr("title"))
                elif (lx + i, ly) in explored:
                    put(self.scr, sy, sx, char, memory_attr)

        # здобич на землі (лише у зоні огляду)
        for (px, py), pile in state.piles.items():
            sx, sy = px - cam_x, py - cam_y
            if 0 <= sx < view_w and 0 <= sy < view_h and state.can_see(px, py):
                put(self.scr, sy, sx, pile.glyph, colors.attr(pile.color))

        # монстри й NPC (лише у зоні огляду) та гравець
        for entity in state.entities:
            sx, sy = entity.x - cam_x, entity.y - cam_y
            if (0 <= sx < view_w and 0 <= sy < view_h
                    and state.can_see(entity.x, entity.y)):
                put(self.scr, sy, sx, entity.glyph, colors.attr(entity.color))
        p = state.player
        sx, sy = p.x - cam_x, p.y - cam_y
        if 0 <= sx < view_w and 0 <= sy < view_h:
            put(self.scr, sy, sx, p.glyph, colors.attr(p.color))

        for ox, oy, glyph, color in overlay or []:
            sx, sy = ox - cam_x, oy - cam_y
            if 0 <= sx < view_w and 0 <= sy < view_h:
                put(self.scr, sy, sx, glyph, colors.attr(color))

    # ---------- HUD ----------
    def _draw_hud(self, state: GameState, view_w: int, view_h: int) -> None:
        p = state.player
        ui = colors.attr("ui")
        x = view_w + 2
        bar_w = HUD_WIDTH - 5
        line = "-" * (HUD_WIDTH - 3)

        for y in range(view_h):
            put(self.scr, y, view_w, "|", ui)

        put(self.scr, 0, x, GAME_TITLE, colors.attr("title"))
        zone, _hint = zones.zone_info(state.tilemap, p.x, p.y)
        safe = state.tilemap.is_safe(p.x, p.y)
        put(self.scr, 1, x, zone[:HUD_WIDTH - 3], colors.attr("hp_good" if safe else "ui"))
        put(self.scr, 2, x, p.name, colors.attr("player"))
        put(self.scr, 3, x, f"{p.class_name}, рівень {p.level}")

        put(self.scr, 4, x, f"Здоров'я {p.hp}/{p.max_hp}")
        put(self.scr, 5, x, make_bar(p.hp, p.max_hp, bar_w),
            colors.attr(hp_color(p.hp, p.max_hp)))
        put(self.scr, 6, x, f"Мана {p.mp}/{p.max_mp}")
        put(self.scr, 7, x, make_bar(p.mp, p.max_mp, bar_w), colors.attr("mp"))
        put(self.scr, 8, x, f"Досвід {p.xp}/{p.xp_to_next}")
        put(self.scr, 9, x, make_bar(p.xp, p.xp_to_next, bar_w), colors.attr("xp"))

        put(self.scr, 10, x, f"Атака {p.power}  Захист {p.armor}")
        put(self.scr, 11, x, f"Золото {p.gold}  Крит {round(p.crit_chance * 100)}%",
            colors.attr("gold"))
        inv = p.inventory
        put(self.scr, 12, x,
            f"Зілля: [1]HP x{inv.count_effect('heal')} [2]MP x{inv.count_effect('mana')}")
        put(self.scr, 13, x, f"Хід {state.turn}  Загроза +{state.threat_bonus}")
        put(self.scr, 14, x, f"Вбито {state.kills}  Смертей {state.deaths}")

        put(self.scr, 15, x, line, ui)
        skill = p.skill
        put(self.scr, 16, x, f"[F] {skill['name']} {skill['cost']}мп", colors.attr("title"))
        put(self.scr, 17, x, line, ui)

        self._draw_target(state, x, 18, bar_w)
        event = state.events.hud_text(state)
        if event:
            put(self.scr, 20, x, ("* " + event)[:HUD_WIDTH - 3], colors.attr("title"))
        else:
            put(self.scr, 20, x, line, ui)
        self._draw_quests(state, x, 21)

        put(self.scr, view_h - 4, x, "WASD рух  F вміння", ui)
        put(self.scr, view_h - 3, x, "R спокій  G підібрати", ui)
        put(self.scr, view_h - 2, x, "I рюкзак J журнал M карта", ui)
        put(self.scr, view_h - 1, x, "P збер  H довідка  Esc меню", ui)

    def _draw_target(self, state: GameState, x: int, row: int, bar_w: int) -> None:
        target = state.nearest_monster(10, visible_only=True)
        if target is None:
            put(self.scr, row, x, "Поблизу тихо...", colors.attr("ui"))
            return
        tag = " БОС" if getattr(target, "is_boss", False) else ""
        put(self.scr, row, x, f"{target.name} [рів.{target.display_level}]{tag}",
            colors.attr(target.color))
        bar = make_bar(target.hp, target.max_hp, bar_w - 9)
        put(self.scr, row + 1, x, f"{bar} {target.hp}/{target.max_hp}",
            colors.attr(hp_color(target.hp, target.max_hp)))

    def _draw_quests(self, state: GameState, x: int, row: int) -> None:
        log = state.quest_log
        ready = sum(1 for qid in log.active if log.is_ready(state, qid))
        put(self.scr, row, x, f"Завдання: {len(log.active)}  готово: {ready}",
            colors.attr("hp_good" if ready else "ui"))
        if log.active:
            qid = next((q for q in log.active if log.is_ready(state, q)),
                       next(iter(log.active)))
            put(self.scr, row + 1, x, log.short(state, qid)[:HUD_WIDTH - 3])
        else:
            put(self.scr, row + 1, x, "Шукай ! над NPC", colors.attr("log_old"))

    # ---------- журнал ----------
    def _draw_log(self, state: GameState, width: int, height: int, view_h: int) -> None:
        put(self.scr, view_h, 0, "-" * width, colors.attr("ui"))
        lines = state.messages[-(LOG_HEIGHT - 1):]
        for i, text in enumerate(lines):
            is_newest = i == len(lines) - 1
            attr = colors.attr("log_new" if is_newest else "log_old")
            put(self.scr, view_h + 1 + i, 1, text, attr)

    # ---------- спливаюче вікно ----------
    def _draw_popup(self, lines: list[str]) -> None:
        height, width = self.scr.getmaxyx()
        box_w = max(len(line) for line in lines) + 4
        box_h = len(lines) + 2
        x0, y0 = (width - box_w) // 2, (height - box_h) // 2
        attr = colors.attr("title")

        put(self.scr, y0, x0, "+" + "-" * (box_w - 2) + "+", attr)
        for i, line in enumerate(lines, start=1):
            put(self.scr, y0 + i, x0, "| " + line.ljust(box_w - 4) + " |", attr)
        put(self.scr, y0 + box_h - 1, x0, "+" + "-" * (box_w - 2) + "+", attr)