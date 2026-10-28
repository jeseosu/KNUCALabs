"""Стан гри: усе, що потім зберігатиметься у файл."""
import random
from dataclasses import dataclass

from game.config import (MAX_LOG_SIZE, TOWN_VISION_BONUS, VISION_RADIUS,
                         VISION_X_STRETCH)
from game.entities.entity import Entity
from game.entities.monster import Monster, level_bonus
from game.entities.npc import NPC
from game.entities.player import Player
from game.items.loot import LootPile
from game.systems.market import Market
from game.systems.quests import QuestLog
from game.systems.world_events import WorldEvents
from game.world import dungeon
from game.world.tilemap import TileMap


@dataclass
class Level:
    """Неактивний рівень (поверхня, поки ми в підземеллі, або підземелля, поки ми нагорі)."""
    tilemap: TileMap
    entities: list
    piles: dict
    explored: set


@dataclass
class DungeonStatus:
    cleared: bool = False
    cleared_turn: int = 0
    visits: int = 0


class GameState:
    def __init__(self, player: Player, tilemap: TileMap, seed: int | None = None):
        self.player = player
        self.tilemap = tilemap                 # поточна карта (поверхня або підземелля)
        self.rng = random.Random(seed)
        self.entities: list[Entity] = []       # монстри, NPC поточної карти
        self.piles: dict[tuple[int, int], LootPile] = {}   # здобич на землі
        self.messages: list[str] = []
        self.turn = 0
        self.kills = 0
        self.deaths = 0
        self.running = True
        self.quest_log = QuestLog()

        # --- економіка та події (етап 6) ---
        self.events = WorldEvents()
        self.market = Market()
        self.pending_menu: tuple[str, str] | None = None   # (тип, id) екрана після діалогу
        self.slot: str | None = None      # слот, у який гравець востаннє зберігався вручну
        self.victory = False              # чи переможено Володаря Безодні
        self.playtime = 0.0               # скільки секунд триває гра
        # --- кілька рівнів ---
        self.level_id = "overworld"
        self.levels: dict[str, Level] = {}             # усі НЕактивні рівні
        self.dungeons: dict[str, DungeonStatus] = {}   # прогрес підземель

        # --- туман війни ---
        self.fog_enabled = True
        self.visible: set[tuple[int, int]] = set()    # що видно прямо зараз
        self.explored: set[tuple[int, int]] = set()   # що вже відкрито (пам'ять)
        self._vision_key: tuple | None = None         # кеш: де були востаннє
        self._reveal_safe_zones()
        self.market.seed(self)

    def _reveal_safe_zones(self) -> None:
        """Рідне місто герой знає зі старту: воно вже на карті."""
        for x0, y0, x1, y1 in self.tilemap.safe_rects:
            self.explored.update((x, y) for y in range(y0, y1 + 1)
                                 for x in range(x0, x1 + 1))

    def log(self, text: str) -> None:
        self.messages.append(text)
        if len(self.messages) > MAX_LOG_SIZE:
            del self.messages[0]

    # ---------- сутності ----------
    @property
    def overworld_entities(self) -> list:
        """Сутності поверхні, навіть якщо гравець зараз у підземеллі."""
        if self.level_id == "overworld":
            return self.entities
        return self.levels["overworld"].entities

    def entity_at(self, x: int, y: int) -> Entity | None:
        for entity in self.entities:
            if entity.x == x and entity.y == y and entity.is_alive:
                return entity
        return None

    def nearest_monster(self, radius: int, visible_only: bool = False) -> Entity | None:
        """Найближчий жива ворожа істота (NPC не рахуються) в межах radius.
        visible_only: ігнорувати тих, кого гравець зараз не бачить."""
        p = self.player
        best, best_dist = None, radius + 1
        for entity in self.entities:
            if not isinstance(entity, Monster) or not entity.is_alive:
                continue
            if visible_only and not self.can_see(entity.x, entity.y):
                continue
            dist = abs(entity.x - p.x) + abs(entity.y - p.y)
            if dist < best_dist:
                best, best_dist = entity, dist
        return best

    # ---------- рівні та підземелля ----------
    def switch_level(self, level_id: str) -> None:
        """Ховає поточну карту в self.levels і робить активною іншу."""
        self.levels[self.level_id] = Level(self.tilemap, self.entities,
                                           self.piles, self.explored)
        new = self.levels.pop(level_id)
        self.tilemap, self.entities = new.tilemap, new.entities
        self.piles, self.explored = new.piles, new.explored
        self.level_id = level_id
        self.visible = set()
        self._vision_key = None

    def enter_dungeon(self, dungeon_id: str) -> None:
        cfg = dungeon.dungeon_defs()[dungeon_id]
        status = self.dungeons.setdefault(dungeon_id, DungeonStatus())

        # зачищене підземелля через час оживає: новий план, нові монстри, новий бос
        reset = status.cleared and self.turn - status.cleared_turn >= cfg["reset_turns"]
        if reset:
            status.cleared = False
            self.levels.pop(dungeon_id, None)

        if dungeon_id not in self.levels:
            tilemap, entities, piles = dungeon.build_level(self, dungeon_id)
            self.levels[dungeon_id] = Level(tilemap, entities, piles, set())
            if reset:
                self.log("Підземелля ожило: у ньому знову оселилися ворог та бос!")

        self.switch_level(dungeon_id)
        self.player.move_to(*self.tilemap.spawn)
        status.visits += 1

    def leave_dungeon(self, to_town: bool = False) -> None:
        if self.level_id == "overworld":
            return
        dungeon_id = self.level_id
        for entity in self.entities:              # бос відновлюється, якщо його кинули
            if getattr(entity, "is_boss", False) and entity.is_alive:
                entity.hp = entity.max_hp
        self.switch_level("overworld")

        if to_town:
            pos = self.tilemap.spawn
        else:
            pos = self.tilemap.entrances.get(dungeon_id, self.tilemap.spawn)
            self.log("Ти виходиш на поверхню.")
        self.player.move_to(*pos)

    def on_boss_killed(self, boss) -> None:
        cfg = dungeon.dungeon_defs().get(self.level_id)
        status = self.dungeons.get(self.level_id)
        if cfg is None or status is None:
            return
        self.quest_log.on_clear(self, self.level_id)     # квест зараховується завжди
        if status.cleared:
            return
        status.cleared = True
        status.cleared_turn = self.turn
        self.player.gold += cfg["clear_gold"]
        self.log(f"*** {cfg['name']} зачищено! Нагорода: {cfg['clear_gold']} золота. ***")
        for message in self.player.gain_xp(cfg["clear_xp"]):
            self.log(message)

    # ---------- зростання монстрів ----------
    @property
    def threat_bonus(self) -> int:
        """Поточний бонус рівнів для монстрів (залежить від кількості ходів)."""
        return level_bonus(self.turn)

    def _scale_new_monsters(self) -> None:
        """Монстр отримує бонус у момент, коли його вперше побачили."""
        bonus = self.threat_bonus
        for entity in self.entities:
            if (isinstance(entity, Monster) and not entity.scaled
                    and (entity.x, entity.y) in self.visible):
                entity.scale_to(bonus)

    # ---------- NPC ----------
    def _refresh_npc_markers(self) -> None:
        """Над квестодавцями світиться ! (новий квест) або ? (можна здати)."""
        for entity in self.entities:
            if isinstance(entity, NPC):
                entity.set_marker(self.quest_log.marker(self, entity.npc_id))

    # ---------- огляд ----------
    @property
    def vision_radius(self) -> int:
        base = self.tilemap.vision or VISION_RADIUS      # у підземеллях свій радіус
        if self.tilemap.is_safe(self.player.x, self.player.y):
            base += TOWN_VISION_BONUS                    # у місті світліше
        return base + int(self.player.inventory.bonus("vision"))

    def can_see(self, x: int, y: int) -> bool:
        """Чи видно клітинку (з вимкненим туманом видно все)."""
        return not self.fog_enabled or (x, y) in self.visible

    def update_vision(self) -> None:
        """Перераховує поле зору, якщо гравець зрушив. Викликається перед малюванням."""
        p = self.player
        key = (p.x, p.y, self.vision_radius)
        if key != self._vision_key:
            self._vision_key = key
            self.visible = self._compute_visible()
            self.explored.update(self.visible)
        self._scale_new_monsters()
        self._refresh_npc_markers()

    def _compute_visible(self) -> set[tuple[int, int]]:
        p, tilemap = self.player, self.tilemap
        r, stretch = self.vision_radius, VISION_X_STRETCH
        visible = {(p.x, p.y)}
        for dy in range(-r, r + 1):
            for dx in range(-r * stretch, r * stretch + 1):
                # еліпс: по горизонталі в stretch разів ширше
                if (dx / stretch) ** 2 + dy ** 2 > r * r + 0.5:
                    continue
                x, y = p.x + dx, p.y + dy
                if not tilemap.in_bounds(x, y):
                    continue
                if tilemap.line_clear(p.x, p.y, x, y):   # стіни й дерева закривають огляд
                    visible.add((x, y))
        return visible