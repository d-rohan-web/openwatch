import subprocess
import sys

DIFF = """+++ b/apps/collector/feeds/x.py
@@ -0,0 +1,4 @@
+r = await ctx.get(url, verify=False)
+headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0)"}
+print("debug")
+key = "x"
+++ b/apps/frontend/src/a.ts
@@ -1,0 +5,1 @@
+console.log(x)
"""


def run(diff: str):
    p = subprocess.run([sys.executable, "scripts/ci/review_checks.py"], input=diff, capture_output=True, text=True)
    return p.returncode, p.stdout


def test_blocks_tls_off_and_ua_spoof_warns_on_debug():
    code, out = run(DIFF)
    assert code == 1
    assert "title=tls-off" in out and "line=1" in out and "title=ua-spoof" in out
    assert "::warning file=apps/collector/feeds/x.py,line=3,title=debug-print" in out
    assert "::warning file=apps/frontend/src/a.ts,line=5,title=console-log" in out


def test_clean_diff_passes():
    code, _ = run("+++ b/apps/api/main.py\n@@ -1,0 +1,1 @@\n+x = 1\n")
    assert code == 0
