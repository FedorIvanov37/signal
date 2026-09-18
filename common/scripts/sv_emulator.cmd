@echo off
rem Start the local SmartVista emulator to test Signal without a processing host.
rem Listens on 127.0.0.1:16677 by default and generates test responses.
rem It does not perform real transaction authorization.
rem Implementation: common/core/toolkit/sv_emulator.py
rem Requires Python 3.12 in LOCALAPPDATA/Programs/Python/Python312
rem with the project's Python dependencies installed.
rem Usage from the project root: common\scripts\sv_emulator.cmd
rem Custom port: common\scripts\sv_emulator.cmd --port 16678
rem Help: common\scripts\sv_emulator.cmd --help
rem Set the same host and port in Signal. Stop the emulator with Ctrl+C.
rem You can also launch this file by its full path from any directory.

setlocal
pushd "%~dp0..\.." || exit /b 1
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m common.core.toolkit.sv_emulator %*
set "emulator_exit_code=%errorlevel%"
popd
exit /b %emulator_exit_code%
