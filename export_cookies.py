from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context()
    page = context.new_page()
    page.goto('https://www.youtube.com')
    page.wait_for_timeout(3000)
    cookies = context.cookies()
    browser.close()
    
    count = 0
    with open('E:/mikem/CardputerOS/server/cookies.txt', 'w') as f:
        f.write('# Netscape HTTP Cookie File\n')
        for c in cookies:
            domain = c['domain']
            if 'youtube' in domain or 'google' in domain:
                exp = int(c.get('expires', 0))
                secure = 'TRUE' if c.get('secure') else 'FALSE'
                f.write(domain + "\tTRUE\t" + c['path'] + "\t" + secure + "\t" + str(exp) + "\t" + c['name'] + "\t" + c['value'] + "\n")
                count += 1
    
    print(f'Exported {count} YouTube cookies')
