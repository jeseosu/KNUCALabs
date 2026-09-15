import random

# Звичайні функції
def print_artwork(art):
    # інформація про картину
    print(f"Назва: {art['title']}, Автор: {art['artist']}, Рік: {art['year']}, Ціна: ${art['price']}")

def get_age(year, current_year=2026):
    # вік картини
    return current_year - year

# Функція з параметрами за замовчуванням
def is_expensive(price, threshold=2000.0):
    # ціна картини
    return price > threshold

# Функція зі змінною кількістю аргументів (*args)
def average_price(*prices):
    # середня ціна з переданих цін
    if len(prices) == 0:
        return 0
    return sum(prices) / len(prices)

# Лямбда-функція
# знижка 10%
apply_discount_lambda = lambda price: round(price * 0.9, 2)


# рекурсивна функція
def find_oldest_year(data, start, end):

    # базовий випадок
    if start == end:
        return data[start]['year']

    # рекурсивно ділимо список навпіл
    mid = (start + end) // 2
    left_oldest = find_oldest_year(data, start, mid)
    right_oldest = find_oldest_year(data, mid + 1, end)

    return min(left_oldest, right_oldest)


# власна функція вищого порядку
def apply_to_prices(data, func):

    new_data = []
    for item in data:
        new_item = item.copy()
        new_item['price'] = func(item['price'])
        new_data.append(new_item)
    return new_data


# функція генерації даних
def generate_artworks(count=20):
    artworks = []
    artists = ["Да Вінчі", "Ван Гог", "Пікассо", "Моне", "Рембрандт"]
    for i in range(count):
        artworks.append({
            'title': f"Шедевр #{i + 1}",
            'artist': random.choice(artists),
            'year': random.randint(1500, 2000),
            'price': round(random.uniform(500.0, 5000.0), 2)
        })
    return artworks


# програма
def main():
    artworks = generate_artworks(25)

    while True:
        print("\n--- МЕНЮ ---")
        print("1. Показати перші 5 картин")
        print("2. Показати лише дорогі картини (використання filter)")
        print("3. Обчислити середню ціну всіх картин (*args)")
        print("4. Застосувати знижку 10% (функція вищого порядку)")
        print("5. Знайти рік найстарішої картини (рекурсія)")
        print("6. Вийти")

        try:
            choice = int(input("Ваш вибір (1-6): "))

            if choice == 1:
                for art in artworks[:5]:
                    print_artwork(art)

            elif choice == 2:

                expensive_arts = list(filter(lambda art: is_expensive(art['price']), artworks))
                print(f"Знайдено дорогих картин: {len(expensive_arts)}")
                for art in expensive_arts[:5]:
                    print_artwork(art)

            elif choice == 3:
                prices = [art['price'] for art in artworks]
                avg = average_price(*prices)
                print(f"Середня ціна картин у галереї: ${avg:.2f}")

            elif choice == 4:
                discounted_arts = apply_to_prices(artworks, apply_discount_lambda)
                print("Ціни після знижки (перші 5):")
                for art in discounted_arts[:5]:
                    print_artwork(art)

            elif choice == 5:
                oldest = find_oldest_year(artworks, 0, len(artworks) - 1)
                print(f"Найстаріший рік написання картини в базі: {oldest}")

            elif choice == 6:
                print("Дякуємо за використання програми!")
                break

            else:
                print("Невірний вибір. Введіть число від 1 до 6.")

        except ValueError:
            print("Помилка: Будь ласка, введіть числове значення!")


if __name__ == "__main__":
    main()