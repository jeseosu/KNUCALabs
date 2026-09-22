import re
from collections import Counter

def find_substring(text, substring):
    return text.find(substring)

def replace_substring(text, old, new):
    return text.replace(old, new)

def split_text(text, delimiter=' '):
    return text.split(delimiter)

def format_string_f(name, age):
    return f"Мене звати {name} і мені {age} років."

def format_string_method(name, age):
    return "Мене звати {} і мені {} років.".format(name, age)

def extract_emails(text):
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
    return re.findall(pattern, text)

def validate_phone_number(number):
    pattern = r'^\+?3?8?(0\d{9})$'
    return bool(re.match(pattern, number))

def extract_hashtags(text):
    return re.findall(r'#\w+', text)

def extract_mentions(text):
    return re.findall(r'@\w+', text)

def count_words(text):
    return len(re.findall(r'\w+', text))

def count_sentences(text):
    return len(re.findall(r'[.!?]+', text))

def word_frequency(text):
    words = re.findall(r'\w+', text.lower())
    return Counter(words)

def analyze_text(text):
    word_count = count_words(text)
    sentence_count = count_sentences(text)
    freq = word_frequency(text)
    emails = extract_emails(text)
    hashtags = extract_hashtags(text)
    mentions = extract_mentions(text)
    return {
        'word_count': word_count,
        'sentence_count': sentence_count,
        'word_frequency': freq.most_common(5),
        'emails': emails,
        'hashtags': hashtags,
        'mentions': mentions
    }

def format_analysis_results(results):
    output = "Результати аналізу тексту:\n\n"
    output += f"Кількість слів: {results['word_count']}\n"
    output += f"Кількість речень: {results['sentence_count']}\n\n"
    output += "Топ-5 найчастіших слів:\n"
    for word, count in results['word_frequency']:
        output += f"{word}: {count}\n"
    output += f"\nЗнайдені email адреси: {', '.join(results['emails'])}\n"
    output += f"Знайдені хештеги: {', '.join(results['hashtags'])}\n"
    output += f"Знайдені згадування: {', '.join(results['mentions'])}\n"
    return output

def main():
    print("Ласкаво просимо до аналізатора тексту!")
    while True:
        try:
            choice = input("\nОберіть опцію:\n1. Аналіз тексту\n2. Валідація телефону\n3. Вихід\nВаш вибір: ")
            if choice == '1':
                text = input("Введіть текст для аналізу: ")
                results = analyze_text(text)
                print(format_analysis_results(results))
            elif choice == '2':
                phone = input("Введіть номер телефону для валідації: ")
                if validate_phone_number(phone):
                    print("Номер телефону валідний.")
                else:
                    print("Номер телефону невалідний.")
            elif choice == '3':
                print("Дякуємо за використання аналізатора!")
                break
            else:
                print("Невірний вибір. Спробуйте ще раз.")
        except Exception as e:
            print(f"Виникла помилка: {e}")

if __name__ == '__main__':
    main()