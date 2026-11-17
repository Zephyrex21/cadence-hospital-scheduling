import time, json, os
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
BIN="/tmp/mamba/envs/ff/bin"
o=Options(); o.binary_location=f"{BIN}/firefox"; o.add_argument("-headless")
d=webdriver.Firefox(options=o, service=Service(f"{BIN}/geckodriver", log_output="/tmp/gecko.log"))
d.set_window_size(1280,900)
t0=time.time(); d.get("http://127.0.0.1:4100/")
def body(): return d.find_element(By.TAG_NAME,"body").text
def wait(pred, timeout):
    end=time.time()+timeout
    while time.time()<end:
        try:
            v=pred()
            if v: return v
        except Exception: pass
        time.sleep(0.4)
    return None
banner=wait(lambda: "Waking up the server" in body() and body(), 8)
print(f"[{time.time()-t0:4.1f}s] waking banner shown:", bool(banner))
diag=wait(lambda: d.find_element(By.CSS_SELECTOR,'[data-testid="wake-diagnostics"]').text, 10)
print(f"[{time.time()-t0:4.1f}s] diagnostics line:", diag)
d.save_screenshot("/tmp/shot_waking.png")
live=wait(lambda: "Service is live" in body(), 60)
print(f"[{time.time()-t0:4.1f}s] 'Service is live' shown:", bool(live))
d.save_screenshot("/tmp/shot_live.png")
time.sleep(3.5)
print("login form visible:", wait(lambda: d.find_elements(By.CSS_SELECTOR,'input[type=email], input[name=email]'), 10) is not None)
# sign in through the real backend, via the proxy
email=d.find_element(By.CSS_SELECTOR,'input[type=email], input[name=email]'); email.clear(); email.send_keys("admin@cadence.dev")
pw=d.find_element(By.CSS_SELECTOR,'input[type=password]'); pw.clear(); pw.send_keys("cadence123")
d.find_element(By.CSS_SELECTOR,'button[type=submit]').click()
ok=wait(lambda: "Dashboard" in body() or "Emergency" in body(), 30)
print(f"[{time.time()-t0:4.1f}s] signed in & app rendered:", bool(ok), "| url:", d.current_url)
d.save_screenshot("/tmp/shot_dashboard.png")
d.quit()
