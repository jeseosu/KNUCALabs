"""Меню рюкзака та спорядження."""
import curses
import textwrap
from functools import lru_cache

from game.config import (INVENTORY_KEYS, MENU_CONFIRM, MENU_DOWN, MENU_DROP,
                         MENU_SORT, MENU_SWITCH, MENU_UP, QUIT_KEYS,
                         THREAT_RADIUS, load_json)
from game.items.item import Item, slot_names
from game.ui import colors
from game.ui.renderer import put

CLOSE_KEYS = INVENTORY_KEYS | QUIT_KEYS
LEFT_W = 38        # ширина лівої панелі (рюкзак)


@lru_cache(maxsize=1)
def _class_names() -> dict[str, str]:
    return {cid: data["name"] for cid, data in load_json("classes.json").items()}


class InventoryMenu:
    def __init__(self, stdscr, state):
        self.scr = stdscr
        self.state = state
        self.focus = "bag"                  # "bag" - рюкзак, "equip" - спорядження
        self.cursor = 0
        self.slot_cursor = 0
        self.slots = list(slot_names())
        self.note = ""
        self.turns = 0                      # скільки ходів забрали дії в меню

    # ---------- головний цикл ----------
    def run(self) -> int:
        """Показує меню. Повертає кількість ходів, витрачених на дії в бою."""
        while True:
            self._draw()
            try:
                key = self.scr.get_wch()
            except curses.error:
                continue
            if key == curses.KEY_RESIZE:
                self.scr.clear()
                continue
            if key in CLOSE_KEYS:
                break
            self._handle(key)
        return self.turns

    # ---------- ввід ----------
    def _handle(self, key) -> None:
        if key in MENU_UP:
            self._move(-1)
        elif key in MENU_DOWN:
            self._move(1)
        elif key in MENU_SWITCH:
            self.focus = "equip" if self.focus == "bag" else "bag"
        elif key in MENU_CONFIRM:
            self._confirm()
        elif key in MENU_DROP and self.focus == "bag":
            self._drop()
        elif key in MENU_SORT:
            self.state.player.inventory.sort()
            self.note = "Рюкзак відсортовано."

    def _move(self, delta: int) -> None:
        if self.focus == "bag":
            count = len(self.state.player.inventory.stacks)
            if count:
                self.cursor = (self.cursor + delta) % count
        else:
            self.slot_cursor = (self.slot_cursor + delta) % len(self.slots)

    def _confirm(self) -> None:
        p = self.state.player
        if self.focus == "bag":
            if not p.inventory.stacks:
                return
            item = p.inventory.stacks[self.cursor].item
            result = p.equip(self.cursor) if item.equippable else p.use_item(self.cursor)
        else:
            result = p.unequip(self.slots[self.slot_cursor])
        self._report(*result)
        self._clamp()

    def _report(self, ok: bool, message: str) -> None:
        self.note = message
        if ok:
            self.state.log(message)
            # у бою дія з предметом забирає хід
            if self.state.nearest_monster(THREAT_RADIUS):
                self.turns += 1

    def _drop(self) -> None:
        inv = self.state.player.inventory
        if not inv.stacks:
            return
        item = inv.remove_at(self.cursor)
        self.note = f"Ти викидаєш: {item.name}."
        self.state.log(self.note)
        self._clamp()

    def _clamp(self) -> None:
        count = len(self.state.player.inventory.stacks)
        self.cursor = max(0, min(self.cursor, count - 1))

    # ---------- допоміжне ----------
    def _selected_item(self) -> Item | None:
        inv = self.state.player.inventory
        if self.focus == "bag":
            if inv.stacks and self.cursor < len(inv.stacks):
                return inv.stacks[self.cursor].item
            return None
        return inv.equipment[self.slots[self.slot_cursor]]

    def _is_upgrade(self, item: Item) -> bool:
        p = self.state.player
        if not item.equippable or item.level_req > p.level:
            return False
        if item.classes and p.class_id not in item.classes:
            return False
        current = p.inventory.equipment.get(item.slot)
        return current is None or item.score > current.score

    @staticmethod
    def _kind_label(item: Item) -> str:
        if item.equippable:
            return slot_names()[item.slot].lower()
        return {"consumable": "зілля / їжа", "material": "матеріал"}.get(item.kind, item.kind)

    def _compare(self, item: Item) -> tuple[str, str]:
        current = self.state.player.inventory.equipment.get(item.slot)

        def stat(it, key):
            return it.stats.get(key, 0) if it else 0

        parts, total = [], 0
        for key, label, mult in (("attack", "атака", 1), ("defense", "захист", 1),
                                 ("crit", "крит %", 100)):
            diff = round((stat(item, key) - stat(current, key)) * mult)
            if diff:
                parts.append(f"{label} {diff:+d}")
                total += diff
        if not parts:
            return "Проти одягненого: без змін", "default"
        color = "hp_good" if total > 0 else "hp_bad" if total < 0 else "default"
        return "Проти одягненого: " + ", ".join(parts), color

    def _item_lines(self, item: Item, width: int) -> list[tuple[str, str]]:
        p = self.state.player
        lines: list[tuple[str, str]] = []

        def add(text: str, color: str = "default") -> None:
            for part in textwrap.wrap(text, width) or [""]:
                lines.append((part, color))

        add(item.name, item.color)
        add(f"{item.rarity_name} ({self._kind_label(item)})", item.color)

        s = item.stats
        if s.get("attack"):
            add(f"Атака +{s['attack']}")
        if s.get("defense"):
            add(f"Захист +{s['defense']}")
        if s.get("crit"):
            add(f"Шанс крита +{round(s['crit'] * 100)}%")
        if item.effect.get("heal"):
            add(f"Лікує {item.effect['heal']} HP", "hp_good")
        if item.effect.get("mana"):
            add(f"Відновлює {item.effect['mana']} мани", "mp")

        if item.level_req > 1:
            add(f"Потрібен рівень {item.level_req}",
                "hp_bad" if item.level_req > p.level else "default")
        if item.classes:
            names = ", ".join(_class_names()[c] for c in item.classes)
            add(f"Клас: {names}", "default" if p.class_id in item.classes else "hp_bad")

        if self.focus == "bag" and item.equippable:
            text, color = self._compare(item)
            add(text, color)

        if item.desc:
            add(item.desc, "log_old")
        add(f"Ціна: {item.value} золота", "gold")
        return lines

    # ---------- малювання ----------
    def _draw(self) -> None:
        scr = self.scr
        scr.erase()
        height, width = scr.getmaxyx()
        p = self.state.player
        inv = p.inventory
        ui = colors.attr("ui")
        title = colors.attr("title")
        right_x = LEFT_W + 3
        right_w = max(10, width - right_x - 1)

        put(scr, 0, 1, f"РЮКЗАК  {len(inv.stacks)}/{inv.capacity}", title)
        put(scr, 0, right_x, "СПОРЯДЖЕННЯ", title)
        put(scr, 1, 0, "-" * width, ui)
        for y in range(2, height - 4):
            put(scr, y, LEFT_W + 1, "|", ui)

        # --- ліва панель: список предметів ---
        visible = max(1, height - 6)
        count = len(inv.stacks)
        top = max(0, min(self.cursor - visible // 2, count - visible))
        if count == 0:
            put(scr, 2, 2, "(порожньо)", colors.attr("log_old"))
        for row in range(visible):
            idx = top + row
            if idx >= count:
                break
            stack = inv.stacks[idx]
            item = stack.item
            selected = self.focus == "bag" and idx == self.cursor
            reverse = curses.A_REVERSE if selected else 0
            suffix = f" x{stack.count}" if stack.count > 1 else ""
            text = f"{'>' if selected else ' '} {item.name}{suffix}"
            put(scr, 2 + row, 1, text[:LEFT_W - 1].ljust(LEFT_W - 1),
                colors.attr(item.color) | reverse)
            if self._is_upgrade(item):
                put(scr, 2 + row, 2, "^", colors.attr("hp_good") | reverse)

        # --- права панель: спорядження ---
        for i, slot in enumerate(self.slots):
            item = inv.equipment[slot]
            selected = self.focus == "equip" and i == self.slot_cursor
            reverse = curses.A_REVERSE if selected else 0
            label = slot_names()[slot]
            name = item.name if item else "-"
            text = f"{'>' if selected else ' '} {label:<8}{name}"
            color = colors.attr(item.color) if item else colors.attr("log_old")
            put(scr, 2 + i, right_x, text[:right_w].ljust(right_w), color | reverse)

        put(scr, 8, right_x,
            f"Атака {p.power}  Захист {p.armor}  Крит {round(p.crit_chance * 100)}%")
        put(scr, 9, right_x, f"Золото: {p.gold}", colors.attr("gold"))
        put(scr, 10, right_x, "-" * right_w, ui)

        # --- опис вибраного предмета ---
        item = self._selected_item()
        row = 11
        if item is None:
            put(scr, row, right_x, "Нічого не вибрано.", colors.attr("log_old"))
        else:
            for text, color in self._item_lines(item, right_w):
                if row >= height - 5:
                    break
                put(scr, row, right_x, text, colors.attr(color))
                row += 1

        # --- низ ---
        put(scr, height - 4, 0, "-" * width, ui)
        put(scr, height - 3, 1, self.note, colors.attr("log_new"))
        put(scr, height - 2, 1, "W/S вибір  Tab панель  Enter/E одягнути, використати", ui)
        put(scr, height - 1, 1, "X викинути  T сортувати  I/Esc закрити  ^ краще за одягнене", ui)
        scr.refresh()