@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 nao foi localizado.
    echo Instale pelo endereco https://www.python.org/downloads/ e marque Add Python to PATH.
    pause
    exit /b 1
  )
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -m pip install -r requirements.txt
) else (
  python -m pip install -r requirements.txt
)
if errorlevel 1 (
  echo Nao foi possivel instalar os componentes de criptografia e PDF.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\SIVS.lnk'); $s.TargetPath='%~dp0start.bat'; $s.WorkingDirectory='%~dp0'; $s.Description='SIVS - Gestao Integrada'; $s.Save()"
echo.
echo SIVS instalado. Um atalho foi criado na Area de Trabalho.
echo O banco de dados permanecera nesta pasta.
echo.
start "" "%~dp0start.bat"
pause
