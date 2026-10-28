"""Екрани економіки: крамниця, крафт, аукціон."""
import curses
import textwrap
from functools import lru_cache

from game.config import (MENU_CONFIRM, MENU_DOWN, MENU_SWITCH, MENU_UP,
                         QUIT_KEYS, load_json)
from game.items.item import get_item
from game.systems import crafting, market
from game.ui import colors
from game.ui.renderer import put

SELL_ALL_KEYS = {"x", "X", "ч", "Ч"}
CLAIM_KEYS = {"c", "C", "с", "С"}
ENTER_KEYS = {"\n", "\r", curses.KEY_ENTER}
BACKSPACE_KEYS = {curses.KEY_BACKSPACE, "\x7f", "\b", 127}
PREV_TAB = {curses.KEY_LEFT, "a", "A", "ф", "Ф"}
NEXT_TAB = {curses.KEY_RIGHT, "d", "D", "в", "В", "\t"}


def _read(scr):
    try:
        key = scr.get_wch()
    except curses.error:
        return None
    if key == curses.KEY_RESIZE:
        scr.clear()
        return None
    return key


@lru_cache(maxsize=1)
def _class_names() -> dict[str, str]:
    return {cid: d["name"] for cid, d in load_json("classes.json").items()}


def stat_line(item) -> str:
    s, parts = item.stats, []
    if s.get("attack"):
        parts.append(f"Атака +{s['attack']}")
    if s.get("defense"):
        parts.append(f"Захист +{s['defense']}")
    if s.get("crit"):
        parts.append(f"Крит +{round(s['crit'] * 100)}%")
    if item.effect.get("heal"):
        parts.append(f"Лікує {item.effect['heal']}")
    if item.effect.get("mana"):
        parts.append(f"Мана +{item.effect['mana']}")
    if item.level_req > 1:
        parts.append(f"рів.{item.level_req}")
    if item.classes:
        parts.append("/".join(_class_names()[c] for c in item.classes))
    return ", ".join(parts)


def _window(cursor: int, count: int, visible: int) -> int:
    return max(0, min(cursor - visible // 2, count - visible))


def _row_text(left: str, right: str, width: int) -> str:
    left = left[: max(0, width - len(right) - 1)]
    return left.ljust(width - len(right)) + right


# =====================================================================
class ShopMenu:
    """Крамниця: ліворуч купити, праворуч продати."""

    def __init__(self, stdscr, state, shop_id: str):
        self.scr = stdscr
        self.state = state
        self.shop_id = shop_id
        self.cfg = market.shop_defs()[shop_id]
        self.focus = "buy"
        self.cursor = {"buy": 0, "sell": 0}
        self.note = ""

    def _rows(self, focus: str):
        p = self.state.player
        if focus == "buy":
            return [(item, n) for item, n in market.shop_stock(self.state, self.shop_id)
                    if not item.classes or p.class_id in item.classes]
        return [(i, s) for i, s in enumerate(p.inventory.stacks)
                if s.item.kind in self.cfg["buys"]]

    def run(self) -> None:
        while True:
            self._draw()
            key = _read(self.scr)
            if key is None:
                continue
            if key in QUIT_KEYS:
                break
            if key in MENU_SWITCH:
                self.focus = "sell" if self.focus == "buy" else "buy"
            elif key in MENU_UP:
                self._move(-1)
            elif key in MENU_DOWN:
                self._move(1)
            elif key in MENU_CONFIRM:
                self._act(False)
            elif key in SELL_ALL_KEYS and self.focus == "sell":
                self._act(True)
            for f in ("buy", "sell"):
                n = len(self._rows(f))
                self.cursor[f] = max(0, min(self.cursor[f], n - 1))

    def _move(self, delta: int) -> None:
        n = len(self._rows(self.focus))
        if n:
            self.cursor[self.focus] = (self.cursor[self.focus] + delta) % n

    def _act(self, all_stack: bool) -> None:
        rows = self._rows(self.focus)
        if not rows:
            return
        row = rows[min(self.cursor[self.focus], len(rows) - 1)]
        if self.focus == "buy":
            ok, msg = market.buy_from_shop(self.state, self.shop_id, row[0])
        else:
            ok, msg = market.sell_to_shop(self.state, self.shop_id, row[0], all_stack)
        self.note = msg

    def _draw(self) -> None:
        scr, state = self.scr, self.state
        scr.erase()
        h, w = scr.getmaxyx()
        ui, title = colors.attr("ui"), colors.attr("title")
        mid = w // 2
        col_w = mid - 3

        put(scr, 0, 1, self.cfg["title"], title)
        gold = f"Золото: {state.player.gold}"
        put(scr, 0, max(1, w - len(gold) - 2), gold, colors.attr("gold"))
        put(scr, 1, 0, "-" * w, ui)
        for y in range(2, h - 5):
            put(scr, y, mid, "|", ui)
        put(scr, 2, 1, "КУПИТИ", title if self.focus == "buy" else ui)
        put(scr, 2, mid + 2, "ПРОДАТИ (ціна за 1 шт.)", title if self.focus == "sell" else ui)

        visible = h - 9
        selected_item = None
        for focus, x in (("buy", 1), ("sell", mid + 2)):
            rows = self._rows(focus)
            cur = self.cursor[focus]
            top = _window(cur, len(rows), visible)
            for r in range(visible):
                i = top + r
                if i >= len(rows):
                    break
                sel = self.focus == focus and i == cur
                reverse = curses.A_REVERSE if sel else 0
                if focus == "buy":
                    item, n = rows[i]
                    right = f"{market.shop_price(state, item)}з" + (f" x{n}" if n else " --")
                    color = item.color if n else "log_old"
                else:
                    _, stack = rows[i]
                    item = stack.item
                    cnt = f" x{stack.count}" if stack.count > 1 else ""
                    right = f"{market.sell_price(state, self.shop_id, item)}з"
                    color = item.color
                    name_part = item.name + cnt
                text = _row_text(f"{'>' if sel else ' '} " + (item.name if focus == "buy" else name_part),
                                 right, col_w)
                put(scr, 3 + r, x, text, colors.attr(color) | reverse)
                if sel:
                    selected_item = item

        put(scr, h - 5, 0, "-" * w, ui)
        if selected_item:
            put(scr, h - 4, 1, f"{selected_item.name}: {stat_line(selected_item)}",
                colors.attr(selected_item.color))
            put(scr, h - 3, 1, selected_item.desc, colors.attr("log_old"))
        event = state.events.current
        if event and (state.events.mult("shop_mult") != 1 or state.events.mult("sell_mult") != 1):
            put(scr, h - 3, max(1, w - 30), f"Подія: {event['name']}", colors.attr("title"))
        put(scr, h - 2, 1, self.note, colors.attr("log_new"))
        put(scr, h - 1, 1, "W/S вибір  Tab купити/продати  Enter 1 шт.  X усе  Esc вийти", ui)
        scr.refresh()


# =====================================================================
class CraftMenu:
    """Крафт: список рецептів станції та потрібні матеріали."""

    def __init__(self, stdscr, state, station: str):
        self.scr = stdscr
        self.state = state
        self.station = station
        self.recipes = crafting.recipes_for(station, state.player.class_id)
        self.cursor = 0
        self.note = ""

    def run(self) -> None:
        while True:
            self._draw()
            key = _read(self.scr)
            if key is None:
                continue
            if key in QUIT_KEYS:
                break
            n = len(self.recipes)
            if not n:
                continue
            if key in MENU_UP:
                self.cursor = (self.cursor - 1) % n
            elif key in MENU_DOWN:
                self.cursor = (self.cursor + 1) % n
            elif key in MENU_CONFIRM:
                ok, msg = crafting.craft(self.state, self.recipes[self.cursor])
                self.note = msg
                if ok:
                    self.state.log(msg)

    def _draw(self) -> None:
        scr, state = self.scr, self.state
        scr.erase()
        h, w = scr.getmaxyx()
        ui, title = colors.attr("ui"), colors.attr("title")
        inv = state.player.inventory
        left_w = 38

        put(scr, 0, 1, f"КРАФТ: {crafting.station_title(self.station)}", title)
        gold = f"Золото: {state.player.gold}"
        put(scr, 0, max(1, w - len(gold) - 2), gold, colors.attr("gold"))
        put(scr, 1, 0, "-" * w, ui)
        for y in range(2, h - 4):
            put(scr, y, left_w + 1, "|", ui)

        visible = h - 7
        top = _window(self.cursor, len(self.recipes), visible)
        for r in range(visible):
            i = top + r
            if i >= len(self.recipes):
                break
            recipe = self.recipes[i]
            item = get_item(recipe["output"][0])
            ok, _ = crafting.can_craft(state, recipe)
            sel = i == self.cursor
            count = recipe["output"][1]
            name = item.name + (f" x{count}" if count > 1 else "")
            text = f"{'>' if sel else ' '}{'+' if ok else ' '} {name}"
            attr = colors.attr(item.color if ok else "log_old") | (curses.A_REVERSE if sel else 0)
            put(scr, 2 + r, 1, text[:left_w - 1].ljust(left_w - 1), attr)

        x = left_w + 3
        if not self.recipes:
            put(scr, 2, x, "Рецептів для твого класу немає.", colors.attr("log_old"))
        else:
            recipe = self.recipes[self.cursor]
            item = get_item(recipe["output"][0])
            put(scr, 2, x, item.name, colors.attr(item.color))
            put(scr, 3, x, f"{item.rarity_name}: {stat_line(item)}"[: w - x - 1])
            put(scr, 4, x, item.desc[: w - x - 1], colors.attr("log_old"))
            put(scr, 6, x, "Потрібно:", title)
            row = 7
            for item_id, need in recipe["inputs"]:
                have = inv.count(item_id)
                put(scr, row, x, f"  {get_item(item_id).name}: {have}/{need}",
                    colors.attr("hp_good" if have >= need else "hp_bad"))
                row += 1
            cost = recipe.get("gold", 0)
            put(scr, row, x, f"  Золото: {cost}",
                colors.attr("hp_good" if state.player.gold >= cost else "hp_bad"))
            lvl = recipe.get("level_req", 1)
            put(scr, row + 1, x, f"  Рівень: {lvl}",
                colors.attr("hp_good" if state.player.level >= lvl else "hp_bad"))
            _, reason = crafting.can_craft(state, recipe)
            if reason:
                put(scr, row + 3, x, reason, colors.attr("hp_bad"))

        put(scr, h - 4, 0, "-" * w, ui)
        put(scr, h - 3, 1, self.note, colors.attr("log_new"))
        put(scr, h - 1, 1, "W/S вибір  Enter створити  Esc вийти  (+ = можна створити)", ui)
        scr.refresh()


# =====================================================================
class AuctionMenu:
    """Аукціон: лоти ботів, власні лоти, виставлення предметів, пошта."""

    TABS = ("Лоти", "Мої лоти", "Виставити")

    def __init__(self, stdscr, state):
        self.scr = stdscr
        self.state = state
        self.market = state.market
        self.tab = 0
        self.cursor = [0, 0, 0]
        self.note = ""

    def _rows(self):
        m = self.market
        if self.tab == 0:
            lots = [lot for lot in m.lots if not lot.mine]
            lots.sort(key=lambda l: (-get_item(l.item_id).rank, get_item(l.item_id).name, l.price))
            return lots
        if self.tab == 1:
            return [lot for lot in m.lots if lot.mine]
        return list(enumerate(self.state.player.inventory.stacks))

    def run(self) -> None:
        while True:
            self._draw()
            key = _read(self.scr)
            if key is None:
                continue
            if key in QUIT_KEYS:
                break
            rows = self._rows()
            n = len(rows)
            if key in PREV_TAB:
                self.tab = (self.tab - 1) % 3
            elif key in NEXT_TAB:
                self.tab = (self.tab + 1) % 3
            elif key in MENU_UP and n:
                self.cursor[self.tab] = (self.cursor[self.tab] - 1) % n
            elif key in MENU_DOWN and n:
                self.cursor[self.tab] = (self.cursor[self.tab] + 1) % n
            elif key in CLAIM_KEYS:
                self.note = self.market.claim(self.state)[1]
            elif key in MENU_CONFIRM and n:
                self._act(rows[self.cursor[self.tab]])
            n = len(self._rows())
            self.cursor[self.tab] = max(0, min(self.cursor[self.tab], n - 1))

    def _act(self, row) -> None:
        if self.tab == 0:
            self.note = self.market.buy_lot(self.state, row.id)[1]
        elif self.tab == 1:
            self.note = self.market.cancel_lot(self.state, row.id)[1]
        else:
            self._sell(row)

    def _sell(self, row) -> None:
        index, stack = row
        item = stack.item
        count = 1
        if stack.count > 1:
            count = self._ask("Скільки штук", stack.count, 1, stack.count)
            if count is None:
                return
        fair = self.market.fair_price(item, count)
        price = self._ask(f"Ціна за весь лот (справедлива ~{fair})", fair, 1, 999999)
        if price is None:
            return
        self.note = self.market.list_item(self.state, index, count, price)[1]

    def _ask(self, label: str, default: int, lo: int, hi: int):
        """Просте введення числа. Повертає число або None (Esc)."""
        text = str(default)
        while True:
            self._draw(prompt=f"{label} [{lo}-{hi}]: {text}_")
            key = _read(self.scr)
            if key is None:
                continue
            if key in QUIT_KEYS:
                return None
            if key in ENTER_KEYS:
                value = int(text) if text else lo
                return max(lo, min(hi, value))
            if key in BACKSPACE_KEYS:
                text = text[:-1]
            elif isinstance(key, str) and key.isdigit() and len(text) < 7:
                text = key if text == "0" else text + key

    def _draw(self, prompt: str | None = None) -> None:
        scr, state, m = self.scr, self.state, self.market
        scr.erase()
        h, w = scr.getmaxyx()
        ui, title = colors.attr("ui"), colors.attr("title")
        side_w = 34
        list_w = max(30, w - side_w - 4)
        side_x = list_w + 3

        put(scr, 0, 1, "АУКЦІОН ЕЛЬДОРІЇ", title)
        gold = f"Золото: {state.player.gold}"
        put(scr, 0, max(1, w - len(gold) - 2), gold, colors.attr("gold"))
        x = 1
        for i, name in enumerate(self.TABS):
            label = f" {name} "
            put(scr, 1, x, label, title | (curses.A_REVERSE if i == self.tab else 0))
            x += len(label) + 1
        put(scr, 2, 0, "-" * w, ui)
        for y in range(3, h - 6):
            put(scr, y, side_x - 1, "|", ui)

        rows = self._rows()
        cur = self.cursor[self.tab]
        visible = h - 10
        top = _window(cur, len(rows), visible)
        if not rows:
            empty = ("Лотів немає.", "Ти ще нічого не виставив.", "Рюкзак порожній.")[self.tab]
            put(scr, 3, 2, empty, colors.attr("log_old"))
        selected = None
        for r in range(visible):
            i = top + r
            if i >= len(rows):
                break
            sel = i == cur
            reverse = curses.A_REVERSE if sel else 0
            if self.tab == 2:
                _, stack = rows[i]
                item = stack.item
                name = item.name + (f" x{stack.count}" if stack.count > 1 else "")
                right = f"~{m.fair_price(item, stack.count)}з"
            else:
                lot = rows[i]
                item = get_item(lot.item_id)
                name = item.name + (f" x{lot.count}" if lot.count > 1 else "")
                if self.tab == 0:
                    ratio = round(100 * lot.price / m.fair_price(item, lot.count))
                    right = f"{lot.price}з {ratio}%"
                else:
                    right = f"{lot.price}з ост.{max(0, lot.expires - state.turn)}"
            text = _row_text(f"{'>' if sel else ' '} {name}", right, list_w)
            put(scr, 3 + r, 1, text, colors.attr(item.color) | reverse)
            if sel:
                selected = rows[i]

        # права панель: пошта та новини
        put(scr, 3, side_x, "ПОШТА (C - забрати)", title)
        put(scr, 4, side_x, f"  золото: {m.mail_gold}", colors.attr("gold"))
        put(scr, 5, side_x, f"  предметів: {len(m.mail_items)}")
        put(scr, 7, side_x, "НОВИНИ РИНКУ", title)
        wrapped = []
        for line in m.feed:
            wrapped += textwrap.wrap(line, side_w - 2) or [""]
        space = h - 6 - 8
        for i, line in enumerate(wrapped[-space:] if space > 0 else []):
            put(scr, 8 + i, side_x, line, colors.attr("log_old"))

        # деталі вибраного
        put(scr, h - 6, 0, "-" * w, ui)
        if selected is not None:
            if self.tab == 2:
                item, extra = selected[1].item, ""
            else:
                item = get_item(selected.item_id)
                extra = f"Продавець: {selected.seller}. Справедлива ціна: {m.fair_price(item, selected.count)}з"
            put(scr, h - 5, 1, f"{item.name}: {stat_line(item)}", colors.attr(item.color))
            put(scr, h - 4, 1, item.desc, colors.attr("log_old"))
            put(scr, h - 3, 1, extra, ui)
        put(scr, h - 2, 1, prompt if prompt else self.note,
            colors.attr("title" if prompt else "log_new"))
        helps = ("W/S вибір  Enter купити  A/D вкладка  C пошта  Esc вийти",
                 "W/S вибір  Enter зняти лот  A/D вкладка  C пошта  Esc вийти",
                 "W/S вибір  Enter виставити  A/D вкладка  C пошта  Esc вийти")
        put(scr, h - 1, 1, helps[self.tab], ui)
        scr.refresh()