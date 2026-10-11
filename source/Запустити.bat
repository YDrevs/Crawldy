@echo off
rem Umyslno tilky ASCII: cmd ne chytaye UTF-8 u tili .bat i lamaye kyrylytsyu.
rem Vsya logika i povidomlennya - u scripts\start.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
if errorlevel 1 pause
