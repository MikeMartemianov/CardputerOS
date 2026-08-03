"""
Auto-deploy trigger for Render.
Posts to the Render Deploy Hook URL, which makes Render pull the
latest commit from GitHub and redeploy automatically.

Usage:
    python deploy.py

Setup (one time):
1. Render Dashboard -> your service -> Settings -> Deploy Hook
2. Copy the Deploy Hook URL (https://api.render.com/deploy/srv-...?key=...)
3. Save it into deploy_hook.txt (same folder as this script)
"""
import sys
import json
import urllib.request

HOOK_FILE = 'deploy_hook.txt'


def load_hook_url():
    try:
        with open(HOOK_FILE, 'r', encoding='utf-8') as f:
            url = f.read().strip()
    except FileNotFoundError:
        print(f"[DEPLOY] ERROR: {HOOK_FILE} not found.")
        print("  1. Open Render Dashboard -> service -> Settings -> Deploy Hook")
        print(f"  2. Copy the hook URL and save it into {HOOK_FILE}")
        sys.exit(1)
    if not url.startswith('https://api.render.com/deploy/'):
        print(f"[DEPLOY] ERROR: URL in {HOOK_FILE} looks wrong: {url[:60]}")
        sys.exit(1)
    return url


def main():
    hook_url = load_hook_url()
    print("[DEPLOY] Triggering Render deploy hook...")
    try:
        req = urllib.request.Request(hook_url, method='POST')
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            print(f"[DEPLOY] HTTP {resp.status}")
            try:
                data = json.loads(body)
                deploy_id = data.get('deployId', '?')
                print(f"[DEPLOY] SUCCESS! Deploy ID: {deploy_id}")
            except json.JSONDecodeError:
                print(f"[DEPLOY] Response: {body[:300]}")
    except Exception as e:
        print(f"[DEPLOY] FAILED: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
