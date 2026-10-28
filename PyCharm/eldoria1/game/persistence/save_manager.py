"""Збереження та завантаження гри: усе, що є в GameState, перетворюється на JSON."""
import json
import os
import time
from dataclasses import asdict

from game.config import SAVE_SLOTS, SAVES_DIR
from game.entities.monster import Monster
from game.entities.npc import NPC
from game.entities.player import Player
from game.items.inventory import Inventory
from game.items.item import get_item
from game.items.loot import LootPile
from game.state import DungeonStatus, GameState, Level
from game.systems.market import Lot, Market
from game.systems.quests import QuestLog
from game.systems.world_events import WorldEvents, event_defs
from game.world import zones
from game.world.tilemap import Building, TileMap

SAVE_VERSION = 1
AUTOSAVE = "auto"
MANUAL_SLOTS = [str(i) for i in range(1, SAVE_SLOTS + 1)]
SLOTS = [AUTOSAVE] + MANUAL_SLOTS
MAX_SAVED_MESSAGES = 60


class SaveError(Exception):
    """Збереження неможливо прочитати (немає файлу, пошкоджене, інша версія)."""


def slot_label(slot: str) -> str:
    return "Автозбереження" if slot == AUTOSAVE else f"Слот {slot}"


def save_path(slot: str):
    name = "autosave.json" if slot == AUTOSAVE else f"slot{slot}.json"
    return SAVES_DIR / name


def _item_exists(item_id: str) -> bool:
    try:
        get_item(item_id)
        return True
    except KeyError:
        return False


# ---------- множини клітинок (туман війни) ----------
def _encode_cells(cells: set, width: int, height: int) -> list[str]:
    """Множина (x, y) -> список рядків з '0' і '1': набагато компактніше за список пар."""
    return ["".join("1" if (x, y) in cells else "0" for x in range(width))
            for y in range(height)]


def _decode_cells(rows: list[str]) -> set:
    return {(x, y) for y, row in enumerate(rows)
            for x, char in enumerate(row) if char == "1"}


# ---------- карта ----------
def _tilemap_to_dict(tm: TileMap) -> dict:
    return {
        "grid": ["".join(row) for row in tm.grid],
        "spawn": list(tm.spawn),
        "name": tm.name,
        "kind": tm.kind,
        "hint": tm.hint,
        "vision": tm.vision,
        "biome_phase": list(tm.biome_phase),
        "portals": [[x, y, did] for (x, y), did in tm.portals.items()],
        "entrances": {did: list(pos) for did, pos in tm.entrances.items()},
        "buildings": [asdict(b) for b in tm.buildings],
        "safe_rects": [list(r) for r in tm.safe_rects],
        "huts": [list(h) for h in tm.huts],
    }


def _tilemap_from_dict(d: dict) -> TileMap:
    tm = TileMap([list(row) for row in d["grid"]], tuple(d["spawn"]),
                 d["name"], d["kind"])
    tm.hint = d.get("hint", "")
    tm.vision = d.get("vision")
    tm.biome_phase = tuple(d.get("biome_phase", (0.0, 0.0)))
    tm.portals = {(x, y): did for x, y, did in d["portals"]}
    tm.entrances = {did: tuple(pos) for did, pos in d["entrances"].items()}
    tm.buildings = [
        Building(kind=b["kind"], name=b["name"], x=b["x"], y=b["y"], w=b["w"], h=b["h"],
                 door=tuple(b["door"]), spot=tuple(b["spot"]),
                 label_pos=tuple(b["label_pos"]))
        for b in d["buildings"]]
    tm.safe_rects = [tuple(r) for r in d["safe_rects"]]
    tm.huts = [tuple(h) for h in d["huts"]]
    return tm


# ---------- сутності ----------
def _entity_to_dict(e) -> dict | None:
    if isinstance(e, NPC):
        return {"t": "npc", "id": e.npc_id, "x": e.x, "y": e.y}
    if isinstance(e, Monster):
        return {"t": "mob", "id": e.monster_id, "x": e.x, "y": e.y,
                "hp": e.hp, "max_hp": e.max_hp, "attack": e.attack,
                "defense": e.defense, "xp": e.xp_reward, "bonus": e.bonus,
                "scaled": e.scaled, "aggro": e.aggro, "home": list(e.home),
                "chasing": e.chasing, "enraged": e.enraged,
                "summoned": e.summoned, "invader": getattr(e, "invader", False)}
    return None


def _entity_from_dict(d: dict):
    try:
        if d["t"] == "npc":
            return NPC(d["id"], d["x"], d["y"])
        m = Monster(d["id"], d["x"], d["y"])
    except KeyError:          # монстра більше немає в monsters.json: пропускаємо
        return None
    m.max_hp, m.hp = d["max_hp"], d["hp"]
    m.attack, m.defense = d["attack"], d["defense"]
    m.xp_reward, m.bonus, m.scaled = d["xp"], d["bonus"], d["scaled"]
    m.aggro, m.home = d["aggro"], tuple(d["home"])
    m.chasing, m.enraged, m.summoned = d["chasing"], d["enraged"], d["summoned"]
    if d.get("invader"):
        m.invader = True
    return m


# ---------- здобич ----------
def _pile_to_dict(pile: LootPile) -> dict:
    return {"x": pile.x, "y": pile.y, "gold": pile.gold, "born": pile.born,
            "items": [[item.id, count] for item, count in pile.items]}


def _pile_from_dict(d: dict) -> LootPile:
    items = [(get_item(i), n) for i, n in d["items"] if _item_exists(i)]
    return LootPile(d["x"], d["y"], gold=d["gold"], items=items, born=d["born"])


# ---------- рівень (карта + сутності + здобич + відкрита територія) ----------
def _level_to_dict(level: Level) -> dict:
    tm = level.tilemap
    return {
        "tilemap": _tilemap_to_dict(tm),
        "entities": [d for d in map(_entity_to_dict, level.entities) if d],
        "piles": [_pile_to_dict(p) for p in level.piles.values()],
        "explored": _encode_cells(level.explored, tm.width, tm.height),
    }


def _level_from_dict(d: dict) -> Level:
    entities = [e for e in map(_entity_from_dict, d["entities"]) if e]
    piles = {}
    for raw in d["piles"]:
        pile = _pile_from_dict(raw)
        piles[(pile.x, pile.y)] = pile
    return Level(_tilemap_from_dict(d["tilemap"]), entities, piles,
                 _decode_cells(d["explored"]))


# ---------- гравець ----------
def _player_to_dict(p: Player) -> dict:
    return {"name": p.name, "class_id": p.class_id, "x": p.x, "y": p.y,
            "hp": p.hp, "mp": p.mp, "max_hp": p.max_hp, "max_mp": p.max_mp,
            "attack": p.attack, "defense": p.defense, "level": p.level,
            "xp": p.xp, "gold": p.gold, "inventory": p.inventory.to_dict()}


def _player_from_dict(d: dict) -> Player:
    p = Player(d["name"], d["class_id"], d["x"], d["y"])
    p.hp, p.mp = d["hp"], d["mp"]
    p.max_hp, p.max_mp = d["max_hp"], d["max_mp"]
    p.attack, p.defense = d["attack"], d["defense"]
    p.level, p.xp, p.gold = d["level"], d["xp"], d["gold"]
    p.inventory = Inventory.from_dict(d["inventory"])
    return p


# ---------- ринок і події ----------
def _market_to_dict(m: Market) -> dict:
    return {"lots": [asdict(lot) for lot in m.lots], "next_id": m.next_id,
            "demand": m.demand, "feed": m.feed, "mail_gold": m.mail_gold,
            "mail_items": [list(x) for x in m.mail_items],
            "last_tick": m.last_tick, "stock": m.stock, "stock_turn": m.stock_turn}


def _market_from_dict(d: dict) -> Market:
    m = Market()                       # значення за замовчуванням з shops.json
    m.lots = [Lot(**raw) for raw in d["lots"] if _item_exists(raw["item_id"])]
    m.next_id = d["next_id"]
    m.demand = {k: float(v) for k, v in d["demand"].items() if _item_exists(k)}
    m.feed = list(d["feed"])
    m.mail_gold = d["mail_gold"]
    m.mail_items = [(i, n) for i, n in d["mail_items"] if _item_exists(i)]
    m.last_tick = d["last_tick"]
    for shop_id, stock in d["stock"].items():
        if shop_id in m.stock:
            m.stock[shop_id] = {i: n for i, n in stock.items() if _item_exists(i)}
    for shop_id, turn in d["stock_turn"].items():
        if shop_id in m.stock_turn:
            m.stock_turn[shop_id] = turn
    return m


def _events_from_dict(d: dict) -> WorldEvents:
    events = WorldEvents()
    active = d.get("active")
    if active and active.get("id") in event_defs():
        events.active = {"id": active["id"], "ends": active["ends"]}
    events.next_turn = d.get("next_turn", events.next_turn)
    events.completed = d.get("completed", 0)
    return events


# ---------- головні функції ----------
def _meta(state: GameState) -> dict:
    """Коротка довідка про збереження: для списку слотів (без розбору всієї гри)."""
    p = state.player
    return {"name": p.name, "class_name": p.class_name, "level": p.level,
            "turn": state.turn, "gold": p.gold, "kills": state.kills,
            "playtime": int(state.playtime),
            "location": zones.zone_info(state.tilemap, p.x, p.y)[0],
            "saved_at": time.strftime("%Y-%m-%d %H:%M")}


def serialize(state: GameState) -> dict:
    # активна карта лежить у state.tilemap, решта в state.levels: збираємо разом
    levels = dict(state.levels)
    levels[state.level_id] = Level(state.tilemap, state.entities,
                                   state.piles, state.explored)
    rng = state.rng.getstate()
    return {
        "version": SAVE_VERSION,
        "meta": _meta(state),
        "player": _player_to_dict(state.player),
        "level_id": state.level_id,
        "levels": {lid: _level_to_dict(lv) for lid, lv in levels.items()},
        "dungeons": {did: [s.cleared, s.cleared_turn, s.visits]
                     for did, s in state.dungeons.items()},
        "quests": state.quest_log.to_dict(),
        "market": _market_to_dict(state.market),
        "events": {"active": state.events.active, "next_turn": state.events.next_turn,
                   "completed": state.events.completed},
        "state": {"turn": state.turn, "kills": state.kills, "deaths": state.deaths,
                  "fog": state.fog_enabled, "victory": state.victory,
                  "playtime": state.playtime, "slot": state.slot,
                  "messages": state.messages[-MAX_SAVED_MESSAGES:]},
        "rng": [rng[0], list(rng[1]), rng[2]],
    }


def deserialize(data: dict) -> GameState:
    if data.get("version") != SAVE_VERSION:
        raise SaveError("Збереження створене іншою версією гри.")

    player = _player_from_dict(data["player"])
    levels = {lid: _level_from_dict(ld) for lid, ld in data["levels"].items()}
    overworld = levels.pop("overworld")

    state = GameState(player, overworld.tilemap)
    state.entities, state.piles = overworld.entities, overworld.piles
    state.explored = overworld.explored
    state.levels = levels                       # усі підземелля - неактивні рівні

    state.dungeons = {did: DungeonStatus(*vals) for did, vals in data["dungeons"].items()}
    state.quest_log = QuestLog.from_dict(data["quests"])
    state.market = _market_from_dict(data["market"])
    state.events = _events_from_dict(data["events"])

    s = data["state"]
    state.turn, state.kills, state.deaths = s["turn"], s["kills"], s["deaths"]
    state.fog_enabled, state.victory = s["fog"], s["victory"]
    state.playtime, state.slot = s["playtime"], s["slot"]
    state.messages = list(s["messages"])

    if data["level_id"] != "overworld":         # гравець зберігся в підземеллі
        state.switch_level(data["level_id"])

    version, internal, gauss = data["rng"]      # відновлюємо генератор випадкових чисел
    state.rng.setstate((version, tuple(internal), gauss))
    return state


def save_game(state: GameState, slot: str) -> None:
    """Зберігає гру. Спершу пишемо в тимчасовий файл, а потім підміняємо оригінал:
    якщо програма впаде посеред запису, старе збереження залишиться цілим."""
    SAVES_DIR.mkdir(parents=True, exist_ok=True)
    data = serialize(state)
    path = save_path(slot)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def load_game(slot: str) -> GameState:
    try:
        with open(save_path(slot), encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SaveError("Збереження не знайдено.")
    except (OSError, json.JSONDecodeError) as error:
        raise SaveError(f"Файл збереження пошкоджено ({error}).")

    try:
        state = deserialize(data)
    except SaveError:
        raise
    except (KeyError, ValueError, TypeError, IndexError, AttributeError) as error:
        raise SaveError(f"Збереження пошкоджене або застаріле ({type(error).__name__}: {error}).")
    if slot != AUTOSAVE:
        state.slot = slot
    return state


def slot_summary(slot: str) -> dict | None:
    """None, якщо слот порожній; {'error': True}, якщо файл зіпсований."""
    path = save_path(slot)
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        info = dict(data["meta"])
        info["ok"] = data.get("version") == SAVE_VERSION
        return info
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return {"error": True}


def delete_save(slot: str) -> None:
    save_path(slot).unlink(missing_ok=True)


def latest_slot() -> str | None:
    """Слот з найсвіжішим файлом (для кнопки «Продовжити»)."""
    existing = [(save_path(s).stat().st_mtime, s) for s in SLOTS if save_path(s).exists()]
    return max(existing)[1] if existing else None