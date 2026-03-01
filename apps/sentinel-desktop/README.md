# Sentinel Desktop

## Run

```powershell
cd apps/sentinel-desktop
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m sentinel.main
```

## Overlay Journey Harness

From repo root:

```powershell
.\scripts\run-overlay-journey.ps1
```

This starts an isolated mock bridge + sentinel test mode and writes journey artifacts under `artifacts/overlay-journey/`.
