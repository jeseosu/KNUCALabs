"""Автотести збереження. Запуск з кореня проєкту: python3 -m unittest tests.test_save_load -v"""
import tempfile
import unittest
from pathlib import Path

from game.config import MAP_HEIGHT, MAP_WIDTH
from game.entities.monster import populate_world
from game.entities.npc import populate_npcs
from game.entities.player import Player
from game.persistence import save_manager
from game.state import GameState
from game.world.generator import generate_overworld
from game.world.zones import populate_huts


def make_state(seed: int = 1) -> GameState:
    tilemap = generate_overworld(MAP_WIDTH, MAP_HEIGHT, seed=seed)
    sx, sy = tilemap.spawn
    state = GameState(Player("Тест", "mage", sx, sy), tilemap, seed=seed)
    populate_world(state, 40)
    populate_huts(state)
    populate_npcs(state)
    return state


def entity_keys(entities) -> list:
    keys = []
    for e in entities:
        ident = getattr(e, "monster_id", None) or getattr(e, "npc_id", None)
        keys.append((ident, e.x, e.y, e.hp))
    return sorted(keys)


class SaveLoadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_dir = save_manager.SAVES_DIR
        save_manager.SAVES_DIR = Path(self.tmp.name)      # тести не чіпають справжні збереження

    def tearDown(self):
        save_manager.SAVES_DIR = self._old_dir
        self.tmp.cleanup()

    def test_roundtrip_overworld(self):
        state = make_state()
        state.turn, state.kills = 123, 7
        state.player.gold = 777
        state.player.gain_xp(500)
        state.explored.add((5, 5))
        state.log("тестове повідомлення")

        save_manager.save_game(state, "1")
        loaded = save_manager.load_game("1")

        self.assertEqual(loaded.turn, 123)
        self.assertEqual(loaded.kills, 7)
        self.assertEqual(loaded.player.gold, 777)
        self.assertEqual(loaded.player.level, state.player.level)
        self.assertEqual(loaded.player.xp, state.player.xp)
        self.assertEqual(loaded.player.inventory.to_dict(), state.player.inventory.to_dict())
        self.assertEqual(loaded.tilemap.grid, state.tilemap.grid)
        self.assertEqual(loaded.explored, state.explored)
        self.assertEqual(entity_keys(loaded.entities), entity_keys(state.entities))
        self.assertEqual(loaded.messages[-1], "тестове повідомлення")
        self.assertEqual(loaded.slot, "1")

    def test_random_generator_is_restored(self):
        state = make_state()
        save_manager.save_game(state, "1")
        loaded = save_manager.load_game("1")
        self.assertEqual([state.rng.random() for _ in range(5)],
                         [loaded.rng.random() for _ in range(5)])

    def test_roundtrip_inside_dungeon(self):
        state = make_state()
        state.enter_dungeon("rat_cellar")
        dungeon_grid = state.tilemap.grid

        save_manager.save_game(state, "2")
        loaded = save_manager.load_game("2")

        self.assertEqual(loaded.level_id, "rat_cellar")
        self.assertEqual(loaded.tilemap.grid, dungeon_grid)
        self.assertIn("overworld", loaded.levels)
        self.assertEqual((loaded.player.x, loaded.player.y), (state.player.x, state.player.y))
        loaded.leave_dungeon()                       # повернення на поверхню працює
        self.assertEqual(loaded.level_id, "overworld")

    def test_market_and_quests_survive(self):
        state = make_state()
        state.quest_log.active["q_first_steps"] = 3
        state.quest_log.done.add("q_slime")
        state.market.mail_gold = 55
        lots_before = len(state.market.lots)

        save_manager.save_game(state, "1")
        loaded = save_manager.load_game("1")

        self.assertEqual(loaded.quest_log.active, {"q_first_steps": 3})
        self.assertIn("q_slime", loaded.quest_log.done)
        self.assertEqual(loaded.market.mail_gold, 55)
        self.assertEqual(len(loaded.market.lots), lots_before)

    def test_slot_summary_and_latest(self):
        state = make_state()
        self.assertIsNone(save_manager.slot_summary("1"))
        self.assertIsNone(save_manager.latest_slot())
        save_manager.save_game(state, "1")
        info = save_manager.slot_summary("1")
        self.assertEqual(info["name"], "Тест")
        self.assertTrue(info["ok"])
        self.assertEqual(save_manager.latest_slot(), "1")
        save_manager.delete_save("1")
        self.assertIsNone(save_manager.slot_summary("1"))

    def test_broken_and_missing_files(self):
        save_manager.save_path("2").write_text("{це не json", encoding="utf-8")
        with self.assertRaises(save_manager.SaveError):
            save_manager.load_game("2")
        with self.assertRaises(save_manager.SaveError):
            save_manager.load_game("3")
        self.assertTrue(save_manager.slot_summary("2")["error"])


if __name__ == "__main__":
    unittest.main()