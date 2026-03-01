@echo off
echo УСТАНОВКА ШКОЛЬНОГО БОТА
echo =========================
echo.

echo 1. Обновляем pip...
python -m pip install --upgrade pip

echo.
echo 2. Устанавливаем python-telegram-bot...
python -m pip install python-telegram-bot==20.3

echo.
echo 3. Устанавливаем остальные библиотеки...
python -m pip install -r requirements.txt

echo.
echo 4. Проверяем установку...
python check_install.py

echo.
echo 5. Запускаем бота...
python bot.py

pause