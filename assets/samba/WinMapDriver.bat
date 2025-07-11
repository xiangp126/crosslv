@echo off
echo Windows Network Drive Mapper
echo ==============================
echo Disconnecting Z: drive...
net use Z: /delete /y 2>nul
echo.
echo Mapping network drive...
net use Z: \\172.16.67.180\bugzilla /persistent:yes
if %errorlevel% equ 0 (
    echo SUCCESS: Z: drive mapping completed
) else (
    echo ERROR: Failed to map Z: drive
)
echo.
pause