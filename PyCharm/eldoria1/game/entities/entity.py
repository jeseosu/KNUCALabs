"""Базовий клас для всіх живих істот у грі."""


class Entity:
    def __init__(self, name: str, x: int, y: int, glyph: str, color: str,
                 max_hp: int, attack: int, defense: int):
        self.name = name
        self.x = x
        self.y = y
        self.glyph = glyph
        self.color = color
        self.max_hp = max_hp
        self.hp = max_hp
        self.attack = attack
        self.defense = defense

    @property
    def is_alive(self) -> bool:
        return self.hp > 0

    @property
    def power(self) -> int:
        """Реальна сила атаки. Гравець перевизначає її з урахуванням спорядження."""
        return self.attack

    @property
    def armor(self) -> int:
        """Реальний захист. Гравець перевизначає його з урахуванням спорядження."""
        return self.defense

    def move_to(self, x: int, y: int) -> None:
        self.x, self.y = x, y

    def take_damage(self, amount: int) -> int:
        """Віднімає HP, повертає реально отриману шкоду."""
        amount = max(0, amount)
        self.hp = max(0, self.hp - amount)
        return amount

    def heal(self, amount: int) -> int:
        """Лікує, повертає скільки HP реально відновлено."""
        before = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - before