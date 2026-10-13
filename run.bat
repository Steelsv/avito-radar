@echo off
chcp 65001 >nul
title Смотрящий за Авито
echo Запуск: Смотрящий за Авито...
python run.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Программа завершилась с ошибкой. Нажмите любую клавишу для выхода.
    pause >nul
)
