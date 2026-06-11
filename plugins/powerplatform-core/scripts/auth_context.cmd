@echo off
setlocal
python "%~dp0auth_context.py" %*
exit /b %errorlevel%
