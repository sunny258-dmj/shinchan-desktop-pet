# Agent instructions

This repository is intended to be installable by an autonomous Windows-capable agent from the repository URL alone.

## Install and start

From the repository root, run exactly:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\agent-install.ps1
```

The script performs unattended environment setup, installs PySide6 when needed, writes runtime configuration, configures autostart, and launches the desktop pet. Do not ask the user to manually install dependencies unless this command reports a concrete failure.

If the repository is private, use the environment's existing GitHub authorization to clone/download `main` first. Do not request or expose personal access tokens in chat.

For diagnostics after installation:

```powershell
python .\scripts\pet-start.py --status
```

For a foreground launch when troubleshooting:

```powershell
python .\scripts\pet-start.py --foreground
```
