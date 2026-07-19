@echo off
title Comprehensive Text Menu Fix
echo ===================================================
echo   Rebuilding .txt associations and New Menu...
echo ===================================================
echo.

:: 1. Define .txt as a standard text file
reg add "HKEY_CLASSES_ROOT\.txt" /ve /t REG_SZ /d "txtfile" /f
reg add "HKEY_CLASSES_ROOT\.txt" /v "Content Type" /t REG_SZ /d "text/plain" /f
reg add "HKEY_CLASSES_ROOT\.txt" /v "PerceivedType" /t REG_SZ /d "text" /f

:: 2. Rebuild the ShellNew key
reg add "HKEY_CLASSES_ROOT\.txt\ShellNew" /v "NullFile" /t REG_SZ /d "" /f

:: 3. Ensure the system knows what a "txtfile" is called
reg add "HKEY_CLASSES_ROOT\txtfile" /ve /t REG_SZ /d "Text Document" /f

echo.
echo ===================================================
echo Registry updated. Restarting Windows Explorer...
echo Your taskbar will flash for a second.
echo ===================================================
taskkill /f /im explorer.exe
start explorer.exe

echo.
echo Complete! Try right-clicking your desktop now.
pause