# CI helper script for building a Windows .exe using PyInstaller
# This script is intended to run on a windows-latest GitHub Actions runner.

# Fail on any error
$ErrorActionPreference = 'Stop'

# Ensure working directory is repository root
Set-Location $PSScriptRoot\..\

python -m pip install --upgrade pip
if (Test-Path requirements.txt) {
    pip install -r requirements.txt
}

# Install PyInstaller at a pinned, known-good version
pip install pyinstaller==5.13.0

# Clean up previous builds
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
if (Test-Path build) { Remove-Item -Recurse -Force build }

# PyInstaller options:
# - onefile: single EXE
# - windowed: suppress console (if GUI-only). If you want console, remove --windowed
# - add-data: include additional files (DB, templates) if needed

# Example includes - adjust if your app needs the DB or other files packaged
$adds = @()
# If you want to include requirements or data files, add entries like:
# $adds += 'multi-agent_mcp_context_manager.db;.'

$add_flags = ''
foreach ($a in $adds) { $add_flags += " --add-data `"$a`"" }

# Use the main GUI entrypoint
# If a spec file exists, use it. Otherwise, build from the entry script.
$spec = 'mcp_gui.spec'
if (Test-Path $spec) {
    Write-Host "Using spec file: $spec"
    pyinstaller --clean $spec
} else {
    $entry = 'main.py'
    # Build
    pyinstaller --clean --onefile --windowed $add_flags $entry
}

# On success, list dist contents
Get-ChildItem -Path dist -Recurse | Format-Table -AutoSize

Write-Host 'Build complete, artifacts are in dist\\'