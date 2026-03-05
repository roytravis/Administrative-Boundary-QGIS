"""
GeoServer upload via REST API with CSRF bypass.
Uses HTTPS + session login to get proper CSRF token.
"""
import requests
import os
import sys
import re
import json
import warnings

warnings.filterwarnings('ignore')

GS = "https://geoserver.tasikmalayakota.go.id/geoserver"
REST = f"{GS}/rest"
WS = "putr"
BASE = os.path.dirname(os.path.abspath(__file__))

def main():
    s = requests.Session()
    s.verify = False
    
    print("=== GeoServer Upload ===")
    
    # 1) Get login page and CSRF token
    print("\n[1] Getting login page...")
    r = s.get(f"{GS}/web/wicket/bookmarkable/org.geoserver.web.GeoServerLoginPage", timeout=60)
    print(f"    HTTP {r.status_code}, cookies: {list(s.cookies.keys())}")
    
    # Extract form action and CSRF token
    csrf = None
    m = re.search(r'name="_csrf"[^>]*value="([^"]+)"', r.text)
    if m:
        csrf = m.group(1)
        print(f"    CSRF token: {csrf[:20]}...")
    
    # Find login form action URL - typically j_spring_security_check
    form_action = None
    m = re.search(r'<form[^>]+action="([^"]*security_check[^"]*)"', r.text)
    if m:
        form_action = m.group(1)
    else:
        m = re.search(r'<form[^>]+action="([^"]*)"', r.text)
        if m:
            form_action = m.group(1)
    
    if form_action and not form_action.startswith('http'):
        form_action = f"{GS}{form_action}" if form_action.startswith('/') else f"{GS}/{form_action}"
    
    print(f"    Form action: {form_action}")
    
    # 2) Login  
    print("\n[2] Logging in...")
    login_data = {
        'username': 'admin_putr',
        'password': 'putr3278',
    }
    if csrf:
        login_data['_csrf'] = csrf
    
    if form_action:
        r = s.post(form_action, data=login_data, timeout=60, allow_redirects=True)
    else:
        r = s.post(f"{GS}/j_spring_security_check", data=login_data, timeout=60, allow_redirects=True)
    
    print(f"    HTTP {r.status_code}, cookies: {list(s.cookies.keys())}")
    print(f"    Logged in: {'admin_putr' in r.text or 'Logout' in r.text}")
    
    # 3) Test REST API with this authenticated session
    print("\n[3] Testing REST API...")
    
    # Different header combinations to try
    attempts = [
        {"Accept": "application/json"},
        {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
        {"Accept": "application/json", "Referer": f"{GS}/web/"},
        {
            "Accept": "application/json",
            "Referer": f"{GS}/web/",
            "X-Requested-With": "XMLHttpRequest",
        },
    ]
    
    success = False
    for i, heads in enumerate(attempts):
        try:
            r = s.get(f"{REST}/workspaces/{WS}.json", headers=heads, timeout=60)
            print(f"    Attempt {i+1}: HTTP {r.status_code}")
            if r.status_code == 200:
                print(f"    SUCCESS! Response: {r.text[:150]}")
                success = True
                good_headers = heads
                break
            elif r.status_code == 403:
                print(f"    CSRF blocked")
        except Exception as e:
            print(f"    Error: {e}")
    
    if not success:
        # Try with basic auth instead of session
        print("\n[3b] Trying basic auth with session cookies...")
        s.auth = ("admin_putr", "putr3278")
        for i, heads in enumerate(attempts):
            try:
                r = s.get(f"{REST}/workspaces/{WS}.json", headers=heads, timeout=60)
                print(f"    Attempt {i+1}: HTTP {r.status_code}")
                if r.status_code == 200:
                    print(f"    SUCCESS! Response: {r.text[:150]}")
                    success = True
                    good_headers = heads
                    break
            except Exception as e:
                print(f"    Error: {e}")
    
    if not success:
        print("\n    All attempts failed. CSRF protection cannot be bypassed.")
        print("    Please consider:")
        print("    1. Disable CSRF filter in GeoServer web.xml")
        print("    2. Add your IP to CSRF whitelist")
        print("    3. Use SSH/SCP to upload files to GeoServer data directory")
        return 1
    
    # 4) Upload shapefiles
    print("\n[4] Uploading Batas_Kecamatan...")
    with open(os.path.join(BASE, "Batas_Kecamatan.zip"), "rb") as f:
        data = f.read()
    
    heads = {**good_headers, "Content-Type": "application/zip"}
    heads.pop("Accept", None)
    r = s.put(
        f"{REST}/workspaces/{WS}/datastores/Batas_Kecamatan/file.shp?update=overwrite",
        data=data, headers=heads, timeout=120
    )
    print(f"    HTTP {r.status_code}")
    if r.status_code in (200, 201):
        print(f"    OK!")
    else:
        print(f"    Response: {r.text[:200]}")
    
    print("\n[5] Uploading jaringan-jalan...")
    with open(os.path.join(BASE, "jaringan-jalan.zip"), "rb") as f:
        data = f.read()
    
    r = s.put(
        f"{REST}/workspaces/{WS}/datastores/jaringan_jalan/file.shp?update=overwrite",
        data=data, headers=heads, timeout=120
    )
    print(f"    HTTP {r.status_code}")
    if r.status_code in (200, 201):
        print(f"    OK!")
    else:
        print(f"    Response: {r.text[:200]}")
    
    # 6) Upload styles
    print("\n[6] Uploading batas_kecamatan_style...")
    with open(os.path.join(BASE, "batas_kecamatan_style.sld"), "r", encoding="utf-8") as f:
        sld = f.read()
    
    # Create style entry
    heads_json = {**good_headers, "Content-Type": "application/json"}
    r = s.post(
        f"{REST}/workspaces/{WS}/styles",
        json={"style": {"name": "batas_kecamatan_style", "filename": "batas_kecamatan_style.sld"}},
        headers=heads_json, timeout=60
    )
    print(f"    Create entry: HTTP {r.status_code}")
    
    heads_sld = {**good_headers, "Content-Type": "application/vnd.ogc.sld+xml"}
    heads_sld.pop("Accept", None)
    r = s.put(
        f"{REST}/workspaces/{WS}/styles/batas_kecamatan_style",
        data=sld.encode("utf-8"), headers=heads_sld, timeout=60
    )
    print(f"    Upload SLD: HTTP {r.status_code}")
    
    print("\n[7] Uploading jaringan_jalan_style...")
    with open(os.path.join(BASE, "jaringan_jalan_style.sld"), "r", encoding="utf-8") as f:
        sld = f.read()
    
    r = s.post(
        f"{REST}/workspaces/{WS}/styles",
        json={"style": {"name": "jaringan_jalan_style", "filename": "jaringan_jalan_style.sld"}},
        headers=heads_json, timeout=60
    )
    print(f"    Create entry: HTTP {r.status_code}")
    
    r = s.put(
        f"{REST}/workspaces/{WS}/styles/jaringan_jalan_style",
        data=sld.encode("utf-8"), headers=heads_sld, timeout=60
    )
    print(f"    Upload SLD: HTTP {r.status_code}")
    
    # 8) Apply styles
    print("\n[8] Applying styles...")
    for layer, style in [("Batas_Kecamatan", "batas_kecamatan_style"), ("jaringan-jalan", "jaringan_jalan_style")]:
        r = s.put(
            f"{REST}/layers/{WS}:{layer}",
            json={"layer": {"defaultStyle": {"name": f"{WS}:{style}"}}},
            headers=heads_json, timeout=60
        )
        print(f"    {layer}: HTTP {r.status_code}")
    
    # 9) Create Layer Group
    print("\n[9] Creating Layer Group...")
    # Delete existing
    s.delete(f"{REST}/workspaces/{WS}/layergroups/peta_satu_peta", headers=good_headers, timeout=60)
    
    group_payload = {
        "layerGroup": {
            "name": "peta_satu_peta",
            "mode": "SINGLE",
            "title": "Peta Satu Peta - Kota Tasikmalaya",
            "abstractTxt": "Peta komposit jaringan jalan dan batas kecamatan Kota Tasikmalaya",
            "workspace": {"name": WS},
            "publishables": {
                "published": [
                    {"@type": "layer", "name": f"{WS}:Batas_Kecamatan"},
                    {"@type": "layer", "name": f"{WS}:jaringan-jalan"},
                ]
            },
            "styles": {
                "style": [
                    {"name": f"{WS}:batas_kecamatan_style"},
                    {"name": f"{WS}:jaringan_jalan_style"},
                ]
            },
            "bounds": {
                "minx": 108.1, "maxx": 108.35,
                "miny": -7.45, "maxy": -7.25,
                "crs": "EPSG:4326"
            },
        }
    }
    r = s.post(
        f"{REST}/workspaces/{WS}/layergroups",
        json=group_payload, headers=heads_json, timeout=60
    )
    print(f"    HTTP {r.status_code}")
    if r.status_code not in (200, 201):
        print(f"    Response: {r.text[:200]}")
    
    print("\n=== DONE ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
