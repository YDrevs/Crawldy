@echo off
rem Umyslno tilky ASCII: dyv. komentar u Zapustyty.bat
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1"
if errorlevel 1 pause
