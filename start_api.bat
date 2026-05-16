@echo off
cd /d C:\Users\User\btc-trader
echo Starting BTC Trader API...
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
pause
