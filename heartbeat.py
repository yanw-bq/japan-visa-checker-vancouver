"""Daily heartbeat: confirms checker is healthy, based on last_state.json freshness."""
import os, json, subprocess, datetime

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_state.json")
title = "Japan visa checker — daily check-in"
if os.path.exists(STATE):
    d = json.load(open(STATE))
    ts = d.get("ts", "?")
    n = len(d.get("slots", []))
    age_min = int((datetime.datetime.now() - datetime.datetime.fromisoformat(ts)).total_seconds() / 60) if ts != "?" else -1
    if 0 <= age_min <= 30:
        msg = f"Running OK. Last check {age_min} min ago. Open slots: {n}."
    else:
        msg = f"WARNING: last run was {age_min} min ago (expected <=30). Open slots: {n}."
else:
    msg = "WARNING: no state file yet — task may not have run."

# Windows toast via XML template (BurntToast-free)
xml = f"""<toast><visual><binding template="ToastText02"><text id="1">{title}</text><text id="2">{msg}</text></binding></visual></toast>"""
ps = (f'$x=New-Object Windows.Data.Xml.Dom.XmlDocument;'
      f'$x.LoadXml(@"\n{xml}\n"@);'
      f'$n=[Windows.UI.Notifications.ToastNotification]::new($x);'
      f'[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JapanVisa").Show($n)')
subprocess.run(["powershell", "-NoProfile", "-Command",
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null; " +
                "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null; " +
                ps], timeout=10)
print(msg)
