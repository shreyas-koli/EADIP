import urllib.request, re
try:
    req = urllib.request.Request('https://eadip.onrender.com/register', headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        js_files = re.findall(r'src="([^"]+\.js)"', html)
        
        found = False
        for js in js_files:
            js_url = 'https://eadip.onrender.com' + (js if js.startswith('/') else '/' + js)
            try:
                js_req = urllib.request.Request(js_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(js_req) as js_res:
                    js_content = js_res.read().decode('utf-8')
                    if 'truncate manually' in js_content:
                        print(f'Found string in {js}!')
                        found = True
            except Exception as e:
                pass
        if not found:
            print('String not found in JS bundles.')
except Exception as e:
    print('Failed:', e)
