"""Екрани меню: титульний екран, нова гра, слоти, пауза, смерть, перемога, довідка."""
import curses
import random
import textwrap

from game.config import (DEBUG, HELP_KEYS, MENU_CONFIRM, MENU_DOWN, MENU_UP,
                         QUIT_KEYS, load_json)
from game.items.item import get_item, starting_kit
from game.persistence import save_manager
from game.ui import colors
from game.ui.renderer import put

ENTER_KEYS = {"\n", "\r", curses.KEY_ENTER}
BACKSPACE_KEYS = {curses.KEY_BACKSPACE, "\x7f", "\b", 127}
DELETE_KEYS = {"x", "X", "ч", "Ч", curses.KEY_DC}
NAME_MAX = 16

# шрифт 5x5 для великих заголовків (кожен рядок рівно 5 символів)
GLYPHS = {
    "E": ("#####", "#    ", "#### ", "#    ", "#####"),
    "L": ("#    ", "#    ", "#    ", "#    ", "#####"),
    "D": ("#### ", "#   #", "#   #", "#   #", "#### "),
    "O": (" ### ", "#   #", "#   #", "#   #", " ### "),
    "R": ("#### ", "#   #", "#### ", "#  # ", "#   #"),
    "I": ("#####", "  #  ", "  #  ", "  #  ", "#####"),
    "A": (" ### ", "#   #", "#####", "#   #", "#   #"),
    "V": ("#   #", "#   #", "#   #", " # # ", "  #  "),
    "C": (" ####", "#    ", "#    ", "#    ", " ####"),
    "T": ("#####", "  #  ", "  #  ", "  #  ", "  #  "),
    "Y": ("#   #", " # # ", "  #  ", "  #  ", "  #  "),
}

TOMBSTONE = [
    r"     _________     ",
    r"    /         \    ",
    r"   /  R. I. P. \   ",
    r"   |           |   ",
    r"   |           |   ",
    r" __|___________|__ ",
]

DEATH_QUOTES = [
    "Навіть герої іноді падають. Головне, що вони встають.",
    "Темрява Ельдорії не прощає поспіху.",
    "Зілля лікують рани, а розсудливість лікує гординю.",
    "Храм завжди прийме тебе назад.",
    "Кожен програш - це урок, який не купиш за золото.",
]


# ---------- допоміжне ----------
def big_text(word: str) -> list[str]:
    return ["  ".join(GLYPHS[ch][row] for ch in word) for row in range(5)]


def read_key(scr):
    """Читає клавішу. None, якщо читати нічого або змінився розмір вікна."""
    try:
        key = scr.get_wch()
    except curses.error:
        return None
    if key == curses.KEY_RESIZE:
        scr.clear()
        return None
    return key


def center(scr, y: int, text: str, attr: int = 0) -> None:
    _, width = scr.getmaxyx()
    put(scr, y, max(0, (width - len(text)) // 2), text, attr)


def draw_box(scr, lines: list[str], attr: int) -> None:
    height, width = scr.getmaxyx()
    box_w = max(len(line) for line in lines) + 4
    box_h = len(lines) + 2
    x0, y0 = max(0, (width - box_w) // 2), max(0, (height - box_h) // 2)
    put(scr, y0, x0, "+" + "-" * (box_w - 2) + "+", attr)
    for i, line in enumerate(lines, start=1):
        put(scr, y0 + i, x0, "| " + line.ljust(box_w - 4) + " |", attr)
    put(scr, y0 + box_h - 1, x0, "+" + "-" * (box_w - 2) + "+", attr)


def fmt_time(seconds) -> str:
    minutes = int(seconds) // 60
    return f"{minutes // 60}г {minutes % 60:02d}хв"


def navigate(key, cursor: int, count: int) -> tuple[int, bool]:
    """W/S, стрілки, цифри та Enter. Повертає (новий_курсор, підтверджено)."""
    if key in MENU_UP:
        return (cursor - 1) % count, False
    if key in MENU_DOWN:
        return (cursor + 1) % count, False
    if key in MENU_CONFIRM:
        return cursor, True
    if isinstance(key, str) and len(key) == 1 and key in "123456789" and int(key) <= count:
        return int(key) - 1, True
    return cursor, False


def draw_options(scr, y: int, labels: list[str], cursor: int) -> None:
    _, width = scr.getmaxyx()
    box = max(len(label) for label in labels) + 8
    x = max(0, (width - box) // 2)
    for i, label in enumerate(labels):
        selected = i == cursor
        text = f"{'>' if selected else ' '} {i + 1}. {label}".ljust(box)
        attr = colors.attr("title" if selected else "default")
        put(scr, y + i, x, text, attr | (curses.A_REVERSE if selected else 0))


def stats_lines(state) -> list[str]:
    p = state.player
    return [f"Герой: {p.name}, {p.class_name}, рівень {p.level}",
            f"Ходів: {state.turn}     Час гри: {fmt_time(state.playtime)}",
            f"Ворогів переможено: {state.kills}     Смертей: {state.deaths}",
            f"Золото: {p.gold}"]


# =====================================================================
class TitleScreen:
    """Головне меню. run() повертає ('new', ім'я, клас) | ('load', слот) | ('quit',)."""

    def __init__(self, scr):
        self.scr = scr
        self.note = ""
        self.latest: str | None = None
        self.latest_info: dict | None = None
        self._refresh()

    def _refresh(self) -> None:
        self.latest = save_manager.latest_slot()
        info = save_manager.slot_summary(self.latest) if self.latest else None
        ok = info and not info.get("error") and info.get("ok", True)
        self.latest_info = info if ok else None
        if self.latest_info is None:
            self.latest = None

    def _items(self) -> list[tuple[str, str]]:
        items = []
        if self.latest:
            items.append(("continue", "Продовжити"))
        items += [("new", "Нова гра"), ("load", "Завантажити гру"),
                  ("help", "Керування та довідка"), ("quit", "Вийти")]
        return items

    def run(self):
        self._refresh()
        cursor = 0
        while True:
            items = self._items()
            cursor = min(cursor, len(items) - 1)
            self._draw(items, cursor)
            key = read_key(self.scr)
            if key is None:
                continue
            self.note = ""
            cursor, confirmed = navigate(key, cursor, len(items))
            if not confirmed:
                continue
            result = self._activate(items[cursor][0])
            if result:
                return result

    def _activate(self, action: str):
        if action == "continue":
            return ("load", self.latest)
        if action == "new":
            created = NewGameScreen(self.scr).run()
            return ("new", *created) if created else None
        if action == "load":
            slot = SlotMenu(self.scr, "load").run()
            self._refresh()
            return ("load", slot) if slot else None
        if action == "help":
            HelpScreen(self.scr).run()
            return None
        return ("quit",)

    def _draw(self, items, cursor: int) -> None:
        scr = self.scr
        scr.erase()
        height, _ = scr.getmaxyx()
        ui, title = colors.attr("ui"), colors.attr("title")
        top = max(1, (height - 22) // 2)

        center(scr, top, "~ ~ ~   E C H O E S   O F   ~ ~ ~", ui)
        for i, line in enumerate(big_text("ELDORIA")):
            center(scr, top + 2 + i, line, title)
        center(scr, top + 8, "Текстова MMORPG для одного гравця", colors.attr("log_new"))
        center(scr, top + 9, "-" * 44, ui)
        draw_options(scr, top + 11, [label for _, label in items], cursor)

        info = self.latest_info
        if info and items[cursor][0] == "continue":
            center(scr, top + 12 + len(items),
                   f"{info['name']}, {info['class_name']}, рівень {info['level']}, {info['location']}",
                   colors.attr("log_old"))
        if self.note:
            center(scr, top + 14 + len(items), self.note, colors.attr("hp_bad"))
        if DEBUG:
            center(scr, height - 2, "[режим розробника: DEBUG = True]", colors.attr("log_old"))
        center(scr, height - 1, "W/S вибір   Enter підтвердити   1-9 швидко", ui)
        scr.refresh()


# =====================================================================
class NewGameScreen:
    """Вибір імені, а потім класу героя."""

    def __init__(self, scr):
        self.scr = scr

    def run(self):
        name = self._ask_name("")
        while name is not None:
            class_id = self._pick_class(name)
            if class_id is not None:
                return name, class_id
            name = self._ask_name(name)          # Esc на виборі класу: назад до імені
        return None

    def _ask_name(self, text: str):
        scr = self.scr
        while True:
            scr.erase()
            ui = colors.attr("ui")
            put(scr, 0, 1, "НОВА ГРА", colors.attr("title"))
            put(scr, 1, 0, "-" * scr.getmaxyx()[1], ui)
            center(scr, 5, "Як звати твого героя?", colors.attr("log_new"))
            center(scr, 7, f"[ {text}_ ]".ljust(NAME_MAX + 6), colors.attr("player"))
            center(scr, 10, "Порожнє ім'я стане «Мандрівник».", colors.attr("log_old"))
            put(scr, scr.getmaxyx()[0] - 1, 1, "Enter далі   Esc назад", ui)
            scr.refresh()

            key = read_key(scr)
            if key is None:
                continue
            if key == "\x1b":                 # лише Esc: літери q, й можуть бути в імені
                return None
            if key in ENTER_KEYS:
                return text.strip() or "Мандрівник"
            if key in BACKSPACE_KEYS:
                text = text[:-1]
            elif isinstance(key, str) and len(key) == 1 and key.isprintable() \
                    and len(text) < NAME_MAX:
                text += key

    def _pick_class(self, name: str):
        classes = load_json("classes.json")
        ids = list(classes)
        cursor = 0
        while True:
            self._draw_classes(name, classes, ids, cursor)
            key = read_key(self.scr)
            if key is None:
                continue
            if key in QUIT_KEYS:
                return None
            if key in MENU_UP:
                cursor = (cursor - 1) % len(ids)
            elif key in MENU_DOWN:
                cursor = (cursor + 1) % len(ids)
            elif key in MENU_CONFIRM:
                return ids[cursor]

    def _draw_classes(self, name, classes, ids, cursor) -> None:
        scr = self.scr
        scr.erase()
        height, width = scr.getmaxyx()
        ui, title = colors.attr("ui"), colors.attr("title")
        put(scr, 0, 1, f"ОБЕРИ КЛАС ДЛЯ ГЕРОЯ: {name}", title)
        put(scr, 1, 0, "-" * width, ui)

        for i, cid in enumerate(ids):
            selected = i == cursor
            text = f"{'>' if selected else ' '} {classes[cid]['name']}".ljust(16)
            put(scr, 3 + i * 2, 2, text, title | (curses.A_REVERSE if selected else 0))

        c = classes[ids[cursor]]
        b, g, skill = c["base"], c["per_level"], c["skill"]
        kit = starting_kit(ids[cursor])
        gear = [get_item(i).name for i in kit.get("equip", [])]
        gear += [f"{get_item(i).name} x{n}" for i, n in kit.get("items", [])]

        x, wrap_w = 22, max(20, width - 24)
        row = 3
        put(scr, row, x, c["name"], colors.attr("player"))
        row += 2
        for line in textwrap.wrap(c["description"], wrap_w):
            put(scr, row, x, line)
            row += 1
        row += 1
        put(scr, row, x, f"Здоров'я {b['max_hp']} (+{g['max_hp']} за рівень)", colors.attr("hp_good"))
        put(scr, row + 1, x, f"Мана {b['max_mp']} (+{g['max_mp']} за рівень)", colors.attr("mp"))
        put(scr, row + 2, x, f"Атака {b['attack']} (+{g['attack']})   Захист {b['defense']} (+{g['defense']})")
        row += 4
        put(scr, row, x, f"Вміння: {skill['name']}", title)
        put(scr, row + 1, x, f"мана {skill['cost']}, дальність {skill['range']}, шкода x{skill['multiplier']}")
        row += 3
        put(scr, row, x, "Стартове спорядження:", colors.attr("gold"))
        for line in textwrap.wrap(", ".join(gear), wrap_w):
            row += 1
            put(scr, row, x, line, colors.attr("log_old"))
        put(scr, height - 1, 1, "W/S вибір   Enter почати гру   Esc назад", ui)
        scr.refresh()


# =====================================================================
class SlotMenu:
    """Вибір слота. mode: 'load' (є й автозбереження) або 'save'. Повертає слот чи None."""

    def __init__(self, scr, mode: str, current: str | None = None):
        self.scr = scr
        self.mode = mode
        self.slots = save_manager.SLOTS if mode == "load" else save_manager.MANUAL_SLOTS
        self.note = ""
        self.confirm: tuple[str, str] | None = None     # ("overwrite" | "delete", слот)
        self._refresh()
        if current in self.slots:
            self.cursor = self.slots.index(current)
        else:
            empty = [i for i, s in enumerate(self.slots) if self.info[s] is None]
            self.cursor = empty[0] if empty else 0

    def _refresh(self) -> None:
        self.info = {slot: save_manager.slot_summary(slot) for slot in self.slots}

    def run(self):
        while True:
            self._draw()
            key = read_key(self.scr)
            if key is None:
                continue

            if self.confirm:
                kind, slot = self.confirm
                self.confirm = None
                if key in ENTER_KEYS:
                    if kind == "overwrite":
                        return slot
                    save_manager.delete_save(slot)
                    self._refresh()
                    self.note = f"{save_manager.slot_label(slot)} видалено."
                continue

            slot = self.slots[self.cursor]
            info = self.info[slot]
            self.note = ""
            if key in QUIT_KEYS:
                return None
            if key in MENU_UP:
                self.cursor = (self.cursor - 1) % len(self.slots)
            elif key in MENU_DOWN:
                self.cursor = (self.cursor + 1) % len(self.slots)
            elif key in DELETE_KEYS and info is not None:
                self.confirm = ("delete", slot)
            elif key in MENU_CONFIRM:
                if self.mode == "save":
                    if info is None:
                        return slot
                    self.confirm = ("overwrite", slot)
                elif info is None:
                    self.note = "Цей слот порожній."
                elif info.get("error") or not info.get("ok", True):
                    self.note = "Файл пошкоджено або створено іншою версією гри."
                else:
                    return slot

    def _draw(self) -> None:
        scr = self.scr
        scr.erase()
        height, width = scr.getmaxyx()
        ui = colors.attr("ui")
        put(scr, 0, 1, "ЗАВАНТАЖИТИ ГРУ" if self.mode == "load" else "ЗБЕРЕГТИ ГРУ",
            colors.attr("title"))
        put(scr, 1, 0, "-" * width, ui)

        for i, slot in enumerate(self.slots):
            y = 3 + i * 4
            selected = i == self.cursor
            reverse = curses.A_REVERSE if selected else 0
            mark = ">" if selected else " "
            label = save_manager.slot_label(slot)
            info = self.info[slot]
            line1 = line2 = ""
            color = "default"
            if info is None:
                head, color = f"{mark} {label}: (порожньо)", "log_old"
            elif info.get("error") or not info.get("ok", True):
                head, color = f"{mark} {label}: файл пошкоджено або з іншої версії", "hp_bad"
            else:
                head = f"{mark} {label}   {info.get('saved_at', '')}"
                line1 = (f"    {info.get('name', '?')}, {info.get('class_name', '?')}, "
                         f"рівень {info.get('level', '?')}   хід {info.get('turn', '?')}")
                line2 = (f"    {info.get('location', '?')}   золото {info.get('gold', 0)}   "
                         f"вбито {info.get('kills', 0)}   час {fmt_time(info.get('playtime', 0))}")
            put(scr, y, 1, head.ljust(width - 2), colors.attr(color) | reverse)
            put(scr, y + 1, 1, line1)
            put(scr, y + 2, 1, line2, colors.attr("log_old"))

        put(scr, height - 3, 1, self.note, colors.attr("hp_bad"))
        action = "завантажити" if self.mode == "load" else "зберегти"
        put(scr, height - 1, 1, f"W/S вибір   Enter {action}   X видалити   Esc назад", ui)

        if self.confirm:
            kind, slot = self.confirm
            if kind == "overwrite":
                lines = ["Перезаписати збереження?", save_manager.slot_label(slot), "",
                         "Enter - так, інша клавіша - ні"]
            else:
                lines = ["Видалити збереження назавжди?", save_manager.slot_label(slot), "",
                         "Enter - так, інша клавіша - ні"]
            draw_box(scr, lines, colors.attr("title"))
        scr.refresh()


# =====================================================================
class PauseMenu:
    """Меню паузи. Повертає: resume | save | help | menu | quit."""

    ITEMS = [("resume", "Продовжити гру"), ("save", "Зберегти гру"),
             ("help", "Довідка та керування"), ("menu", "Вийти в головне меню"),
             ("quit", "Закрити гру")]

    def __init__(self, scr, state):
        self.scr = scr
        self.state = state

    def run(self) -> str:
        cursor, confirm = 0, None
        while True:
            self._draw(cursor, confirm)
            key = read_key(self.scr)
            if key is None:
                continue
            if confirm:
                if key in ENTER_KEYS:
                    return confirm
                confirm = None
                continue
            if key in QUIT_KEYS:
                return "resume"
            cursor, ok = navigate(key, cursor, len(self.ITEMS))
            if ok:
                action = self.ITEMS[cursor][0]
                if action in ("menu", "quit"):
                    confirm = action
                else:
                    return action

    def _draw(self, cursor: int, confirm) -> None:
        scr, s = self.scr, self.state
        scr.erase()
        height, width = scr.getmaxyx()
        ui = colors.attr("ui")
        top = max(1, (height - 16) // 2)
        center(scr, top, "ПАУЗА", colors.attr("title"))
        center(scr, top + 1, "-" * 40, ui)
        for i, line in enumerate(stats_lines(s)):
            center(scr, top + 2 + i, line, colors.attr("log_new"))
        slot = f"слот {s.slot}" if s.slot else "ще не збережено вручну"
        center(scr, top + 6, f"Останнє ручне збереження: {slot}", colors.attr("log_old"))
        draw_options(scr, top + 8, [label for _, label in self.ITEMS], cursor)
        center(scr, height - 1, "W/S вибір   Enter підтвердити   Esc назад до гри", ui)
        if confirm:
            draw_box(scr, ["Вийти без збереження?", "Незбережений прогрес буде втрачено.", "",
                           "Enter - так, інша клавіша - ні"], colors.attr("hp_bad"))
        scr.refresh()


# =====================================================================
class DeathScreen:
    """Екран смерті. Повертає: respawn | load | menu."""

    def __init__(self, scr, state, can_load: bool):
        self.scr = scr
        self.state = state
        self.quote = random.choice(DEATH_QUOTES)
        self.options = [("respawn", "Відродитись на площі Ельдорії")]
        if can_load:
            self.options.append(("load", "Завантажити останнє збереження"))
        self.options.append(("menu", "Вийти в головне меню"))

    def run(self) -> str:
        cursor = 0
        while True:
            self._draw(cursor)
            key = read_key(self.scr)
            if key is None:
                continue
            cursor, ok = navigate(key, cursor, len(self.options))
            if ok:
                return self.options[cursor][0]

    def _draw(self, cursor: int) -> None:
        scr = self.scr
        scr.erase()
        height, _ = scr.getmaxyx()
        top = max(0, (height - 24) // 2)
        for i, line in enumerate(TOMBSTONE):
            center(scr, top + i, line, colors.attr("wall"))
        center(scr, top + 7, "ТИ ЗАГИНУВ", colors.attr("hp_bad"))
        center(scr, top + 8, self.quote, colors.attr("log_old"))
        for i, line in enumerate(stats_lines(self.state)):
            center(scr, top + 10 + i, line, colors.attr("log_new"))
        center(scr, top + 15, "Смерть коштує 50% досвіду й 10% золота.", colors.attr("log_old"))
        draw_options(scr, top + 17, [label for _, label in self.options], cursor)
        center(scr, height - 1, "W/S вибір   Enter підтвердити", colors.attr("ui"))
        scr.refresh()


# =====================================================================
class VictoryScreen:
    """Екран перемоги над Володарем Безодні. Повертає: continue | menu."""

    EPILOGUE = ("Володар Безодні повалений, а розлом між світами зачинено. "
                "Ельдорія вільна від пітьми, і ім'я героя звучатиме в піснях. "
                "Та світ не закінчується: лишились невиконані завдання, "
                "рідкісні скарби й нові небезпеки.")
    OPTIONS = [("continue", "Продовжити грати"), ("menu", "Вийти в головне меню")]

    def __init__(self, scr, state):
        self.scr = scr
        self.state = state

    def run(self) -> str:
        cursor = 0
        while True:
            self._draw(cursor)
            key = read_key(self.scr)
            if key is None:
                continue
            cursor, ok = navigate(key, cursor, len(self.OPTIONS))
            if ok:
                return self.OPTIONS[cursor][0]

    def _draw(self, cursor: int) -> None:
        scr = self.scr
        scr.erase()
        height, width = scr.getmaxyx()
        top = max(0, (height - 26) // 2)
        for i, line in enumerate(big_text("VICTORY")):
            center(scr, top + i, line, colors.attr("gold"))
        center(scr, top + 6, "*  *  *   Е Л Ь Д О Р І Я   В І Л Ь Н А   *  *  *", colors.attr("title"))
        for i, line in enumerate(textwrap.wrap(self.EPILOGUE, min(60, width - 6))):
            center(scr, top + 8 + i, line, colors.attr("log_new"))
        for i, line in enumerate(stats_lines(self.state)):
            center(scr, top + 14 + i, line, colors.attr("hp_good"))
        draw_options(scr, top + 19, [label for _, label in self.OPTIONS], cursor)
        center(scr, height - 1, "W/S вибір   Enter підтвердити", colors.attr("ui"))
        scr.refresh()


# =====================================================================
class HelpScreen:
    """Довідка: клавіші та підказки. W/S - прокрутка, Esc - закрити."""

    def __init__(self, scr):
        self.scr = scr

    @staticmethod
    def _lines() -> list[tuple[str, str]]:
        def row(keys: str, text: str) -> tuple[str, str]:
            return f"  {keys:<22}{text}", "default"

        lines = [("КЕРУВАННЯ", "title"),
                 row("WASD / стрілки / ЦФІВ", "рух; йти на ворога = атака; на & = розмова"),
                 row("F / А", "вміння класу (витрачає ману)"),
                 row("R / К / пробіл", "відпочити (не працює біля ворога)"),
                 row("I / Ш", "рюкзак і спорядження"),
                 row("G / П", "підібрати здобич (автопідбір теж є)"),
                 row("1 / 2", "швидке зілля здоров'я / мани"),
                 row("J / О", "журнал завдань"),
                 row("M / Ь", "карта світу"),
                 row("P / З", "швидке збереження"),
                 row("H / Р", "ця довідка"),
                 row("Esc / Q", "меню паузи (збереження, вихід)"),
                 ("", "default"),
                 ("ПОРАДИ", "title"),
                 ("  Місто безпечне: монстри не заходять, а HP й мана відновлюються швидко.", "default"),
                 ("  Над NPC світиться ! (новий квест) або ? (можна здати).", "default"),
                 ("  Монстри з часом міцнішають (Загроза у панелі). Не барися з прокачкою.", "default"),
                 ("  Біоми: захід - зелені землі, схід - пустеля, північ - сніги, південь - болота.", "default"),
                 ("  Входи в підземелля (>) шукай за містом; чутки в таверні відкривають їх на карті.", "default"),
                 ("  Боси шаленіють при 30% HP й кличуть підмогу при 50%.", "default"),
                 ("  Лавки, крафт і аукціон з ботами працюють у будівлях міста.", "default"),
                 ("  Світові події (ярмарок, кривавий місяць, вторгнення) видно в панелі.", "default"),
                 ("  Мета: пройти ланцюжок Мірона й здолати Володаря Безодні.", "default"),
                 ("  Гра автоматично зберігається кожні 300 ходів (слот «Автозбереження»).", "default")]
        if DEBUG:
            lines += [("", "default"), ("DEBUG-КЛАВІШІ", "title"),
                      row("+", "50 досвіду"), row("L", "3 випадкові предмети"),
                      row("$", "+500 золота"), row("V", "вимк./увімк. туман"),
                      row("]", "перемотати 200 ходів"), row("T", "телепорт"),
                      row("K", "виконати активні квести"), row("E", "запустити світову подію")]
        return lines

    def run(self) -> None:
        lines = self._lines()
        top = 0
        while True:
            self._draw(lines, top)
            key = read_key(self.scr)
            if key is None:
                continue
            if key in QUIT_KEYS or key in HELP_KEYS or key in ENTER_KEYS:
                return
            visible = max(1, self.scr.getmaxyx()[0] - 4)
            if key in MENU_UP:
                top = max(0, top - 1)
            elif key in MENU_DOWN:
                top = max(0, min(top + 1, len(lines) - visible))

    def _draw(self, lines, top: int) -> None:
        scr = self.scr
        scr.erase()
        height, width = scr.getmaxyx()
        ui = colors.attr("ui")
        put(scr, 0, 1, "ДОВІДКА", colors.attr("title"))
        put(scr, 1, 0, "-" * width, ui)
        for i, (text, color) in enumerate(lines[top:top + height - 4]):
            put(scr, 2 + i, 1, text, colors.attr(color))
        put(scr, height - 1, 1, "W/S прокрутка   Esc / Enter закрити", ui)
        scr.refresh()