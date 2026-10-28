"""Світові події: ярмарки, дефіцит, кривавий місяць, вторгнення..."""
from functools import lru_cache

from game.config import load_json
from game.entities.monster import Monster

FORBIDDEN_TILES = {"_", "+"}


@lru_cache(maxsize=1)
def _cfg() -> dict:
    return load_json("world_events.json")


def event_defs() -> dict:
    return _cfg()["events"]


class WorldEvents:
    def __init__(self):
        self.active: dict | None = None            # {"id": ..., "ends": хід}
        self.next_turn: int = _cfg().get("first_event_turn", 250)
        self.completed = 0

    @property
    def current(self) -> dict | None:
        return event_defs()[self.active["id"]] if self.active else None

    def effect(self, key: str, default=1.0):
        current = self.current
        return default if current is None else current["effects"].get(key, default)

    def mult(self, key: str) -> float:
        return self.effect(key, 1.0)

    def hud_text(self, state) -> str | None:
        current = self.current
        if current is None:
            return None
        if "invasion" in current["effects"]:
            return f"Вторгнення! ворогів: {self._invaders_left(state)}"
        left = max(0, self.active["ends"] - state.turn)
        return f"{current['name']} ({left})"

    # ---------- цикл ----------
    def tick(self, state) -> None:
        if self.active:
            if state.turn >= self.active["ends"]:
                name = self.current["name"]
                self._finish(state, f"Подія «{name}» завершилась.")
            elif "invasion" in self.current["effects"] and self._invaders_left(state) == 0:
                self._victory(state)
            return
        if state.turn >= self.next_turn and state.level_id == "overworld":
            self._start(state, self._pick(state))

    def _pick(self, state) -> str:
        level = state.player.level
        ids = [i for i, e in event_defs().items() if e.get("min_level", 1) <= level]
        weights = [event_defs()[i].get("weight", 1) for i in ids]
        return state.rng.choices(ids, weights)[0]

    def force_start(self, state, event_id: str) -> bool:
        """Для debug: запускає подію незалежно від таймера."""
        if self.active:
            self._finish(state, "Попередню подію скасовано.")
        return self._start(state, event_id)

    def _start(self, state, event_id: str) -> bool:
        event = event_defs()[event_id]
        self.active = {"id": event_id, "ends": state.turn + event["duration"]}
        state.log(f"*** СВІТОВА ПОДІЯ: {event['name']} ***")
        state.log(event["desc"])

        effects = event["effects"]
        if "invasion" in effects and self._spawn_invaders(state, effects["invasion"]) == 0:
            self.active = None
            self.next_turn = state.turn + 60
            return False
        if effects.get("auction_lots"):
            state.market.add_bot_lots(state, int(effects["auction_lots"]))
        return True

    def _finish(self, state, message: str | None = None) -> None:
        entities = state.overworld_entities
        entities[:] = [e for e in entities if not getattr(e, "invader", False)]
        if message:
            state.log(message)
        self.active = None
        self.completed += 1
        self.next_turn = state.turn + state.rng.randint(*_cfg()["gap_turns"])

    # ---------- вторгнення ----------
    def _invaders_left(self, state) -> int:
        return sum(1 for e in state.overworld_entities
                   if getattr(e, "invader", False) and e.is_alive)

    def _spawn_invaders(self, state, cfg: dict) -> int:
        rng, tm = state.rng, state.tilemap
        cx, cy = tm.spawn
        x0, y0, x1, y1 = tm.safe_rects[0]
        ids = [i for i, _ in cfg["ids"]]
        weights = [w for _, w in cfg["ids"]]

        placed = 0
        for _ in range(cfg["count"] * 40):
            if placed >= cfg["count"]:
                break
            x, y = cx + rng.randint(-46, 46), cy + rng.randint(-24, 24)
            tile = tm.tile_at(x, y)
            if tile is None or not tile.walkable or tile.char in FORBIDDEN_TILES:
                continue
            if tm.is_safe(x, y) or state.entity_at(x, y) is not None:
                continue
            gap = max(x0 - x, x - x1, y0 - y, y - y1)      # відстань до стін міста
            if not 4 <= gap <= 16:
                continue
            monster = Monster(rng.choices(ids, weights)[0], x, y)
            monster.invader = True
            monster.scale_to(state.threat_bonus)
            monster.aggro = max(monster.aggro, 30)          # полюють на гравця здалеку
            monster.chasing = True
            state.entities.append(monster)
            placed += 1
        if placed:
            state.log(f"Загарбники ({placed}) оточують Ельдорію!")
        return placed

    def on_kill(self, state, monster) -> None:
        if not self.active or not getattr(monster, "invader", False):
            return
        cfg = self.effect("invasion", None)
        if not cfg:
            return
        bonus = cfg.get("kill_gold", 0)
        state.player.gold += bonus
        left = self._invaders_left(state)
        if left == 0:
            self._victory(state)
        else:
            state.log(f"Загарбників лишилось: {left} (+{bonus} золота).")

    def _victory(self, state) -> None:
        cfg = self.effect("invasion", {})
        gold, xp = cfg.get("reward_gold", 0), cfg.get("reward_xp", 0)
        state.player.gold += gold
        state.log(f"*** Вторгнення відбито! Нагорода: {gold} золота, {xp} досвіду. ***")
        for message in state.player.gain_xp(xp):
            state.log(message)
        self._finish(state)