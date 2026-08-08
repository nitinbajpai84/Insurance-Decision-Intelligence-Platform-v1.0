@echo off
REM Anchor to this script's directory so relative paths resolve correctly.
cd /d "%~dp0"

echo === Insurance PoC V2.0 Setup ===

echo [1/6] Creating Python virtual environment...
python -m venv venv
call venv\Scripts\activate

echo [2/6] Installing Python dependencies...
python -m pip install --upgrade pip
pip install -r embeddings\requirements.txt

echo [3/6] Creating DuckDB schema...
"D:\Projects\CLD Projects\duckdb_cli-windows-amd64\duckdb.exe" "database\insurance_v2.duckdb" < "database\schema.sql"

echo [4/6] Seeding synthetic data...
python database\seed_data.py

echo [5/6] Setting up LanceDB vector store...
python embeddings\lance_setup.py

echo [6/6] Running embedding pipeline...
python embeddings\embed_pipeline.py

echo.
echo === V2.0 Setup Complete ===
echo Run start_v2.bat to launch the application
pause
