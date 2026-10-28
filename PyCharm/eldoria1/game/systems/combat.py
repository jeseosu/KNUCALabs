"""Бойова система: шкода, криті удари, нагорода за перемогу."""
from game.config import CRIT_MULTIPLIER, MISS_CHANCE, MONSTER_CRIT_CHANCE
from game.entities.monster import Monster
from game.items.loot import drop_loot


def roll_damage(attacker, defender, rng, multiplier: float = 1.0,
                crit_chance: float = 0.0, can_miss: bool = True):
    """Повертає кортеж (шкода, чи_крит, чи_промах)."""
    if can_miss and rng.random() < MISS_CHANCE:
        return 0, False, True

    raw = int((attacker.power + rng.randint(-2, 2)) * multiplier)
    is_crit = rng.random() < crit_chance
    if is_crit:
        raw = int(raw * CRIT_MULTIPLIER)

    damage = max(1, raw - defender.armor // 2)
    return damage, is_crit, False


def find_target(state, reach: int):
    """Найближчий монстр у межах reach, до якого є пряма видимість (NPC ігноруються)."""
    p = state.player
    candidates = []
    for m in state.entities:
        if not isinstance(m, Monster) or not m.is_alive:
            continue
        dist = abs(m.x - p.x) + abs(m.y - p.y)
        if dist <= reach:
            candidates.append((dist, m))
    candidates.sort(key=lambda pair: pair[0])
    for _, monster in candidates:
        if state.tilemap.line_clear(p.x, p.y, monster.x, monster.y):
            return monster
    return None


def xp_reward(monster, player) -> int:
    """Чим слабший монстр порівняно з гравцем, тим менше XP (захист від фарму)."""
    diff = monster.level - player.level
    factor = max(0.2, min(2.0, 1 + diff * 0.2))
    return max(1, round(monster.xp_reward * factor))


def player_attack(state, target, multiplier: float = 1.0,
                  skill_name: str | None = None) -> None:
    """Атака гравця. Якщо передано skill_name, це вміння (воно не промахується)."""
    dmg, crit, miss = roll_damage(state.player, target, state.rng, multiplier,
                                  state.player.crit_chance,
                                  can_miss=skill_name is None)
    if miss:
        state.log(f"Ти промахуєшся по: {target.name}.")
        return

    target.take_damage(dmg)
    crit_text = "КРИТ! " if crit else ""
    if skill_name:
        state.log(f"{crit_text}{skill_name}! {target.name}: -{dmg} HP.")
    else:
        state.log(f"{crit_text}Ти атакуєш: {target.name}, -{dmg} HP.")

    if not target.is_alive:
        _on_monster_death(state, target)


def monster_attack(state, monster) -> None:
    dmg, crit, miss = roll_damage(monster, state.player, state.rng,
                                  1.0, MONSTER_CRIT_CHANCE)
    if miss:
        state.log(f"{monster.name} промахується.")
        return
    state.player.take_damage(dmg)
    crit_text = "КРИТ! " if crit else ""
    state.log(f"{crit_text}{monster.name} {monster.verb} тебе: -{dmg} HP.")


def _on_monster_death(state, monster) -> None:
    state.entities.remove(monster)
    state.kills += 1
    state.log(f"{monster.name} переможений!")
    for message in state.player.gain_xp(xp_reward(monster, state.player)):
        state.log(message)
    drop_loot(state, monster)
    state.quest_log.on_kill(state, monster)          # прогрес квестів
    if getattr(monster, "is_boss", False):
        state.on_boss_killed(monster)