"""Головний цикл гри та обробка вводу."""
import curses
import textwrap
import time

from game.config import (ACTIVE_RADIUS, AUTOSAVE_EVERY, DEATH_GOLD_LOSS,
                         DEATH_XP_LOSS, DEBUG, DEBUG_FOG_KEYS, DEBUG_LOOT_KEY,
                         DEBUG_QUEST_KEY, DEBUG_TIME_KEY, DEBUG_TP_KEY,
                         DEBUG_XP_KEY, HELP_KEYS, INVENTORY_KEYS, MAP_KEYS,
                         MAX_MONSTERS, MOVE_KEYS, PICKUP_KEYS, QUEST_KEYS,
                         QUICK_HEAL_KEYS, QUICK_MANA_KEYS, QUIT_KEYS,
                         REGEN_EVERY, REST_HEAL_PCT, REST_KEYS, RESPAWN_EVERY,
                         SAVE_KEYS, SKILL_KEYS, THREAT_RADIUS, TOWN_REGEN_HP,
                         TOWN_REGEN_MP)
from game.entities.monster import Monster, spawn_monster
from game.entities.npc import NPC
from game.items import loot
from game.items.item import get_item
from game.persistence import save_manager
from game.state import GameState
from game.systems import combat, quests
from game.systems.world_events import event_defs
from game.ui.menus import InventoryMenu
from game.ui.renderer import Renderer
from game.ui.screens import DialogueMenu, QuestLogMenu, WorldMap
from game.ui.title_screens import (DeathScreen, HelpScreen, PauseMenu,
                                   SlotMenu, VictoryScreen)
from game.ui.trade_screens import AuctionMenu, CraftMenu, ShopMenu
from game.world import zones
from game.world.dungeon import dungeon_defs

ENTER_KEYS = {"\n", "\r", curses.KEY_ENTER}
DEBUG_EVENT_KEY = "E"       # debug: запустити наступну світову подію
DEBUG_GOLD_KEY = "$"        # debug: +500 золота


class Engine:
    def __init__(self, stdscr, state: GameState):
        self.scr = stdscr
        self.state = state
        self.renderer = Renderer(stdscr)
        self.portal_pending: str | None = None   # id підземелля або "exit"
        self.dead = False
        self.zone: str | None = None             # остання зона (для повідомлень)
        self.result: tuple = ("quit", None)      # що робити після виходу з циклу
        self._clock = time.monotonic()
        self._tp_index = 0
        self._event_index = -1

    # ---------- головний цикл ----------
    def run(self) -> tuple:
        """Повертає ('menu', None), ('quit', None) або ('load', слот)."""
        state = self.state
        p = state.player
        if state.messages:                       # завантажена гра
            state.log(f"З поверненням, {p.name}!")
        else:
            state.log(f"Ласкаво просимо до Ельдорії, {p.name}!")
            state.log("Поговори з жителями (&): над квестодавцями світиться ! або ?.")
            state.log("Іди на монстра - атака. F вміння, I рюкзак, J журнал, M карта, H довідка.")
        self.zone = zones.zone_info(state.tilemap, p.x, p.y)[0]

        while state.running:
            self._tick_clock()
            state.update_vision()          # поле зору + підсилення нових монстрів
            self.renderer.draw(state, self._popup())
            self._handle_key(self._read_key())
            if state.running and self.dead:
                self._show_death()
            if state.running:
                self._check_victory()
        return self.result

    def _tick_clock(self) -> None:
        """Рахує час гри. Паузи довші за 30 с не враховуються."""
        now = time.monotonic()
        self.state.playtime += min(now - self._clock, 30.0)
        self._clock = now

    def _popup(self) -> list[str] | None:
        return self._portal_popup() if self.portal_pending else None

    def _portal_popup(self) -> list[str]:
        s = self.state
        if self.portal_pending == "exit":
            return ["Піднятися нагору?", "", "Enter - так, інша клавіша - ні"]

        cfg = dungeon_defs()[self.portal_pending]
        lines = [cfg["name"].upper(), ""]
        lines += textwrap.wrap(cfg["desc"], 42)
        lines += ["", f"Рекомендований рівень: {cfg['level_hint']}",
                  f"Радіус огляду всередині: {cfg.get('vision', 6)}"]
        status = s.dungeons.get(self.portal_pending)
        if status and status.cleared:
            left = max(0, cfg["reset_turns"] - (s.turn - status.cleared_turn))
            lines.append(f"Зачищено. Оживе через {left} ходів.")
        lines += ["", "Enter - увійти, інша клавіша - ні"]
        return lines

    def _read_key(self):
        try:
            return self.scr.get_wch()   # get_wch вміє читати кирилицю
        except curses.error:
            return None

    # ---------- ввід ----------
    def _handle_key(self, key) -> None:
        if key is None:
            return
        if key == curses.KEY_RESIZE:
            self.scr.clear()
            return
        if self.dead:
            return

        if self.portal_pending:
            target, self.portal_pending = self.portal_pending, None
            if key in ENTER_KEYS:
                self._use_portal(target)
            return

        if key in QUIT_KEYS:
            self._pause()
        elif key in MOVE_KEYS:
            self._move_player(*MOVE_KEYS[key])
        elif key in SKILL_KEYS:
            self._use_skill()
        elif key in REST_KEYS:
            self._rest()
        elif key in INVENTORY_KEYS:
            self._open_inventory()
        elif key in QUEST_KEYS:
            QuestLogMenu(self.scr, self.state).run()
            curses.flushinp()
        elif key in MAP_KEYS:
            WorldMap(self.scr, self.state).run()
            curses.flushinp()
        elif key in PICKUP_KEYS:
            self._pickup_here()
        elif key in QUICK_HEAL_KEYS:
            self._quick_use("heal")
        elif key in QUICK_MANA_KEYS:
            self._quick_use("mana")
        elif key in SAVE_KEYS:
            self._quick_save()
        elif key in HELP_KEYS:
            HelpScreen(self.scr).run()
            curses.flushinp()
        elif DEBUG and key == DEBUG_XP_KEY:
            for msg in self.state.player.gain_xp(50):
                self.state.log(msg)
        elif DEBUG and key == DEBUG_LOOT_KEY:
            self._debug_loot()
        elif DEBUG and key in DEBUG_FOG_KEYS:
            self._debug_fog()
        elif DEBUG and key == DEBUG_TIME_KEY:
            self._debug_time()
        elif DEBUG and key == DEBUG_TP_KEY:
            self._debug_teleport()
        elif DEBUG and key == DEBUG_QUEST_KEY:
            self._debug_quests()
        elif DEBUG and key == DEBUG_EVENT_KEY:
            self._debug_event()
        elif DEBUG and key == DEBUG_GOLD_KEY:
            self.state.player.gold += 500
            self.state.log("[debug] +500 золота.")

    # ---------- пауза та збереження ----------
    def _pause(self) -> None:
        while True:
            action = PauseMenu(self.scr, self.state).run()
            curses.flushinp()
            if action == "resume":
                return
            if action == "save":
                self._save_dialog()
            elif action == "help":
                HelpScreen(self.scr).run()
            elif action == "menu":
                self.result = ("menu", None)
                self.state.running = False
                return
            elif action == "quit":
                self.result = ("quit", None)
                self.state.running = False
                return

    def _save_dialog(self) -> None:
        slot = SlotMenu(self.scr, "save", self.state.slot).run()
        curses.flushinp()
        if slot:
            self._save(slot)

    def _quick_save(self) -> None:
        if self.state.slot:
            self._save(self.state.slot)
        else:
            self._save_dialog()

    def _save(self, slot: str, quiet: bool = False) -> bool:
        state = self.state
        previous = state.slot
        if slot != save_manager.AUTOSAVE:
            state.slot = slot                      # запам'ятовуємо для швидкого збереження
        try:
            save_manager.save_game(state, slot)
        except OSError as error:
            state.slot = previous
            state.log(f"Не вдалося зберегти гру: {error}")
            return False
        if quiet:
            state.log("Автозбереження виконано.")
        else:
            state.log(f"Гру збережено: {save_manager.slot_label(slot)}.")
        return True

    # ---------- перемога ----------
    def _check_victory(self) -> None:
        s = self.state
        if s.victory:
            return
        status = s.dungeons.get("abyss")
        if status is None or not status.cleared:
            return
        s.victory = True
        s.log("*** Володар Безодні повалений! Ельдорія вільна! ***")
        self._save(save_manager.AUTOSAVE, quiet=True)
        choice = VictoryScreen(self.scr, s).run()
        curses.flushinp()
        if choice == "menu":
            self.result = ("menu", None)
            s.running = False

    # ---------- дії гравця ----------
    def _move_player(self, dx: int, dy: int) -> None:
        state = self.state
        player = state.player
        nx, ny = player.x + dx, player.y + dy

        occupant = state.entity_at(nx, ny)
        if isinstance(occupant, NPC):           # йдемо на NPC = розмова (хід не витрачається)
            self._talk(occupant)
            return
        if isinstance(occupant, Monster):       # йдемо на монстра = б'ємо його
            combat.player_attack(state, occupant)
            self._end_turn()
            return

        portal = state.tilemap.portals.get((nx, ny))
        if portal:                              # вхід/вихід: спершу питаємо
            self.portal_pending = portal
            return

        target = state.tilemap.tile_at(nx, ny)
        if target is None:
            return
        if not target.walkable:
            state.log(target.blocked_msg or "Тут не пройти.")
            return

        current = state.tilemap.tile_at(player.x, player.y)
        player.move_to(nx, ny)
        if target.enter_msg and (current is None or current.char != target.char):
            state.log(target.enter_msg)
        if (nx, ny) in state.piles:             # автопідбір здобичі
            loot.pick_up(state, nx, ny)
        self._end_turn()

    def _talk(self, npc: NPC) -> None:
        """Розмова. Якщо вибрано торгівлю/крафт/аукціон, відкриваємо екран і повертаємось."""
        state = self.state
        while True:
            DialogueMenu(self.scr, state, npc).run()
            pending, state.pending_menu = state.pending_menu, None
            if pending is None:
                break
            kind, arg = pending
            if kind == "trade":
                ShopMenu(self.scr, state, arg).run()
            elif kind == "craft":
                CraftMenu(self.scr, state, arg).run()
            elif kind == "auction":
                AuctionMenu(self.scr, state).run()
        curses.flushinp()

    def _use_portal(self, target: str) -> None:
        state = self.state
        if target == "exit":
            state.leave_dungeon()
        else:
            state.enter_dungeon(target)
        state.update_vision()
        self.zone = None                        # щоб повідомлення про зону з'явилось
        self._check_zone()

    def _check_zone(self) -> None:
        """Повідомляє, коли гравець перейшов в іншу зону."""
        state, p = self.state, self.state.player
        name, hint = zones.zone_info(state.tilemap, p.x, p.y)
        if name != self.zone:
            self.zone = name
            suffix = f" ({hint})" if hint else ""
            state.log(f"Ти входиш: {name}{suffix}.")

    def _use_skill(self) -> None:
        state = self.state
        p = state.player
        skill = p.skill

        if p.mp < skill["cost"]:
            state.log(f"Не вистачає мани для «{skill['name']}» (потрібно {skill['cost']}).")
            return
        target = combat.find_target(state, skill["range"])
        if target is None:
            state.log("Немає цілі в межах досяжності.")
            return

        p.mp -= skill["cost"]
        if skill["range"] > 1:
            self._animate_projectile(target, skill)
        combat.player_attack(state, target, skill["multiplier"], skill["name"])
        self._end_turn()

    def _rest(self) -> None:
        state = self.state
        p = state.player
        if self._enemy_near(4):
            state.log("Ворог поруч - не час відпочивати!")
            return
        if p.hp == p.max_hp and p.mp == p.max_mp:
            state.log("Ти і так сповнений сил.")
            return
        hp = p.heal(max(1, int(p.max_hp * REST_HEAL_PCT)))
        mp = p.restore_mp(max(1, int(p.max_mp * REST_HEAL_PCT)))
        state.log(f"Ти відпочиваєш: +{hp} HP, +{mp} мани.")
        self._end_turn()

    def _enemy_near(self, radius: int) -> bool:
        return self.state.nearest_monster(radius) is not None

    def _open_inventory(self) -> None:
        turns = InventoryMenu(self.scr, self.state).run()
        curses.flushinp()
        for _ in range(turns):                  # дії в бою забирають ходи
            if self.dead:
                break
            self._end_turn()

    def _pickup_here(self) -> None:
        p = self.state.player
        if (p.x, p.y) in self.state.piles:
            loot.pick_up(self.state, p.x, p.y)
        else:
            self.state.log("Тут нічого підбирати.")

    def _quick_use(self, kind: str) -> None:
        ok, message = self.state.player.quick_use(kind)
        self.state.log(message)
        if ok and self._enemy_near(THREAT_RADIUS):
            self._end_turn()

    # ---------- debug ----------
    def _debug_loot(self) -> None:
        state, p = self.state, self.state.player
        for _ in range(3):
            item = loot.roll_gear(p.level + 2, p.class_id, state.rng)
            if item and p.inventory.add(item):
                state.log(f"[debug] Отримано: {item.name}")
        p.gold += 50

    def _debug_fog(self) -> None:
        self.state.fog_enabled = not self.state.fog_enabled
        status = "вимкнено" if not self.state.fog_enabled else "увімкнено"
        self.state.log(f"[debug] Туман війни {status}.")

    def _debug_time(self) -> None:
        self.state.turn += 200
        self.state.log(f"[debug] Хід {self.state.turn}, загроза світу +{self.state.threat_bonus}.")

    def _debug_event(self) -> None:
        state = self.state
        if state.level_id != "overworld":
            state.log("[debug] Події запускаються лише на поверхні.")
            return
        ids = list(event_defs())
        self._event_index = (self._event_index + 1) % len(ids)
        state.events.force_start(state, ids[self._event_index])

    def _debug_quests(self) -> None:
        """Миттєво виконує всі активні квести (для демонстрації)."""
        state, p = self.state, self.state.player
        log = state.quest_log
        for qid in list(log.active):
            q = quests.quest_defs()[qid]
            goal = quests.goal_of(qid)
            if q["type"] == "collect":
                p.inventory.add(get_item(q["target"]), goal)
            else:
                log.active[qid] = goal
        state.log("[debug] Усі активні квести виконано.")

    def _debug_teleport(self) -> None:
        """Кожне натискання: центр міста -> вхід у підземелля 1 -> 2 -> ... -> знову місто."""
        state = self.state
        if state.level_id != "overworld":
            state.log("[debug] Телепорт працює лише на поверхні.")
            return
        spots = [state.tilemap.spawn] + list(state.tilemap.entrances.values())
        self._tp_index = (self._tp_index + 1) % len(spots)
        state.player.move_to(*spots[self._tp_index])
        state.log(f"[debug] Телепорт: пункт {self._tp_index + 1} з {len(spots)}.")
        self._check_zone()

    def _animate_projectile(self, target, skill) -> None:
        """Короткий політ снаряда по лінії Брезенхема."""
        p = self.state.player
        path = self.state.tilemap.line_points(p.x, p.y, target.x, target.y)[:-1]
        for x, y in path:
            self.renderer.draw(self.state, overlay=[(x, y, skill["glyph"], skill["color"])])
            curses.napms(40)
        curses.flushinp()   # викидаємо клавіші, натиснуті під час анімації

    # ---------- кінець ходу ----------
    def _end_turn(self) -> None:
        state = self.state
        player = state.player
        state.turn += 1
        state.update_vision()       # щоб монстр був підсилений ще до своєї атаки

        in_combat = False
        for monster in list(state.entities):
            if not isinstance(monster, Monster) or not monster.is_alive:
                continue
            # далекі монстри "сплять": у великому світі це економить багато часу
            if abs(monster.x - player.x) + abs(monster.y - player.y) > ACTIVE_RADIUS:
                continue
            if monster.act(state):
                combat.monster_attack(state, monster)
                in_combat = True
                if not player.is_alive:
                    break

        if not player.is_alive:
            self._on_death()
            return

        if state.tilemap.is_safe(player.x, player.y):          # у місті швидко лікуємось
            player.heal(max(1, player.max_hp // TOWN_REGEN_HP))
            player.restore_mp(max(1, player.max_mp // TOWN_REGEN_MP))
        elif not in_combat and state.turn % REGEN_EVERY == 0:
            player.heal(max(1, player.max_hp // 40))
            player.restore_mp(max(1, player.max_mp // 30))

        # економіка та світові події живуть власним життям
        state.market.tick(state)
        state.events.tick(state)

        # респавн лише на поверхні; під час кривавого місяця монстрів більше
        spawn_every = int(state.events.effect("spawn_every", RESPAWN_EVERY))
        cap = MAX_MONSTERS + (40 if spawn_every < RESPAWN_EVERY else 0)
        if (state.level_id == "overworld" and state.turn % spawn_every == 0
                and len(state.entities) < cap):
            spawn_monster(state)

        loot.expire_piles(state)
        self._check_zone()

        if state.turn % AUTOSAVE_EVERY == 0 and not in_combat:
            self._save(save_manager.AUTOSAVE, quiet=True)

    # ---------- смерть ----------
    def _on_death(self) -> None:
        self.dead = True
        self.state.deaths += 1
        self.state.log("Світ темніє... Ти загинув.")

    def _show_death(self) -> None:
        state = self.state
        self.renderer.draw(state)            # на мить показуємо останній удар
        curses.napms(700)
        curses.flushinp()
        can_load = save_manager.latest_slot() is not None
        choice = DeathScreen(self.scr, state, can_load).run()
        curses.flushinp()
        if choice == "respawn":
            self._respawn()
        elif choice == "load":
            self.result = ("load", save_manager.latest_slot())
            state.running = False
        else:
            self.result = ("menu", None)
            state.running = False

    def _respawn(self) -> None:
        state = self.state
        p = state.player
        lost = p.revive(DEATH_XP_LOSS)
        gold_lost = int(p.gold * DEATH_GOLD_LOSS)
        p.gold -= gold_lost

        if state.level_id != "overworld":       # смерть у підземеллі: прокидаємось у місті
            state.leave_dungeon(to_town=True)
        sx, sy = state.tilemap.spawn
        p.move_to(sx, sy)
        # прибираємо монстрів біля точки відродження (NPC не чіпаємо)
        state.entities = [e for e in state.entities
                          if not isinstance(e, Monster) or abs(e.x - sx) + abs(e.y - sy) > 6]
        state.log(f"Ти прокидаєшся на площі Ельдорії. Втрачено: {lost} досвіду, {gold_lost} золота.")
        self.dead = False
        self.zone = None
        self._check_zone()