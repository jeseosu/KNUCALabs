"""Економіка: крамниці, аукціон із ботами-«гравцями» та динамічний попит."""
from dataclasses import dataclass
from functools import lru_cache

from game.config import load_json
from game.items.item import Item, all_item_ids, get_item, rarity_defs

BUY_MARKUP = 1.5            # крамниця продає за value * 1.5
AUCTION_FEE = 0.05          # комісія аукціону з продажу
TICK_EVERY = 20             # раз на стільки ходів боти "діють"
MAX_BOT_LOTS = 22
MAX_PLAYER_LOTS = 6
BOT_LOT_LIFETIME = (600, 1600)
PLAYER_LOT_LIFETIME = 1500
FEED_SIZE = 8

BOT_NAMES = [
    "Лісовий_Лис", "Мирослава", "xX_Дракон_Xx", "Тарас-Мисливець", "Соломія",
    "Орест_Коваль", "Мандрівник77", "Купець_Іван", "Zoryana", "Hryhorii",
    "Лицар_Данило", "ТіньНочі", "Бджілка", "Степан_Бульба", "NoobSlayer",
]


@lru_cache(maxsize=1)
def shop_defs() -> dict:
    return load_json("shops.json")


@dataclass
class Lot:
    id: int
    item_id: str
    count: int
    price: int          # викуп за весь лот
    seller: str
    mine: bool
    expires: int


# ---------- ціни в крамницях ----------
def shop_price(state, item: Item) -> int:
    return max(1, round(item.value * BUY_MARKUP * state.events.mult("shop_mult")))


def sell_price(state, shop_id: str, item: Item) -> int:
    rate = shop_defs()[shop_id].get("sell_rate", 0.5)
    return max(1, int(item.value * rate * state.events.mult("sell_mult")))


def shop_stock(state, shop_id: str) -> list[tuple[Item, int]]:
    return [(get_item(item_id), n) for item_id, n in state.market.stock[shop_id].items()]


def buy_from_shop(state, shop_id: str, item: Item) -> tuple[bool, str]:
    stock = state.market.stock[shop_id]
    left = stock.get(item.id, 0)
    if left <= 0:
        return False, "Розпродано. Заходь пізніше."
    price = shop_price(state, item)
    p = state.player
    if p.gold < price:
        return False, f"Не вистачає золота (потрібно {price})."
    if p.inventory.free_space_for(item) < 1:
        return False, "Рюкзак повний!"
    p.gold -= price
    p.inventory.add(item, 1)
    stock[item.id] = left - 1
    return True, f"Куплено: {item.name} за {price} золота."


def sell_to_shop(state, shop_id: str, index: int, all_stack: bool = False) -> tuple[bool, str]:
    cfg = shop_defs()[shop_id]
    inv = state.player.inventory
    stack = inv.stacks[index]
    item = stack.item
    if item.kind not in cfg["buys"]:
        return False, "Цей торговець такого не купує."
    count = stack.count if all_stack else 1
    total = sell_price(state, shop_id, item) * count
    inv.remove_at(index, count)
    state.player.gold += total
    suffix = f" x{count}" if count > 1 else ""
    return True, f"Продано: {item.name}{suffix} за {total} золота."


# ---------- ринок ----------
class Market:
    def __init__(self):
        self.lots: list[Lot] = []
        self.next_id = 1
        self.demand: dict[str, float] = {}      # item_id -> множник попиту
        self.feed: list[str] = []               # новини ринку
        self.mail_gold = 0                      # виручка, яку треба забрати
        self.mail_items: list[tuple[str, int]] = []
        self.last_tick = 0
        self.stock: dict[str, dict[str, int]] = {}
        self.stock_turn: dict[str, int] = {}
        for shop_id, cfg in shop_defs().items():
            self.stock[shop_id] = {item_id: n for item_id, n in cfg["stock"]}
            self.stock_turn[shop_id] = 0

    def seed(self, state) -> None:
        """Початкові лоти ботів, щоб аукціон не був порожнім."""
        for _ in range(14):
            self._add_bot_lot(state, announce=False)

    # ---------- ціни ----------
    def fair_price(self, item: Item, count: int = 1) -> int:
        return max(1, round(item.value * self.demand.get(item.id, 1.0) * count))

    def _post(self, text: str) -> None:
        self.feed.append(text)
        del self.feed[:-FEED_SIZE]

    def player_lots(self) -> list[Lot]:
        return [lot for lot in self.lots if lot.mine]

    # ---------- боти ----------
    def _add_bot_lot(self, state, announce: bool = True) -> None:
        rng, p = state.rng, state.player
        items, weights = [], []
        for item_id in all_item_ids():
            item = get_item(item_id)
            if item.equippable and not (p.level - 4 <= item.level_req <= p.level + 3):
                continue
            weight = rarity_defs()[item.rarity]["weight"]
            if item.classes and p.class_id not in item.classes:
                weight *= 0.3
            items.append(item)
            weights.append(weight)
        item = rng.choices(items, weights)[0]
        count = rng.randint(1, 5) if item.stackable else 1
        price = max(1, round(self.fair_price(item, count) * rng.uniform(0.85, 1.6)))
        lot = Lot(self.next_id, item.id, count, price, rng.choice(BOT_NAMES), False,
                  state.turn + rng.randint(*BOT_LOT_LIFETIME))
        self.next_id += 1
        self.lots.append(lot)
        if announce:
            suffix = f" x{count}" if count > 1 else ""
            self._post(f"{lot.seller} виставив: {item.name}{suffix} за {price}з")

    def add_bot_lots(self, state, count: int) -> None:
        for _ in range(count):
            self._add_bot_lot(state, announce=False)
        self._post("Прибув караван: нові лоти!")

    # ---------- час ----------
    def tick(self, state) -> None:
        self._restock(state)
        steps = (state.turn - self.last_tick) // TICK_EVERY
        if steps <= 0:
            return
        self.last_tick = state.turn
        for _ in range(min(steps, 6)):
            self._step(state)

    def _restock(self, state) -> None:
        for shop_id, cfg in shop_defs().items():
            if state.turn - self.stock_turn[shop_id] >= cfg.get("restock_turns", 400):
                self.stock[shop_id] = {item_id: n for item_id, n in cfg["stock"]}
                self.stock_turn[shop_id] = state.turn

    def _drift(self, state) -> None:
        rng = state.rng
        for item_id in list(self.demand):
            d = self.demand[item_id]
            d += (1 - d) * 0.12 + rng.uniform(-0.04, 0.04)
            d = max(0.6, min(1.8, d))
            if abs(d - 1) < 0.03:
                del self.demand[item_id]
            else:
                self.demand[item_id] = d
        if rng.random() < 0.35:                      # випадкова "мода" на предмет
            item = get_item(rng.choice(all_item_ids()))
            if item.value > 0:
                new = rng.choice((rng.uniform(1.35, 1.8), rng.uniform(0.6, 0.78)))
                self.demand[item.id] = new
                self._post(f"Попит на «{item.name}» {'зріс' if new > 1 else 'впав'}")

    def _step(self, state) -> None:
        rng, turn = state.rng, state.turn
        self._drift(state)
        boost = state.events.mult("auction_buy")

        survivors = []
        for lot in self.lots:
            item = get_item(lot.item_id)
            ratio = lot.price / self.fair_price(item, lot.count)
            suffix = f" x{lot.count}" if lot.count > 1 else ""
            if lot.mine:
                if turn >= lot.expires:
                    self.mail_items.append((lot.item_id, lot.count))
                    state.log(f"Лот «{item.name}» не продався. Предмет чекає в Гаспара.")
                    continue
                chance = max(0.0, min(0.7, 0.9 - 0.6 * ratio)) * boost
                if rng.random() < chance:
                    fee = int(lot.price * AUCTION_FEE)
                    self.mail_gold += lot.price - fee
                    buyer = rng.choice(BOT_NAMES)
                    self._post(f"{buyer} купив лот гравця: {item.name}{suffix}")
                    state.log(f"Твій лот «{item.name}» продано! Забери золото в Гаспара.")
                    continue
            else:
                if turn >= lot.expires:
                    continue
                chance = 0.07 * (1.6 if ratio < 1 else 1.0) * boost
                if rng.random() < chance:
                    self._post(f"{rng.choice(BOT_NAMES)} купив: {item.name}{suffix} за {lot.price}з")
                    continue
            survivors.append(lot)
        self.lots = survivors

        bots = sum(1 for lot in self.lots if not lot.mine)
        for _ in range(rng.randint(0, 2)):
            if bots < MAX_BOT_LOTS:
                self._add_bot_lot(state)
                bots += 1

    # ---------- дії гравця ----------
    def list_item(self, state, index: int, count: int, price: int) -> tuple[bool, str]:
        if len(self.player_lots()) >= MAX_PLAYER_LOTS:
            return False, f"Максимум {MAX_PLAYER_LOTS} власних лотів."
        inv = state.player.inventory
        count = max(1, min(count, inv.stacks[index].count))
        item = inv.remove_at(index, count)
        self.lots.append(Lot(self.next_id, item.id, count, max(1, price),
                             state.player.name, True, state.turn + PLAYER_LOT_LIFETIME))
        self.next_id += 1
        suffix = f" x{count}" if count > 1 else ""
        return True, f"Лот виставлено: {item.name}{suffix} за {price} золота."

    def _find(self, lot_id: int) -> Lot | None:
        return next((lot for lot in self.lots if lot.id == lot_id), None)

    def buy_lot(self, state, lot_id: int) -> tuple[bool, str]:
        lot = self._find(lot_id)
        if lot is None:
            return False, "Лот уже зник."
        if lot.mine:
            return False, "Це твій власний лот."
        p, item = state.player, get_item(lot.item_id)
        if p.gold < lot.price:
            return False, f"Не вистачає золота (потрібно {lot.price})."
        if p.inventory.free_space_for(item) < lot.count:
            return False, "Рюкзак повний!"
        p.gold -= lot.price
        p.inventory.add(item, lot.count)
        self.lots.remove(lot)
        suffix = f" x{lot.count}" if lot.count > 1 else ""
        return True, f"Куплено: {item.name}{suffix} за {lot.price} золота."

    def cancel_lot(self, state, lot_id: int) -> tuple[bool, str]:
        lot = self._find(lot_id)
        if lot is None or not lot.mine:
            return False, "Лот не знайдено."
        self.lots.remove(lot)
        self.mail_items.append((lot.item_id, lot.count))
        return True, "Лот знято. Предмет чекає на пошті (C)."

    def claim(self, state) -> tuple[bool, str]:
        p, parts = state.player, []
        if self.mail_gold:
            p.gold += self.mail_gold
            parts.append(f"{self.mail_gold} золота")
            self.mail_gold = 0
        rest = []
        for item_id, count in self.mail_items:
            item = get_item(item_id)
            added = p.inventory.add(item, count)
            if added:
                parts.append(item.name + (f" x{added}" if added > 1 else ""))
            if added < count:
                rest.append((item_id, count - added))
        self.mail_items = rest
        if not parts:
            return False, "На пошті порожньо (або рюкзак повний)."
        return True, "Забрано: " + ", ".join(parts) + "."