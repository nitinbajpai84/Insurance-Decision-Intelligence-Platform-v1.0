@echo off
rem Note: kept on one line because cmd.exe mis-parses a "<" redirect after "^" line continuations.
"D:\Projects\CLD Projects\duckdb_cli-windows-amd64\duckdb.exe" "D:\Projects\CLD Projects\Insurance PoC - V2.0\database\insurance_v2.duckdb" < "D:\Projects\CLD Projects\Insurance PoC - V2.0\database\schema.sql"
if %ERRORLEVEL% NEQ 0 (
  echo Schema creation FAILED with exit code %ERRORLEVEL%
  exit /b %ERRORLEVEL%
)
echo Schema created successfully
