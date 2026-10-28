"""Точка входу: Echoes of Eldoria."""
import curses
import locale
import os

os.environ.setdefault("ESCDELAY", "25")  # щоб Esc не "гальмував"

from game.config import INITIAL_MONSTERS, MAP_HEIGHT, MAP_WIDTH
from game.engine import Engine
from game.entities.monster import populate_world
from game.entities.npc import populate_npcs
from game.entities.player import Player
from game.persistence import save_manager
from game.state import GameState
from game.ui import colors
from game.ui.renderer import put
from game.ui.title_screens import TitleScreen
from game.world.generator import generate_overworld
from game.world.zones import populate_huts


def show_message(stdscr, text: str) -> None:
    """Короткий напис посеред екрана на час довгої операції."""
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    put(stdscr, height // 2, max(0, (width - len(text)) // 2), text, colors.attr("title"))
    stdscr.refresh()


def create_new_game(stdscr, name: str, class_id: str) -> GameState:
    show_message(stdscr, "Створюю світ Ельдорії...")
    tilemap = generate_overworld(MAP_WIDTH, MAP_HEIGHT)
    sx, sy = tilemap.spawn
    state = GameState(Player(name, class_id, sx, sy), tilemap)
    populate_world(state, INITIAL_MONSTERS)
    populate_huts(state)
    populate_npcs(state)
    return state


def load_or_note(stdscr, title: TitleScreen, slot: str) -> GameState | None:
    """Завантажує гру. Якщо не вийшло, повертає None і ставить повідомлення в меню."""
    show_message(stdscr, "Завантаження...")
    try:
        return save_manager.load_game(slot)
    except save_manager.SaveError as error:
        title.note = str(error)
        return None


def app(stdscr) -> None:
    curses.curs_set(0)
    colors.init_colors()
    title = TitleScreen(stdscr)
    state: GameState | None = None

    while True:
        if state is None:                           # головне меню
            choice = title.run()
            if choice[0] == "quit":
                return
            if choice[0] == "new":
                state = create_new_game(stdscr, choice[1], choice[2])
            else:
                state = load_or_note(stdscr, title, choice[1])
                if state is None:
                    continue

        action, payload = Engine(stdscr, state).run()
        state = None
        if action == "quit":
            return
        if action == "load":                        # з екрана смерті
            state = load_or_note(stdscr, title, payload)


def main() -> None:
    locale.setlocale(locale.LC_ALL, "")   # потрібно для кирилиці в curses
    try:
        curses.wrapper(app)
    except KeyboardInterrupt:
        pass
    print("Дякуємо за гру! До зустрічі в Ельдорії.")


if __name__ == "__main__":
    main()