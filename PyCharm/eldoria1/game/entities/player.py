"""Гравець: клас, рівні, досвід, вміння, інвентар, спорядження."""
from game.config import CRIT_CHANCE, START_GOLD, load_json
from game.entities.entity import Entity
from game.items.inventory import Inventory
from game.items.item import get_item, starting_kit


class Player(Entity):
    def __init__(self, name: str, class_id: str, x: int = 0, y: int = 0):
        classes = load_json("classes.json")
        if class_id not in classes:
            raise ValueError(f"Невідомий клас: {class_id}")
        data = classes[class_id]
        base = data["base"]

        super().__init__(name, x, y, "@", "player",
                         base["max_hp"], base["attack"], base["defense"])

        self.class_id = class_id
        self.class_name = data["name"]
        self.per_level = data["per_level"]
        self.skill = data["skill"]
        self.max_mp = base["max_mp"]
        self.mp = self.max_mp
        self.level = 1
        self.xp = 0
        self.gold = START_GOLD
        self.inventory = Inventory()
        self._give_starting_kit(class_id)

    def _give_starting_kit(self, class_id: str) -> None:
        kit = starting_kit(class_id)
        for item_id in kit.get("equip", []):
            item = get_item(item_id)
            self.inventory.equipment[item.slot] = item
        for item_id, count in kit.get("items", []):
            self.inventory.add(get_item(item_id), count)

    # ---------- характеристики з урахуванням спорядження ----------
    @property
    def power(self) -> int:
        return self.attack + int(self.inventory.bonus("attack"))

    @property
    def armor(self) -> int:
        return self.defense + int(self.inventory.bonus("defense"))

    @property
    def crit_chance(self) -> float:
        return CRIT_CHANCE + self.inventory.bonus("crit")

    # ---------- досвід ----------
    @property
    def xp_to_next(self) -> int:
        """Скільки XP потрібно для наступного рівня."""
        return int(40 * self.level ** 1.6)

    def gain_xp(self, amount: int) -> list[str]:
        """Додає XP. Повертає список повідомлень (про отриманий досвід і рівні)."""
        messages = [f"Ти отримуєш {amount} досвіду."]
        self.xp += amount
        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            messages.append(self._level_up())
        return messages

    def _level_up(self) -> str:
        self.level += 1
        self.max_hp += self.per_level["max_hp"]
        self.max_mp += self.per_level["max_mp"]
        self.attack += self.per_level["attack"]
        self.defense += self.per_level["defense"]
        self.hp = self.max_hp
        self.mp = self.max_mp
        return f"*** НОВИЙ РІВЕНЬ! Тепер ти {self.level} рівня. ***"

    def restore_mp(self, amount: int) -> int:
        """Відновлює ману, повертає скільки реально відновлено."""
        before = self.mp
        self.mp = min(self.max_mp, self.mp + amount)
        return self.mp - before

    def revive(self, xp_loss_pct: float) -> int:
        """Відродження після смерті: повне HP/MP, штраф до XP. Повертає втрачений XP."""
        lost = int(self.xp * xp_loss_pct)
        self.xp -= lost
        self.hp = self.max_hp
        self.mp = self.max_mp
        return lost

    # ---------- дії з предметами (повертають (успіх, повідомлення)) ----------
    def equip(self, index: int) -> tuple[bool, str]:
        stacks = self.inventory.stacks
        if not 0 <= index < len(stacks):
            return False, "Нічого не вибрано."
        item = stacks[index].item

        if not item.equippable:
            return False, f"{item.name} не можна одягнути."
        if item.level_req > self.level:
            return False, f"Потрібен {item.level_req} рівень, щоб одягнути: {item.name}."
        if item.classes and self.class_id not in item.classes:
            return False, f"{item.name} не підходить класу «{self.class_name}»."

        self.inventory.remove_at(index)          # звільняємо слот у рюкзаку
        old = self.inventory.equipment[item.slot]
        self.inventory.equipment[item.slot] = item
        if old is not None:
            self.inventory.add(old)              # місце гарантовано є
            return True, f"Ти одягаєш: {item.name} (замість {old.name})."
        return True, f"Ти одягаєш: {item.name}."

    def unequip(self, slot: str) -> tuple[bool, str]:
        item = self.inventory.equipment.get(slot)
        if item is None:
            return False, "Цей слот порожній."
        if self.inventory.free_space_for(item) < 1:
            return False, "Рюкзак повний!"
        self.inventory.equipment[slot] = None
        self.inventory.add(item)
        return True, f"Ти знімаєш: {item.name}."

    def use_item(self, index: int) -> tuple[bool, str]:
        stacks = self.inventory.stacks
        if not 0 <= index < len(stacks):
            return False, "Нічого не вибрано."
        item = stacks[index].item

        if item.kind != "consumable":
            return False, f"{item.name} не можна використати."

        heal = item.effect.get("heal", 0)
        mana = item.effect.get("mana", 0)
        need_heal = heal and self.hp < self.max_hp
        need_mana = mana and self.mp < self.max_mp
        if not (need_heal or need_mana):
            return False, "Тобі це зараз не потрібно."

        parts = []
        healed = self.heal(heal) if heal else 0
        restored = self.restore_mp(mana) if mana else 0
        if healed:
            parts.append(f"+{healed} HP")
        if restored:
            parts.append(f"+{restored} мани")

        self.inventory.remove_at(index)
        return True, f"Ти використовуєш: {item.name} ({', '.join(parts)})."

    def quick_use(self, kind: str) -> tuple[bool, str]:
        """Швидке зілля. kind: 'heal' або 'mana'. Бере найменше зілля, що вистачає."""
        missing = (self.max_hp - self.hp) if kind == "heal" else (self.max_mp - self.mp)
        if missing <= 0:
            return False, "Усе й так на максимумі."

        options = sorted(
            (s.item.effect[kind], i)
            for i, s in enumerate(self.inventory.stacks)
            if s.item.kind == "consumable" and s.item.effect.get(kind, 0) > 0
        )
        if not options:
            return False, "Немає відповідних зілль."
        for amount, index in options:
            if amount >= missing:
                return self.use_item(index)
        return self.use_item(options[-1][1])      # жодне не покриває - беремо найсильніше