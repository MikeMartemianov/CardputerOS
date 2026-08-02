#!/usr/bin/env python3
"""Open YouTube login, wait 60s for manual login, then save cookies"""
import time, sys
from playwright.sync_api import sync_playwright

print("Opening YouTube login page...")
print("Please log in within 60 seconds!")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto('https://accounts.google.com/signin?continue=https://www.youtube.com')
    
    # Wait for user to log in (check every 2 seconds)
    for i in range(30):
        time.sleep(2)
        cookies = context.cookies()
        has_login = any(c['name'] == 'LOGIN_INFO' for c in cookies)
        if has_login:
            print(f"LOGIN_INFO detected after {(i+1)*2}s! Saving cookies...")
            break
        print(f"Waiting... {(i+1)*2}s / 60s")
    
    # Extra wait for full cookie set
    page.goto('https://www.youtube.com')
    time.sleep(3)
    cookies = context.cookies()
    browser.close()

count = 0
with open('server/cookies.txt', 'w') as f:
    f.write('# Netscape HTTP Cookie File\n')
    for c in cookies:
        domain = c['domain']
        if 'youtube' in domain or 'google' in domain:
            exp = int(c.get('expires', 0))
            secure = 'TRUE' if c.get('secure') else 'FALSE'
            http_only = 'TRUE' if c.get('httpOnly') else 'FALSE'
            f.write(f"{domain}\t{http_only}\t{c['path']}\t{secure}\t{exp}\t{c['name']}\t{c['value']}\n")
            count += 1

print(f"\nExported {count} cookies to server/cookies.txt")
if count > 0:
    print("Now run: git add server/cookies.txt && git commit -m 'update cookies' && git push")
else:
    print("NO cookies exported! Login might have failed.")
