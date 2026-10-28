"""Квести: журнал завдань, прогрес і нагороди."""
from functools import lru_cache

from game.config import load_json
from game.entities.monster import monster_defs
from game.entities.npc import npc_defs
from game.items import loot
from game.items.item import get_item, rarity_defs
from game.world.dungeon import dungeon_defs

STATUS_ORDER = {"ready": 0, "available": 1, "active": 2, "low_level": 3}


@lru_cache(maxsize=1)
def quest_defs() -> dict:
    return load_json("quests.json")


def quests_of(npc_id: str) -> list[str]:
    """Усі квести, які видає цей NPC."""
    return [qid for qid, q in quest_defs().items() if q["giver"] == npc_id]


def giver_name(qid: str) -> str:
    return npc_defs()[quest_defs()[qid]["giver"]]["name"]


def goal_of(qid: str) -> int:
    return quest_defs()[qid].get("count", 1)


def reward_text(qid: str) -> str:
    r = quest_defs()[qid].get("reward", {})
    parts = []
    if r.get("gold"):
        parts.append(f"{r['gold']} золота")
    if r.get("xp"):
        parts.append(f"{r['xp']} досвіду")
    for item_id, count in r.get("items", []):
        item = get_item(item_id)
        parts.append(item.name + (f" x{count}" if count > 1 else ""))
    if r.get("gear"):
        names = [v["name"] for v in rarity_defs().values()]
        parts.append(f"екіпіровка ({names[r['gear'][1]].lower()} або краща)")
    return ", ".join(parts) or "подяка"


class QuestLog:
    def __init__(self):
        self.active: dict[str, int] = {}     # id квеста -> прогрес (для kill / clear)
        self.done: set[str] = set()

    # ---------- статус ----------
    def status(self, state, qid: str) -> str:
        """locked / low_level / available / active / ready / done"""
        q = quest_defs()[qid]
        if qid in self.active:
            return "ready" if self.is_ready(state, qid) else "active"
        if qid in self.done and not q.get("repeatable"):
            return "done"
        required = q.get("requires")
        if required and required not in self.done:
            return "locked"
        if state.player.level < q.get("level_req", 1):
            return "low_level"
        return "available"

    def progress(self, state, qid: str) -> int:
        q = quest_defs()[qid]
        goal = goal_of(qid)
        if q["type"] == "collect":                 # рахуємо те, що лежить у рюкзаку
            return min(goal, state.player.inventory.count(q["target"]))
        return min(goal, self.active.get(qid, 0))

    def is_ready(self, state, qid: str) -> bool:
        return self.progress(state, qid) >= goal_of(qid)

    def objective(self, state, qid: str) -> str:
        q = quest_defs()[qid]
        goal, done = goal_of(qid), self.progress(state, qid)
        if q["type"] == "kill":
            target = q["target"]
            name = "будь-яких ворогів" if target == "*" else monster_defs()[target]["name"]
            return f"Вбити: {name} ({done}/{goal})"
        if q["type"] == "collect":
            return f"Принести: {get_item(q['target']).name} ({done}/{goal})"
        name = dungeon_defs()[q["target"]]["name"]
        return f"Зачистити: {name}" + (" (виконано)" if done >= goal else "")

    def short(self, state, qid: str) -> str:
        return f"{quest_defs()[qid]['name']} {self.progress(state, qid)}/{goal_of(qid)}"

    def marker(self, state, npc_id: str) -> str | None:
        """Що показати над NPC: 'ready' (?), 'new' (!) або нічого."""
        result = None
        for qid in quests_of(npc_id):
            status = self.status(state, qid)
            if status == "ready":
                return "ready"
            if status == "available":
                result = "new"
        return result

    # ---------- дії ----------
    def accept(self, state, qid: str) -> None:
        q = quest_defs()[qid]
        self.active[qid] = 0
        if q["type"] == "clear":                   # підземелля вже зачищене - зараховуємо одразу
            status = state.dungeons.get(q["target"])
            if status and status.cleared:
                self.active[qid] = 1

    def on_kill(self, state, monster) -> None:
        for qid in list(self.active):
            q = quest_defs()[qid]
            if q["type"] != "kill":
                continue
            if q["target"] not in ("*", monster.monster_id):
                continue
            if self.active[qid] >= goal_of(qid):
                continue
            self.active[qid] += 1
            self._announce(state, qid)

    def on_clear(self, state, dungeon_id: str) -> None:
        for qid in list(self.active):
            q = quest_defs()[qid]
            if q["type"] == "clear" and q["target"] == dungeon_id and self.active[qid] < 1:
                self.active[qid] = 1
                self._announce(state, qid)

    def _announce(self, state, qid: str) -> None:
        name, goal = quest_defs()[qid]["name"], goal_of(qid)
        done = self.active[qid]
        if done >= goal:
            state.log(f"Завдання «{name}» виконано! Поверніться до: {giver_name(qid)}.")
        else:
            state.log(f"Завдання «{name}»: {done}/{goal}.")

    def turn_in(self, state, qid: str) -> list[str]:
        """Здає квест, видає нагороду. Повертає список рядків про отримане."""
        q = quest_defs()[qid]
        p = state.player
        if q["type"] == "collect":
            p.inventory.remove_by_id(q["target"], goal_of(qid))
        del self.active[qid]
        if not q.get("repeatable"):
            self.done.add(qid)

        reward, lines = q.get("reward", {}), []
        if reward.get("gold"):
            p.gold += reward["gold"]
            lines.append(f"{reward['gold']} золота")
        if reward.get("xp"):
            for message in p.gain_xp(reward["xp"]):
                state.log(message)
            lines.append(f"{reward['xp']} досвіду")
        for item_id, count in reward.get("items", []):
            item = get_item(item_id)
            self._give(state, item, count)
            lines.append(item.name + (f" x{count}" if count > 1 else ""))
        if reward.get("gear"):
            level, min_rank = reward["gear"]
            gear = loot.roll_gear(level, p.class_id, state.rng, min_rank)
            if gear:
                self._give(state, gear, 1)
                lines.append(gear.name)

        state.log(f"Завдання «{q['name']}» завершено!")
        return lines

    @staticmethod
    def _give(state, item, count: int) -> None:
        """Кладе предмет у рюкзак; те, що не влізло, лишається купкою під ногами."""
        p = state.player
        added = p.inventory.add(item, count)
        if added < count:
            pile = state.piles.get((p.x, p.y))
            if pile is None:
                pile = loot.LootPile(p.x, p.y, born=state.turn)
                state.piles[(p.x, p.y)] = pile
            pile.add_item(item, count - added)
            state.log("Рюкзак повний! Частину нагороди залишено на землі.")

    # ---------- збереження (знадобиться на етапі 7) ----------
    def to_dict(self) -> dict:
        return {"active": dict(self.active), "done": sorted(self.done)}

    @classmethod
    def from_dict(cls, data: dict) -> "QuestLog":
        log = cls()
        defs = quest_defs()
        log.active = {q: n for q, n in data.get("active", {}).items() if q in defs}
        log.done = {q for q in data.get("done", []) if q in defs}
        return log