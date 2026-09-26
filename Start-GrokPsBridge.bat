@echo off
title Grok PowerShell Bridge
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Start-GrokPsBridge.ps1"
