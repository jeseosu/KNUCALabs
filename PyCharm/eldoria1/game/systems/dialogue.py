"""Діалоги з NPC: сторінки, варіанти відповіді, послуги, вхід у торгівлю."""
import math
from dataclasses import dataclass

from game.systems import crafting
from game.systems.market import shop_defs
from game.systems.quests import STATUS_ORDER, giver_name, quest_defs, quests_of, reward_text
from game.world.dungeon import dungeon_defs

COMPASS = {"схід": "на сході", "захід": "на заході",
           "північ": "на півночі", "південь": "на півдні"}


@dataclass
class Option:
    label: str
    action: str
    arg: str = ""
    color: str = "default"


@dataclass
class Page:
    speaker: str
    text: str
    options: list[Option]


def _speaker(npc) -> str:
    return f"{npc.name}, {npc.title}" if npc.title else npc.name


def service_cost(state, cfg: dict) -> int:
    return cfg.get("cost", 0) + cfg.get("per_level", 0) * state.player.level


# ---------- сторінки ----------
def main_page(state, npc, text: str | None = None) -> Page:
    data = npc.data
    log = state.quest_log
    options: list[Option] = []

    quest_rows = []
    for qid in quests_of(npc.npc_id):
        status = log.status(state, qid)
        if status in STATUS_ORDER:
            quest_rows.append((STATUS_ORDER[status], qid, status))
    for _, qid, status in sorted(quest_rows):
        q = quest_defs()[qid]
        if status == "ready":
            options.append(Option(f"[?] Здати: {q['name']}", "turnin", qid, "hp_good"))
        elif status == "available":
            options.append(Option(f"[!] {q['name']}", "offer", qid, "title"))
        elif status == "active":
            options.append(Option(f"[...] {q['name']}", "progress", qid))
        else:
            options.append(Option(f"[ ] {q['name']} (з {q.get('level_req', 1)} рівня)",
                                  "locked", qid, "log_old"))

    for service in data.get("services", []):
        label = service["label"].format(cost=service_cost(state, service))
        options.append(Option(label, "service", service["id"], "ui"))

    # --- економіка (етап 6) ---
    if npc.npc_id in shop_defs():
        options.append(Option("Торгувати: купити / продати", "trade", npc.npc_id, "ui"))
    if npc.npc_id in crafting.stations():
        options.append(Option(f"Крафт: {crafting.station_title(npc.npc_id)}",
                              "craft", npc.npc_id, "ui"))
    if npc.npc_id == "auction":
        mail = state.market.mail_gold or state.market.mail_items
        options.append(Option("Аукціон: лоти, пошта" + (" [є пошта!]" if mail else ""),
                              "auction", npc.npc_id, "hp_good" if mail else "ui"))

    for i, topic in enumerate(data.get("topics", [])):
        options.append(Option(topic["label"], "topic", str(i)))
    options.append(Option("До побачення", "bye"))
    return Page(_speaker(npc), text or data["greeting"], options)


def _back(npc, text: str) -> Page:
    return Page(_speaker(npc), text, [Option("Назад", "back")])


def handle(state, npc, option: Option) -> Page | None:
    """Обробляє вибір гравця. Повертає наступну сторінку або None (кінець розмови)."""
    action, arg = option.action, option.arg
    log = state.quest_log

    if action == "bye":
        return None
    if action in ("trade", "craft", "auction"):
        state.pending_menu = (action, arg)      # рушій відкриє екран і поверне в діалог
        return None
    if action == "back":
        return main_page(state, npc)
    if action == "topic":
        return _back(npc, npc.data["topics"][int(arg)]["text"])
    if action == "locked":
        return _back(npc, "Ти ще не готовий до цього завдання. Повертайся, коли станеш сильнішим.")
    if action == "service":
        return run_service(state, npc, arg)

    q = quest_defs().get(arg)
    if action == "offer":
        text = (f"{q['offer']}\n\nЗавдання: {log.objective(state, arg)}"
                f"\nНагорода: {reward_text(arg)}")
        return Page(_speaker(npc), text, [
            Option("Прийняти завдання", "accept", arg, "hp_good"),
            Option("Подумаю пізніше", "back"),
        ])
    if action == "accept":
        log.accept(state, arg)
        state.log(f"Нове завдання: «{q['name']}».")
        return main_page(state, npc, "Чудово! Не підведи мене.")
    if action == "progress":
        return _back(npc, f"{q['progress']}\n\n{log.objective(state, arg)}")
    if action == "turnin":
        lines = log.turn_in(state, arg)
        return main_page(state, npc, f"{q['complete']}\n\nОтримано: {', '.join(lines)}.")
    return main_page(state, npc)


# ---------- послуги ----------
def run_service(state, npc, service_id: str) -> Page:
    cfg = next(s for s in npc.data["services"] if s["id"] == service_id)
    p = state.player

    if service_id == "dungeons":
        return _back(npc, _dungeon_report(state))

    cost = service_cost(state, cfg)
    if p.gold < cost:
        return main_page(state, npc, f"Бракує золота. Потрібно: {cost}.")

    if service_id in ("heal", "meal"):
        if p.hp >= p.max_hp and p.mp >= p.max_mp:
            return main_page(state, npc, "Ти і так сповнений сил. Золото не потрібне.")
        p.gold -= cost
        frac = cfg.get("fraction", 1.0)
        healed = p.heal(int(p.max_hp * frac))
        restored = p.restore_mp(int(p.max_mp * frac))
        state.log(f"Відновлено: +{healed} HP, +{restored} мани (-{cost} золота).")
        return main_page(state, npc, cfg.get("done", "Готово."))

    if service_id == "rumor":
        found = _reveal_dungeon(state)
        if found is None:
            return main_page(state, npc, "Усе, що я знаю про підземелля, ти вже знаєш. Нових чуток немає.")
        p.gold -= cost
        name, direction, level = found
        state.log(f"На карті з'явилось нове місце: {name}.")
        return main_page(state, npc,
                         f"Кажуть, {COMPASS[direction]} є місце під назвою «{name}». "
                         f"Рекомендований рівень: {level}. Я позначила його на твоїй карті (клавіша M).")

    return main_page(state, npc)


def _reveal_dungeon(state):
    """Відкриває на карті найближче з невідомих підземель разом зі стежкою до нього."""
    tm = state.tilemap
    if state.level_id != "overworld":
        return None
    hidden = [(pos, did) for pos, did in tm.portals.items()
              if did != "exit" and pos not in state.explored]
    if not hidden:
        return None

    sx, sy = tm.spawn
    (px, py), did = min(hidden, key=lambda it: math.hypot(it[0][0] - sx, (it[0][1] - sy) * 2))
    for dy in range(-3, 4):
        for dx in range(-6, 7):
            if tm.in_bounds(px + dx, py + dy):
                state.explored.add((px + dx, py + dy))
    for yy in range(min(py, sy), max(py, sy) + 1):       # стежка до головної дороги
        state.explored.add((px, yy))

    dx, dy = px - sx, (py - sy) * 2
    if abs(dx) >= abs(dy):
        direction = "схід" if dx > 0 else "захід"
    else:
        direction = "південь" if dy > 0 else "північ"
    cfg = dungeon_defs()[did]
    return cfg["name"], direction, cfg["level_hint"]


def _dungeon_report(state) -> str:
    known = {did: pos for pos, did in state.tilemap.portals.items()}
    lines = ["Ось що гільдії відомо про підземелля:", ""]
    for did, cfg in dungeon_defs().items():
        pos = known.get(did)
        status = state.dungeons.get(did)
        if pos is None or pos not in state.explored:
            lines.append("??? (не розвідано; дізнайся чутки в таверні)")
        else:
            mark = "зачищено" if status and status.cleared else "активне"
            lines.append(f"{cfg['name']} (рівень {cfg['level_hint']}, {mark})")
    return "\n".join(lines)