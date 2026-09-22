from collections import defaultdict
from functools import reduce


art_data = [
    {"title": "Mona Lisa", "artist": "Leonardo da Vinci", "category": "Painting", "year": 1503, "price": 860000000},
    {"title": "Starry Night", "artist": "Vincent van Gogh", "category": "Painting", "year": 1889, "price": 100000000},
    {"title": "David", "artist": "Michelangelo", "category": "Sculpture", "year": 1504, "price": 200000000},
    {"title": "The Thinker", "artist": "Auguste Rodin", "category": "Sculpture", "year": 1904, "price": 15000000}
]


def add_artwork(data, artwork):
    data.append(artwork)
    print("Твір мистецтва додано успішно.")


def remove_artwork(data, index):
    if 0 <= index < len(data):
        del data[index]
        print("Твір видалено успішно.")
    else:
        print("Невірний індекс.")


def update_artwork(data, index, key, value):
    if 0 <= index < len(data):
        data[index][key] = value
        print("Інформацію оновлено успішно.")
    else:
        print("Невірний індекс.")


def find_artworks_by_artist(data, artist):
    return list(filter(lambda x: x["artist"].lower() == artist.lower(), data))


def calculate_total_value(data):
    return reduce(lambda acc, art: acc + art["price"], data, 0)


def sort_artworks_by_year(data):
    return sorted(data, key=lambda x: x["year"])


def group_artworks_by_category(data):
    categories = defaultdict(list)
    for art in data:
        categories[art["category"]].append(art)
    return dict(categories)


def get_unique_categories(data):
    categories_set = {art["category"] for art in data}
    return categories_set


def print_menu():
    print("\n==== Меню управління галереєю ====")
    print("1. Показати всі твори")
    print("2. Додати новий твір")
    print("3. Видалити твір")
    print("4. Оновити інформацію про твір")
    print("5. Знайти твори за автором")
    print("6. Обчислити загальну вартість колекції")
    print("7. Групувати твори за категоріями")
    print("8. Показати унікальні категорії (множини)")
    print("9. Сортувати твори за роком")
    print("0. Вийти")


def main():
    global art_data
    while True:
        print_menu()
        choice = input("Оберіть опцію: ")

        if choice == "1":
            for i, art in enumerate(art_data):
                print(f"{i}: {art}")
        elif choice == "2":
            title = input("Введіть назву: ")
            artist = input("Введіть автора: ")
            category = input("Введіть категорію: ")
            year = int(input("Введіть рік створення: "))
            price = float(input("Введіть вартість: "))
            new_art = {"title": title, "artist": artist, "category": category, "year": year, "price": price}
            add_artwork(art_data, new_art)
        elif choice == "3":
            index = int(input("Введіть індекс твору для видалення: "))
            remove_artwork(art_data, index)
        elif choice == "4":
            index = int(input("Введіть індекс твору для оновлення: "))
            key = input("Введіть ключ для оновлення (title/artist/category/year/price): ")
            value = input("Введіть нове значення: ")
            if key in ["year"]:
                value = int(value)
            elif key in ["price"]:
                value = float(value)
            update_artwork(art_data, index, key, value)
        elif choice == "5":
            artist = input("Введіть автора для пошуку: ")
            results = find_artworks_by_artist(art_data, artist)
            for art in results: print(art)
        elif choice == "6":
            total = calculate_total_value(art_data)
            print(f"Загальна вартість: {total}")
        elif choice == "7":
            grouped = group_artworks_by_category(art_data)
            for category, artworks in grouped.items():
                print(f"\n{category}:")
                for art in artworks: print(f"  {art}")
        elif choice == "8":
            categories = get_unique_categories(art_data)
            print(f"Унікальні категорії: {categories}")
        elif choice == "9":
            sorted_art = sort_artworks_by_year(art_data)
            for art in sorted_art: print(art)
        elif choice == "0":
            print("Дякуємо за використання програми!")
            break
        else:
            print("Невірний вибір. Спробуйте ще раз.")


if __name__ == "__main__":
    main()