@echo off
REM Launches the Digital Ecosystem Platform (Streamlit) in the default browser.
cd /d "%~dp0\.."
py -m streamlit run app.py
pause
