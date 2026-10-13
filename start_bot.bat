@echo off
chcp 65001 >nul
title Смотрящий за Авито — Telegram Бот
echo Запуск интерактивного Telegram-бота «Смотрящий за Авито»...
python run.py bot
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Бот завершился с ошибкой. Нажмите любую клавишу для выхода.
    pause >nul
)
