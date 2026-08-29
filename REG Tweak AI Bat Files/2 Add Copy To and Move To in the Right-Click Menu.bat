@echo off
title Add Copy To and Move To
echo Adding Copy To folder and Move To folder to the right-click menu...

reg add "HKCU\Software\Classes\AllFilesystemObjects\shellex\ContextMenuHandlers\Copy To" /ve /t REG_SZ /d "{C2FBB630-2971-11D1-A18C-00C04FD75D13}" /f
reg add "HKCU\Software\Classes\AllFilesystemObjects\shellex\ContextMenuHandlers\Move To" /ve /t REG_SZ /d "{C2FBB631-2971-11D1-A18C-00C04FD75D13}" /f

echo.
echo Complete! Right-click a file to see Copy To folder and Move To folder.
pause
