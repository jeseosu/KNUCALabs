"""Екрани: діалоги, журнал завдань і карта світу."""
import curses
import math
import textwrap

from game.config import (MAP_KEYS, MENU_CONFIRM, MENU_DOWN, MENU_UP,
                         QUEST_KEYS, QUIT_KEYS)
from game.systems import dialogue, quests
from game.ui import colors
from game.ui.renderer import put
from game.world.tilemap import TILES


def _read(scr):
    """Читає клавішу. None, якщо читати нічого або змінився розмір вікна."""
    try:
        key = scr.get_wch()
    except curses.error:
        return None
    if key == curses.KEY_RESIZE:
        scr.clear()
        return None
    return key


class DialogueMenu:
    """Розмова з NPC: текст зверху, варіанти відповіді знизу."""

    def __init__(self, stdscr, state, npc):
        self.scr = stdscr
        self.state = state
        self.npc = npc

    def run(self) -> None:
        page = dialogue.main_page(self.state, self.npc)
        cursor = 0
        while page is not None:
            self._draw(page, cursor)
            key = _read(self.scr)
            if key is None:
                continue
            if key in QUIT_KEYS:
                break

            count = len(page.options)
            confirm = False
            if key in MENU_UP:
                cursor = (cursor - 1) % count
            elif key in MENU_DOWN:
                cursor = (cursor + 1) % count
            elif key in MENU_CONFIRM:
                confirm = True
            elif isinstance(key, str) and key.isdigit() and 1 <= int(key) <= count:
                cursor, confirm = int(key) - 1, True

            if confirm:
                page = dialogue.handle(self.state, self.npc, page.options[cursor])
                cursor = 0

    def _draw(self, page, cursor: int) -> None:
        scr = self.scr
        scr.erase()
        height, width = scr.getmaxyx()
        ui = colors.attr("ui")
        wrap_w = max(20, min(width - 6, 76))

        put(scr, 0, 1, page.speaker, colors.attr("title"))
        gold = f"Золото: {self.state.player.gold}"
        put(scr, 0, max(1, width - len(gold) - 2), gold, colors.attr("gold"))
        put(scr, 1, 0, "-" * width, ui)

        row = 3
        for paragraph in page.text.split("\n"):
            for line in textwrap.wrap(paragraph, wrap_w) or [""]:
                put(scr, row, 2, line, colors.attr("log_new"))
                row += 1

        row += 1
        put(scr, row, 0, "-" * width, ui)
        row += 1
        for i, option in enumerate(page.options):
            selected = i == cursor
            text = f"{'>' if selected else ' '} {i + 1}. {option.label}"
            attr = colors.attr(option.color) | (curses.A_REVERSE if selected else 0)
            put(scr, row + i, 2, text.ljust(wrap_w), attr)

        put(scr, height - 1, 1, "W/S вибір  Enter/E підтвердити  1-9 швидко  Esc вийти", ui)
        scr.refresh()


class QuestLogMenu:
    """Журнал активних завдань."""

    def __init__(self, stdscr, state):
        self.scr = stdscr
        self.state = state
        self.top = 0

    def run(self) -> None:
        while True:
            lines = self._lines()
            self._draw(lines)
            key = _read(self.scr)
            if key is None:
                continue
            if key in QUIT_KEYS or key in QUEST_KEYS:
                break
            if key in MENU_UP:
                self.top = max(0, self.top - 1)
            elif key in MENU_DOWN:
                self.top = min(max(0, len(lines) - 1), self.top + 1)

    def _lines(self) -> list[tuple[str, str]]:
        s, log = self.state, self.state.quest_log
        out: list[tuple[str, str]] = []
        if not log.active:
            out.append(("Активних завдань немає. Шукай жителів з позначкою ! над головою.",
                        "log_old"))
        for qid in log.active:
            ready = log.is_ready(s, qid)
            name = quests.quest_defs()[qid]["name"]
            out.append((("[ГОТОВО] " if ready else "") + name, "hp_good" if ready else "title"))
            out.append(("   " + log.objective(s, qid), "default"))
            role = "Здати" if ready else "Замовник"
            out.append((f"   {role}: {quests.giver_name(qid)}", "log_old"))
            out.append(("", "default"))
        return out

    def _draw(self, lines: list[tuple[str, str]]) -> None:
        scr = self.scr
        scr.erase()
        height, width = scr.getmaxyx()
        ui = colors.attr("ui")
        put(scr, 0, 1, f"ЖУРНАЛ ЗАВДАНЬ  ({len(self.state.quest_log.active)} активних)",
            colors.attr("title"))
        put(scr, 1, 0, "-" * width, ui)
        for i, (text, color) in enumerate(lines[self.top:self.top + height - 5]):
            put(scr, 2 + i, 2, text, colors.attr(color))
        put(scr, height - 3, 0, "-" * width, ui)
        put(scr, height - 2, 1, f"Виконано завдань: {len(self.state.quest_log.done)}",
            colors.attr("gold"))
        put(scr, height - 1, 1, "W/S прокрутка  J/Esc закрити", ui)
        scr.refresh()


# пріоритет символів при стисканні карти: що показати, якщо в блок потрапило кілька
MAP_PRIORITY = {">": 9, "<": 9, "+": 5, "#": 4, "o": 4, "~": 3, "^": 3,
                "=": 2, "T": 2, "A": 2, "Y": 2, "\"": 1}


class WorldMap:
    """Карта світу: показує лише відкриті клітинки."""

    def __init__(self, stdscr, state):
        self.scr = stdscr
        self.state = state

    def run(self) -> None:
        while True:
            self._draw()
            key = _read(self.scr)
            if key is None:
                continue
            if key in QUIT_KEYS or key in MAP_KEYS:
                break

    def _draw(self) -> None:
        scr, state = self.scr, self.state
        scr.erase()
        height, width = scr.getmaxyx()
        tm, explored, p = state.tilemap, state.explored, state.player
        ui = colors.attr("ui")

        fx = max(1, math.ceil(tm.width / (width - 2)))        # скільки клітинок в одному символі
        fy = max(1, math.ceil(tm.height / (height - 4)))

        percent = round(100 * len(explored) / (tm.width * tm.height))
        put(scr, 0, 1, f"КАРТА: {tm.name}   відкрито {percent}%", colors.attr("title"))

        for sy in range(math.ceil(tm.height / fy)):
            for sx in range(math.ceil(tm.width / fx)):
                best, best_priority = None, -1
                for y in range(sy * fy, min(tm.height, (sy + 1) * fy)):
                    for x in range(sx * fx, min(tm.width, (sx + 1) * fx)):
                        if (x, y) in explored:
                            char = tm.grid[y][x]
                            priority = MAP_PRIORITY.get(char, 0)
                            if priority > best_priority:
                                best, best_priority = char, priority
                if best is not None:
                    tile = TILES.get(best)
                    put(scr, 1 + sy, 1 + sx, best, colors.attr(tile.color if tile else "default"))

        put(scr, 1 + p.y // fy, 1 + p.x // fx, "@", colors.attr("player") | curses.A_REVERSE)
        put(scr, height - 2, 1, "@ ти   > підземелля   # стіни/місто   = дороги   ~ вода   ^ гори", ui)
        put(scr, height - 1, 1, "M/Esc закрити", ui)
        scr.refresh()