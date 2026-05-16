"""Deploy latest code to VPS and restart the API service."""
import paramiko
import os

VPS = "95.111.243.97"
USER = "root"

FILES = [
    "requirements.txt",
    "bot/__init__.py", "bot/exchange.py", "bot/risk.py",
    "bot/state.py", "bot/strategy.py", "bot/trader.py",
    "api/__init__.py", "api/main.py", "api/db.py",
    "backtest/__init__.py", "backtest/data.py", "backtest/engine.py",
    "backtest/metrics.py", "backtest/validation.py", "backtest/leaderboard.py",
]

def get_password():
    path = os.path.expanduser("~/OneDrive/Desktop/Contabo_new_VPS.txt")
    with open(path) as f:
        for line in f:
            if line.startswith("VPS_PASSWORD="):
                return line.strip().split("=", 1)[1]
    raise RuntimeError("VPS_PASSWORD not found in credentials file")

def ssh(c, cmd, timeout=60):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read().decode() + e.read().decode()).strip()

def deploy():
    pwd = get_password()
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(VPS, username=USER, password=pwd, timeout=15)

    base = os.path.dirname(__file__)
    sftp = c.open_sftp()
    for f in FILES:
        local = os.path.join(base, f)
        if os.path.exists(local):
            sftp.put(local, f"/root/btc-trader/{f}")
            print(f"  uploaded: {f}")
        else:
            print(f"  MISSING: {f}")
    sftp.close()

    print(ssh(c, "systemctl restart btc-trader"))
    import time; time.sleep(4)
    status = ssh(c, "systemctl status btc-trader --no-pager | grep Active")
    print(status)
    health = ssh(c, "curl -s http://localhost:8000/health")
    print("health:", health)
    c.close()

if __name__ == "__main__":
    deploy()
