@echo off
rem Assemble the Signal distribution ZIP with a freshly compiled binary.
rem Builds in system Temp; never reads or overwrites common/bin/signal.exe.
rem Does not launch the application or copy the EXE to the project root.
rem Layout: signal.exe, release_info.txt, postman, common/data, common/doc,
rem empty common/log, and source code with README.md in common/src.
rem Active config, license acceptance, logs, backups and UI layouts are excluded.
rem Config and theme defaults are prepared in system Temp; local settings stay intact.
rem Output: dist/Signal_VERSION.zip, using ReleaseDefinition.VERSION.
rem Implementation: common/core/toolkit/build_binary/build_release.py
rem Requires PyInstaller, application dependencies, HTML guide and matching Postman archive.
rem Usage from the project root: common\scripts\build_release.cmd
rem Can also be launched by its full path from any working directory.
rem Uses Python 3.12 installed under LOCALAPPDATA/Programs/Python/Python312.

"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0..\core\toolkit\build_binary\build_release.py"
exit /b %errorlevel%
