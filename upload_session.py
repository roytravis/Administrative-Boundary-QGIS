"""
Upload shapefiles to GeoServer via REST API with proper CSRF handling.
Uses a session to handle cookies and CSRF tokens.
"""
import requests
import os
import sys
import re
import warnings

warnings.filterwarnings('ignore', message='Unverified HTTPS request')

GEOSERVER_URL = "https://geoserver.tasikmalayakota.go.id/geoserver"
REST_URL = f"{GEOSERVER_URL}/rest"
AUTH = ("admin_putr", "putr3278")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    session = requests.Session()
    session.auth = AUTH
    session.verify = False
    
    # Step 1: Get initial session and cookies by visiting the web page
    print("[1] Getting session cookies...")
    try:
        r = session.get(f"{GEOSERVER_URL}/web/", timeout=30)
        print(f"    Web page: HTTP {r.status_code}")
        print(f"    Cookies: {dict(session.cookies)}")
    except Exception as e:
        print(f"    Error getting web page: {e}")
        # Try HTTP instead
        print("    Trying HTTP...")
        GEOSERVER_URL_HTTP = "http://geoserver.tasikmalayakota.go.id/geoserver"
        try:
            r = session.get(f"{GEOSERVER_URL_HTTP}/web/", timeout=30)
            print(f"    Web page (HTTP): HTTP {r.status_code}")
            print(f"    Cookies: {dict(session.cookies)}")
        except Exception as e2:
            print(f"    HTTP also failed: {e2}")
            return 1
    
    # Look for CSRF token in cookies or page content
    csrf_token = None
    for cookie_name in ['XSRF-TOKEN', 'csrf-token', 'CSRF-TOKEN']:
        if cookie_name in session.cookies:
            csrf_token = session.cookies[cookie_name]
            print(f"    Found CSRF token in cookie '{cookie_name}': {csrf_token}")
            break
    
    # Also look in page content for hidden form field
    if not csrf_token and r.status_code == 200:
        match = re.search(r'name="csrf[_-]?token"[^>]*value="([^"]+)"', r.text, re.IGNORECASE)
        if match:
            csrf_token = match.group(1)
            print(f"    Found CSRF token in page: {csrf_token}")
        
        # Also check for GeoServer-specific CSRF parameter
        match = re.search(r'name="_csrf"[^>]*value="([^"]+)"', r.text, re.IGNORECASE)
        if match:
            csrf_token = match.group(1)
            print(f"    Found _csrf token in page: {csrf_token}")
    
    # Headers for REST API
    headers = {
        'X-Requested-With': 'XMLHttpRequest',
    }
    if csrf_token:
        headers['X-CSRF-TOKEN'] = csrf_token
        headers['X-XSRF-TOKEN'] = csrf_token
    
    # Step 2: Try workspace check with session
    print("\n[2] Checking workspace 'putr'...")
    try:
        r = session.get(f"{REST_URL}/workspaces/putr.json", headers=headers, timeout=30)
        print(f"    Status: HTTP {r.status_code}")
        if r.status_code == 200:
            print(f"    Response: {r.text[:200]}")
        else:
            print(f"    Response: {r.text[:300]}")
    except Exception as e:
        print(f"    Error: {e}")
        return 1
    
    if r.status_code != 200:
        print("\n    Still getting 403. Trying different approach...")
        
        # Try POSTing login form
        print("\n[2b] Trying form-based login...")
        login_data = {
            'username': 'admin_putr',
            'password': 'putr3278',
        }
        
        # Find the login form URL
        login_r = session.get(f"{GEOSERVER_URL}/web/wicket/bookmarkable/org.geoserver.web.GeoServerLoginPage", timeout=30)
        print(f"    Login page: HTTP {login_r.status_code}")
        
        # Check for JSESSIONID and _csrf in form
        if '_csrf' in login_r.text:
            csrf_match = re.search(r'name="_csrf"[^>]*value="([^"]+)"', login_r.text)
            if csrf_match:
                csrf_token = csrf_match.group(1)
                login_data['_csrf'] = csrf_token
                print(f"    Login CSRF token: {csrf_token}")
        
        # Find login form action
        form_match = re.search(r'<form[^>]*action="([^"]*)"[^>]*>', login_r.text, re.IGNORECASE)
        if form_match:
            login_action = form_match.group(1)
            if not login_action.startswith('http'):
                login_action = f"{GEOSERVER_URL}{login_action}"
            print(f"    Login action: {login_action}")
            
            login_result = session.post(login_action, data=login_data, timeout=30, allow_redirects=True)
            print(f"    Login result: HTTP {login_result.status_code}")
            print(f"    Cookies after login: {dict(session.cookies)}")
        
        # Retry workspace check
        print("\n[2c] Retrying workspace check after login...")
        r = session.get(f"{REST_URL}/workspaces/putr.json", headers=headers, timeout=30)
        print(f"    Status: HTTP {r.status_code}")
        print(f"    Response: {r.text[:300]}")
    
    if r.status_code == 200:
        print("\n    SUCCESS! REST API is accessible.")
        
        # Step 3: Upload Batas_Kecamatan
        print("\n[3] Uploading Batas_Kecamatan shapefile...")
        zip_path = os.path.join(BASE_DIR, "Batas_Kecamatan.zip")
        with open(zip_path, 'rb') as f:
            zip_data = f.read()
        
        r = session.put(
            f"{REST_URL}/workspaces/putr/datastores/Batas_Kecamatan/file.shp?update=overwrite",
            data=zip_data,
            headers={**headers, 'Content-Type': 'application/zip'},
            timeout=120,
        )
        print(f"    Upload: HTTP {r.status_code} - {r.text[:200]}")
        
        # Step 4: Upload jaringan-jalan
        print("\n[4] Uploading jaringan-jalan shapefile...")
        zip_path = os.path.join(BASE_DIR, "jaringan-jalan.zip")
        with open(zip_path, 'rb') as f:
            zip_data = f.read()
        
        r = session.put(
            f"{REST_URL}/workspaces/putr/datastores/jaringan_jalan/file.shp?update=overwrite",
            data=zip_data,
            headers={**headers, 'Content-Type': 'application/zip'},
            timeout=120,
        )
        print(f"    Upload: HTTP {r.status_code} - {r.text[:200]}")
    else:
        print(f"\n    REST API still blocked. Cannot proceed with upload.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
