@echo off
title Speed Up File Explorer
echo Disabling Automatic Folder Type Discovery...

:: Deletes existing cached folder views to ensure a clean slate
reg delete "HKCU\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\Bags" /f
reg delete "HKCU\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\BagMRU" /f

:: Forces all folders to open instantly as generic items
reg add "HKCU\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\Bags\AllFolders\Shell" /v FolderType /t REG_SZ /d "NotSpecified" /f

taskkill /f /im explorer.exe
start explorer.exe
echo Complete! Folders will now load instantly.
pause

2. Add "Copy To" and "Move To" in the Right-Click Menu