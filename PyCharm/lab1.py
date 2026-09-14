num1 = float(input("Введіть перше число: "))
num2 = float(input("Введіть друге число: "))

suma = num1 + num2
riznytsia = num1 - num2
dobutok = num1 * num2

print(f"Сума: {suma}")
print(f"Різниця: {riznytsia}")
print(f"Добуток: {dobutok}")

if num2 != 0:
    chastka = num1 / num2
    print(f"Частка: {chastka}")
else:
    print("Ділення на нуль неможливе")