@echo off
rem Build the standalone Signal User Guide HTML with embedded images.
rem Source: common/doc/signal_user_guide.md
rem Images: common/data/static
rem Output: common/doc/signal_user_guide.html (replaced on each build).
rem Implementation: common/core/toolkit/make_doc.py
rem Requires Python 3.12 in LOCALAPPDATA/Programs/Python/Python312,
rem the grip package in that Python installation, and network access.
rem Usage from the project root: common\scripts\make_doc.cmd
rem You can also launch this file by its full path from any directory.

"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0..\core\toolkit\make_doc.py"
exit /b %errorlevel%
