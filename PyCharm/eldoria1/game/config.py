"""Глобальні налаштування та константи гри."""
import curses
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SAVES_DIR = BASE_DIR / "saves"

GAME_TITLE = "Echoes of Eldoria"
DEBUG = True  # перед здачею постав False

# --- Світ ---
MAP_WIDTH = 240
MAP_HEIGHT = 120

# --- Інтерфейс ---
HUD_WIDTH = 30       # ширина правої панелі
LOG_HEIGHT = 5       # 1 рядок-роздільник + 4 рядки повідомлень
MIN_TERM_WIDTH = 80
MIN_TERM_HEIGHT = 32
MAX_LOG_SIZE = 200

# --- Огляд (туман війни) ---
VISION_RADIUS = 7           # радіус огляду по вертикалі (у клітинках)
VISION_X_STRETCH = 2        # по горизонталі ширше вдвічі: символи вужчі за висоту
TOWN_VISION_BONUS = 3       # у місті вдень видно далі
SPAWN_MIN_PLAYER_DIST = 18  # нові монстри з'являються поза полем зору

# --- Місто ---
TOWN_REGEN_HP = 15          # у місті щоходу лікуємось на max_hp / 15
TOWN_REGEN_MP = 12          # ... і відновлюємо max_mp / 12

# --- Зростання монстрів з часом ---
SCALING_TURNS = 150         # перший бонусний рівень на ході 150 (далі росте як корінь)
SCALING_MAX_BONUS = 8       # стеля бонусних рівнів
SCALING_HP = 0.07           # +7% HP за кожен бонусний рівень
SCALING_ATTACK = 0.05       # +5% атаки
SCALING_DEFENSE = 0.04      # +4% захисту
SCALING_XP = 0.08           # +8% досвіду за вбивство

# --- Бій ---
CRIT_CHANCE = 0.10          # базовий шанс крита у гравця
MONSTER_CRIT_CHANCE = 0.05  # шанс крита у монстрів
CRIT_MULTIPLIER = 2.0
MISS_CHANCE = 0.07          # шанс промаху (вміння не промахуються)
REGEN_EVERY = 4             # кожні N ходів поза боєм відновлюємось
REST_HEAL_PCT = 0.12        # скільки відновлює відпочинок (R)
DEATH_XP_LOSS = 0.5         # частка поточного XP, яку втрачаємо при смерті
DEATH_GOLD_LOSS = 0.1       # частка золота, яку втрачаємо при смерті

# --- Монстри ---
INITIAL_MONSTERS = 200
MAX_MONSTERS = 240
RESPAWN_EVERY = 6           # раз на N ходів з'являється новий монстр
SAFE_RADIUS = 12            # біля старту монстри не з'являються
MONSTER_LEASH = 8           # як далеко від "дому" блукає монстр
ACTIVE_RADIUS = 36          # монстри далі за цю відстань "сплять" (економія часу)

# --- Інвентар та здобич ---
INVENTORY_SIZE = 24         # кількість слотів рюкзака
MAX_STACK = 20              # скільки зілль/матеріалів влізає в один слот
START_GOLD = 25
PILE_LIFETIME = 500         # скільки ходів здобич лежить на землі
THREAT_RADIUS = 6           # якщо ворог ближче, дії з предметами забирають хід

# --- Керування ---
# WASD + стрілки + українська розкладка (ц, ф, і, в)
_WASD = {"w": (0, -1), "a": (-1, 0), "s": (0, 1), "d": (1, 0)}
_UA_TO_EN = {"ц": "w", "ф": "a", "і": "s", "в": "d"}

MOVE_KEYS: dict = {
    curses.KEY_UP: (0, -1),
    curses.KEY_DOWN: (0, 1),
    curses.KEY_LEFT: (-1, 0),
    curses.KEY_RIGHT: (1, 0),
}
for _key, _delta in _WASD.items():
    MOVE_KEYS[_key] = _delta
    MOVE_KEYS[_key.upper()] = _delta
for _ua, _en in _UA_TO_EN.items():
    MOVE_KEYS[_ua] = _WASD[_en]
    MOVE_KEYS[_ua.upper()] = _WASD[_en]

QUIT_KEYS = {"q", "Q", "й", "Й", "\x1b"}   # \x1b = Esc
SKILL_KEYS = {"f", "F", "а", "А"}          # вміння класу
REST_KEYS = {"r", "R", "к", "К", " "}      # відпочинок (R або пробіл)
INVENTORY_KEYS = {"i", "I", "ш", "Ш"}      # рюкзак
PICKUP_KEYS = {"g", "G", "п", "П"}         # підібрати здобич під ногами
QUEST_KEYS = {"j", "J", "о", "О"}          # журнал завдань
MAP_KEYS = {"m", "M", "ь", "Ь"}            # карта світу
QUICK_HEAL_KEYS = {"1"}                    # швидке зілля здоров'я
QUICK_MANA_KEYS = {"2"}                    # швидке зілля мани
DEBUG_XP_KEY = "+"
DEBUG_LOOT_KEY = "L"                       # debug: дає випадкову екіпіровку
DEBUG_FOG_KEYS = {"v", "V", "м", "М"}      # debug: вимкнути/увімкнути туман
DEBUG_TIME_KEY = "]"                       # debug: перемотати 200 ходів уперед
DEBUG_TP_KEY = "T"                         # debug: телепорт місто -> входи в підземелля
DEBUG_QUEST_KEY = "K"                      # debug: виконати всі активні квести

# --- Керування в меню рюкзака та діалогів ---
MENU_UP = {curses.KEY_UP, "w", "W", "ц", "Ц"}
MENU_DOWN = {curses.KEY_DOWN, "s", "S", "і", "І"}
MENU_SWITCH = {"\t", curses.KEY_LEFT, curses.KEY_RIGHT,
               "a", "A", "ф", "Ф", "d", "D", "в", "В"}
MENU_CONFIRM = {"\n", "\r", curses.KEY_ENTER, "e", "E", "у", "У"}
MENU_DROP = {"x", "X", "ч", "Ч"}
MENU_SORT = {"t", "T", "е", "Е"}

AUTOSAVE_EVERY = 300                 # автозбереження кожні N ходів (не в бою)
SAVE_SLOTS = 3                       # кількість ручних слотів
SAVE_KEYS = {"p", "P", "з", "З"}     # швидке збереження
HELP_KEYS = {"h", "H", "р", "Р"}     # довідка

def load_json(filename: str) -> dict:
    """Завантажує JSON-файл з папки data/."""
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)