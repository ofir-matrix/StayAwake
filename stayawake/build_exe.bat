@echo off
REM Build script for StayAwake executable
echo Building StayAwake executable...
pyinstaller StayAwake.spec
echo.
echo Build complete! The executable should be in the 'dist' folder.
pause

