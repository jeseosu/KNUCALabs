"""Рюкзак зі стеками та слоти екіпіровки."""
from dataclasses import dataclass

from game.config import INVENTORY_SIZE, MAX_STACK
from game.items.item import Item, get_item, slot_names


@dataclass
class ItemStack:
    item: Item
    count: int = 1


class Inventory:
    def __init__(self, capacity: int = INVENTORY_SIZE):
        self.capacity = capacity
        self.stacks: list[ItemStack] = []
        self.equipment: dict[str, Item | None] = {slot: None for slot in slot_names()}

    # ---------- місце ----------
    def free_space_for(self, item: Item) -> int:
        """Скільки штук цього предмета ще влізе в рюкзак."""
        free_slots = self.capacity - len(self.stacks)
        if item.stackable:
            room = sum(MAX_STACK - s.count for s in self.stacks if s.item.id == item.id)
            return room + free_slots * MAX_STACK
        return free_slots

    # ---------- додавання / видалення ----------
    def add(self, item: Item, count: int = 1) -> int:
        """Кладе предмети в рюкзак. Повертає, скільки штук реально влізло."""
        added = 0
        if item.stackable:
            for stack in self.stacks:               # спершу доповнюємо наявні стеки
                if stack.item.id == item.id and stack.count < MAX_STACK:
                    take = min(count - added, MAX_STACK - stack.count)
                    stack.count += take
                    added += take
                    if added == count:
                        return added
            while added < count and len(self.stacks) < self.capacity:
                take = min(count - added, MAX_STACK)
                self.stacks.append(ItemStack(item, take))
                added += take
        else:
            while added < count and len(self.stacks) < self.capacity:
                self.stacks.append(ItemStack(item, 1))
                added += 1
        return added

    def remove_at(self, index: int, count: int = 1) -> Item:
        """Забирає count штук зі стека за індексом. Повертає предмет."""
        stack = self.stacks[index]
        count = min(count, stack.count)
        stack.count -= count
        if stack.count <= 0:
            del self.stacks[index]
        return stack.item

    def count(self, item_id: str) -> int:
        return sum(s.count for s in self.stacks if s.item.id == item_id)

    def remove_by_id(self, item_id: str, count: int = 1) -> bool:
        """Забирає count штук предмета за id (знадобиться для крафту)."""
        if self.count(item_id) < count:
            return False
        for index in range(len(self.stacks) - 1, -1, -1):
            if count <= 0:
                break
            stack = self.stacks[index]
            if stack.item.id == item_id:
                take = min(count, stack.count)
                self.remove_at(index, take)
                count -= take
        return True

    def count_effect(self, kind: str) -> int:
        """Скільки зілль із ефектом kind (heal / mana) є в рюкзаку."""
        return sum(s.count for s in self.stacks
                   if s.item.kind == "consumable" and s.item.effect.get(kind, 0) > 0)

    # ---------- бонуси екіпіровки ----------
    def bonus(self, stat: str) -> float:
        return sum(item.stats.get(stat, 0)
                   for item in self.equipment.values() if item is not None)

    # ---------- сортування ----------
    def sort(self) -> None:
        """Спершу екіпіровка, потім зілля, потім матеріали; всередині: за рідкістю й назвою."""
        def group(item: Item) -> int:
            if item.equippable:
                return 0
            return 1 if item.kind == "consumable" else 2

        self.stacks.sort(key=lambda s: (group(s.item), -s.item.rank, s.item.name))

    # ---------- збереження (знадобиться на етапі 7) ----------
    def to_dict(self) -> dict:
        return {
            "capacity": self.capacity,
            "stacks": [[s.item.id, s.count] for s in self.stacks],
            "equipment": {slot: (it.id if it else None)
                          for slot, it in self.equipment.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Inventory":
        inv = cls(data.get("capacity", INVENTORY_SIZE))
        for item_id, count in data.get("stacks", []):
            try:
                inv.add(get_item(item_id), count)
            except KeyError:
                continue
        for slot, item_id in data.get("equipment", {}).items():
            if item_id and slot in inv.equipment:
                try:
                    inv.equipment[slot] = get_item(item_id)
                except KeyError:
                    pass
        return inv