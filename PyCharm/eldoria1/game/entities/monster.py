"""Монстри: дані, ШІ, фази босів, зростання з часом та спавн."""
import math
from functools import lru_cache

from game.config import (MONSTER_LEASH, SAFE_RADIUS, SCALING_ATTACK,
                         SCALING_DEFENSE, SCALING_HP, SCALING_MAX_BONUS,
                         SCALING_TURNS, SCALING_XP, SPAWN_MIN_PLAYER_DIST,
                         load_json)
from game.entities.entity import Entity
from game.world.zones import danger_distance

FORBIDDEN_TILES = {"_", "+"}   # монстри не заходять у будівлі
DIRECTIONS = [(0, -1), (0, 1), (-1, 0), (1, 0)]
AROUND = [(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3) if (dx, dy) != (0, 0)]


@lru_cache(maxsize=1)
def monster_defs() -> dict:
    """JSON читається один раз і кешується."""
    return load_json("monsters.json")


def level_bonus(turn: int) -> int:
    """Скільки бонусних рівнів мають монстри на цьому ході.

    Корінь: на початку бонус росте помітно, далі дедалі повільніше.
    Хід 150 -> +1, 600 -> +2, 1350 -> +3, 2400 -> +4 ... стеля SCALING_MAX_BONUS.
    """
    return min(SCALING_MAX_BONUS, int(math.sqrt(max(0, turn) / SCALING_TURNS)))


class Monster(Entity):
    def __init__(self, monster_id: str, x: int, y: int):
        data = monster_defs()[monster_id]
        super().__init__(data["name"], x, y, data["glyph"], data["color"],
                         data["max_hp"], data["attack"], data["defense"])
        self.monster_id = monster_id
        self.level = data["level"]          # базовий рівень (від нього залежить здобич)
        self.bonus = 0                      # бонусні рівні за час гри
        self.scaled = False                 # чи вже підсилений
        self.xp_reward = data["xp"]
        self.aggro = data["aggro"]
        self.move_every = data.get("move_every", 1)
        self.verb = data.get("verb", "б'є")
        self.home = (x, y)
        self.chasing = False

        # --- бос ---
        self.is_boss = data.get("boss", False)
        self.enrage_at = data.get("enrage_at", 0)    # частка HP, при якій бос шаленіє
        self.summon = data.get("summon")             # {"id", "count", "at"}
        self.enraged = False
        self.summoned = False

    @property
    def display_level(self) -> int:
        """Рівень, який бачить гравець: базовий + бонус за час."""
        return self.level + self.bonus

    def scale_to(self, bonus: int) -> None:
        """Підсилює монстра на bonus рівнів. Викликається один раз,
        коли гравець уперше бачить цього монстра."""
        self.scaled = True
        self.bonus = bonus
        if bonus <= 0:
            return
        self.max_hp = round(self.max_hp * (1 + SCALING_HP * bonus))
        self.hp = self.max_hp
        self.attack = round(self.attack * (1 + SCALING_ATTACK * bonus))
        self.defense = round(self.defense * (1 + SCALING_DEFENSE * bonus))
        self.xp_reward = round(self.xp_reward * (1 + SCALING_XP * bonus))

    # ---------- фази боса ----------
    def _phases(self, state) -> None:
        if self.enrage_at and not self.enraged and self.hp <= self.max_hp * self.enrage_at:
            self.enraged = True
            self.attack = round(self.attack * 1.4)
            state.log(f"{self.name} впадає в сказ!")

        if self.summon and not self.summoned and self.hp <= self.max_hp * self.summon["at"]:
            self.summoned = True
            state.log(f"{self.name} кличе підмогу!")
            self._summon_adds(state)

    def _summon_adds(self, state) -> None:
        placed = 0
        for ox, oy in state.rng.sample(AROUND, len(AROUND)):
            if placed >= self.summon.get("count", 2):
                break
            nx, ny = self.x + ox, self.y + oy
            if self._can_enter(state, nx, ny):
                add = Monster(self.summon["id"], nx, ny)
                add.scale_to(state.threat_bonus)
                add.chasing = True
                state.entities.append(add)
                placed += 1

    # ---------- ШІ ----------
    def act(self, state) -> bool:
        """Хід монстра. Повертає True, якщо він хоче атакувати гравця."""
        if self.is_boss:
            self._phases(state)

        p = state.player
        dx, dy = p.x - self.x, p.y - self.y
        dist = abs(dx) + abs(dy)
        player_safe = state.tilemap.is_safe(p.x, p.y)

        if dist == 1 and not player_safe:   # поруч - б'ємо (у місті не нападаємо)
            self.chasing = True
            return True

        can_move = state.turn % self.move_every == 0
        if dist <= self.aggro:              # відчуває гравця - переслідуємо
            if not self.chasing:
                self.chasing = True
                if state.can_see(self.x, self.y):
                    state.log(f"{self.name} помічає тебе!")
                else:
                    state.log("Щось у темряві помічає тебе...")
            if can_move:
                self._step_towards(state, dx, dy)
        else:                               # інакше блукаємо біля дому
            self.chasing = False
            if can_move and state.rng.random() < 0.25:
                self._wander(state)
        return False

    def _can_enter(self, state, x: int, y: int) -> bool:
        tile = state.tilemap.tile_at(x, y)
        if tile is None or not tile.walkable or tile.char in FORBIDDEN_TILES:
            return False
        if state.tilemap.is_safe(x, y):     # у місто монстрам заборонено
            return False
        if (x, y) == (state.player.x, state.player.y):
            return False
        return state.entity_at(x, y) is None

    def _try_move(self, state, ox: int, oy: int) -> bool:
        nx, ny = self.x + ox, self.y + oy
        if self._can_enter(state, nx, ny):
            self.move_to(nx, ny)
            return True
        return False

    def _step_towards(self, state, dx: int, dy: int) -> None:
        sx = (dx > 0) - (dx < 0)
        sy = (dy > 0) - (dy < 0)
        if abs(dx) >= abs(dy):
            options = [(sx, 0), (0, sy)]
        else:
            options = [(0, sy), (sx, 0)]
        for ox, oy in options:
            if (ox, oy) != (0, 0) and self._try_move(state, ox, oy):
                return
        if state.rng.random() < 0.5:        # перешкода - пробуємо обійти
            self._wander(state)

    def _wander(self, state) -> None:
        hx, hy = self.home
        for ox, oy in state.rng.sample(DIRECTIONS, 4):
            nx, ny = self.x + ox, self.y + oy
            if abs(nx - hx) + abs(ny - hy) > MONSTER_LEASH:
                continue
            if self._try_move(state, ox, oy):
                return


# ---------- спавн (лише на поверхні) ----------
def spawn_monster(state, min_player_dist: int = SPAWN_MIN_PLAYER_DIST) -> Monster | None:
    """Пробує створити одного монстра у випадковому місці. Повертає його або None."""
    tilemap, rng, player = state.tilemap, state.rng, state.player
    defs = monster_defs()

    for _ in range(60):
        x = rng.randrange(1, tilemap.width - 1)
        y = rng.randrange(1, tilemap.height - 1)
        tile = tilemap.tile_at(x, y)
        if tile is None or not tile.walkable or tilemap.is_safe(x, y):
            continue
        dist = danger_distance(tilemap, x, y)
        if dist < SAFE_RADIUS:
            continue
        if abs(x - player.x) + abs(y - player.y) < min_player_dist:
            continue
        if state.entity_at(x, y) is not None:
            continue

        candidates = [(mid, d) for mid, d in defs.items()
                      if tile.char in d["spawn_on"]
                      and d["min_dist"] <= dist <= d["max_dist"]]
        if not candidates:
            continue

        ids = [mid for mid, _ in candidates]
        weights = [d["weight"] for _, d in candidates]
        monster = Monster(rng.choices(ids, weights=weights)[0], x, y)
        state.entities.append(monster)
        return monster
    return None


def populate_world(state, count: int) -> None:
    for _ in range(count):
        spawn_monster(state)