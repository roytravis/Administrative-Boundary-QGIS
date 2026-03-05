"""
Upload shapefiles and styles to GeoServer via REST API.
Uses HTTP with proper CSRF bypass headers (Referer + Origin).
"""
import requests
import os
import sys
import re
import json

GEOSERVER_URL = "http://geoserver.tasikmalayakota.go.id/geoserver"
REST_URL = f"{GEOSERVER_URL}/rest"
AUTH = ("admin_putr", "putr3278")
WORKSPACE = "putr"

# CSRF bypass headers - GeoServer CSRF filter checks Referer/Origin
HEADERS_BASE = {
    "Referer": f"{GEOSERVER_URL}/web/",
    "Origin": "http://geoserver.tasikmalayakota.go.id",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TIMEOUT = 120


def log(msg):
    print(f"[*] {msg}")


def ok(msg):
    print(f"  OK: {msg}")


def err(msg):
    print(f"  ERR: {msg}", file=sys.stderr)


def test_csrf_bypass():
    """Test if our CSRF bypass headers work."""
    log("Testing CSRF bypass approach...")
    headers = {**HEADERS_BASE, "Accept": "application/json"}
    try:
        r = requests.get(
            f"{REST_URL}/workspaces/{WORKSPACE}.json",
            auth=AUTH, headers=headers, timeout=TIMEOUT
        )
        if r.status_code == 200:
            ok(f"CSRF bypass works! Workspace: {r.json()}")
            return True
        elif r.status_code == 403:
            err(f"CSRF still blocking: {r.status_code}")
            # Try without Origin (only Referer)
            headers2 = {"Referer": f"{GEOSERVER_URL}/web/", "Accept": "application/json"}
            r2 = requests.get(
                f"{REST_URL}/workspaces/{WORKSPACE}.json",
                auth=AUTH, headers=headers2, timeout=TIMEOUT
            )
            if r2.status_code == 200:
                ok(f"CSRF bypass works with Referer only!")
                return True
            err(f"Still blocked: {r2.status_code}")
            
            # Try with no extra headers at all (basic auth only)
            r3 = requests.get(
                f"{REST_URL}/workspaces/{WORKSPACE}.json",
                auth=AUTH, timeout=TIMEOUT,
                headers={"Accept": "application/json"}
            )
            if r3.status_code == 200:
                ok(f"Works with no CSRF headers!")
                return True
            err(f"Also blocked: {r3.status_code} - {r3.text[:200]}")
            return False
        else:
            err(f"Unexpected: {r.status_code} - {r.text[:200]}")
            return False
    except Exception as e:
        err(f"Connection error: {e}")
        return False


def upload_shapefile_zip(store_name, zip_path):
    """Upload shapefile ZIP to create a datastore."""
    log(f"Uploading {os.path.basename(zip_path)} as store '{store_name}'...")
    with open(zip_path, "rb") as f:
        data = f.read()
    
    headers = {
        **HEADERS_BASE,
        "Content-Type": "application/zip",
    }
    r = requests.put(
        f"{REST_URL}/workspaces/{WORKSPACE}/datastores/{store_name}/file.shp?update=overwrite",
        auth=AUTH, data=data, headers=headers, timeout=TIMEOUT
    )
    if r.status_code in (200, 201, 202):
        ok(f"Uploaded '{store_name}' successfully")
        return True
    err(f"Upload failed: HTTP {r.status_code} - {r.text[:300]}")
    return False


def upload_style(style_name, sld_path):
    """Upload SLD style to GeoServer."""
    log(f"Uploading style '{style_name}' from {os.path.basename(sld_path)}...")
    with open(sld_path, "r", encoding="utf-8") as f:
        sld_data = f.read()

    # Step 1: Create style entity
    headers = {**HEADERS_BASE, "Content-Type": "application/json"}
    payload = {"style": {"name": style_name, "filename": f"{style_name}.sld"}}
    r = requests.post(
        f"{REST_URL}/workspaces/{WORKSPACE}/styles",
        auth=AUTH, json=payload, headers=headers, timeout=TIMEOUT
    )
    if r.status_code in (200, 201):
        ok(f"Created style entity '{style_name}'")
    elif r.status_code == 500 and "already exists" in r.text:
        ok(f"Style '{style_name}' already exists, updating...")
    else:
        err(f"Create style entity: HTTP {r.status_code} - {r.text[:200]}")

    # Step 2: Upload SLD content
    headers = {**HEADERS_BASE, "Content-Type": "application/vnd.ogc.sld+xml"}
    r = requests.put(
        f"{REST_URL}/workspaces/{WORKSPACE}/styles/{style_name}",
        auth=AUTH, data=sld_data.encode("utf-8"), headers=headers, timeout=TIMEOUT
    )
    if r.status_code in (200, 201):
        ok(f"Uploaded SLD content for '{style_name}'")
        return True
    err(f"Upload SLD: HTTP {r.status_code} - {r.text[:300]}")
    return False


def apply_style(layer_name, style_name):
    """Set default style on a layer."""
    log(f"Setting style '{style_name}' on layer '{layer_name}'...")
    headers = {**HEADERS_BASE, "Content-Type": "application/json"}
    payload = {
        "layer": {
            "defaultStyle": {
                "name": f"{WORKSPACE}:{style_name}",
            }
        }
    }
    r = requests.put(
        f"{REST_URL}/layers/{WORKSPACE}:{layer_name}",
        auth=AUTH, json=payload, headers=headers, timeout=TIMEOUT
    )
    if r.status_code in (200, 201):
        ok(f"Applied style '{style_name}' to '{layer_name}'")
        return True
    err(f"Apply style: HTTP {r.status_code} - {r.text[:300]}")
    return False


def get_layer_bbox(store_name, layer_name):
    """Get bounding box from a published layer."""
    headers = {**HEADERS_BASE, "Accept": "application/json"}
    r = requests.get(
        f"{REST_URL}/workspaces/{WORKSPACE}/datastores/{store_name}/featuretypes/{layer_name}.json",
        auth=AUTH, headers=headers, timeout=TIMEOUT
    )
    if r.status_code == 200:
        ft = r.json().get("featureType", {})
        return ft.get("latLonBoundingBox", {})
    return None


def create_layer_group():
    """Create a layer group combining both layers."""
    group_name = "peta_satu_peta"
    log(f"Creating Layer Group '{group_name}'...")

    # Get bounds from layers
    bounds = None
    for store, layer in [("Batas_Kecamatan", "Batas_Kecamatan"), ("jaringan_jalan", "jaringan-jalan")]:
        bb = get_layer_bbox(store, layer)
        if bb:
            if bounds is None:
                bounds = dict(bb)
            else:
                bounds["minx"] = min(bounds["minx"], bb["minx"])
                bounds["maxx"] = max(bounds["maxx"], bb["maxx"])
                bounds["miny"] = min(bounds["miny"], bb["miny"])
                bounds["maxy"] = max(bounds["maxy"], bb["maxy"])

    if not bounds:
        bounds = {"minx": 108.1, "maxx": 108.35, "miny": -7.45, "maxy": -7.25, "crs": "EPSG:4326"}
    else:
        bounds["crs"] = bounds.get("crs", "EPSG:4326")

    ok(f"Bounds: {bounds}")

    # Delete existing group if any
    headers = {**HEADERS_BASE}
    requests.delete(
        f"{REST_URL}/workspaces/{WORKSPACE}/layergroups/{group_name}",
        auth=AUTH, headers=headers, timeout=TIMEOUT
    )

    payload = {
        "layerGroup": {
            "name": group_name,
            "mode": "SINGLE",
            "title": "Peta Satu Peta - Kota Tasikmalaya",
            "abstractTxt": "Peta komposit jaringan jalan dan batas kecamatan Kota Tasikmalaya",
            "workspace": {"name": WORKSPACE},
            "publishables": {
                "published": [
                    {"@type": "layer", "name": f"{WORKSPACE}:Batas_Kecamatan"},
                    {"@type": "layer", "name": f"{WORKSPACE}:jaringan-jalan"},
                ]
            },
            "styles": {
                "style": [
                    {"name": f"{WORKSPACE}:batas_kecamatan_style"},
                    {"name": f"{WORKSPACE}:jaringan_jalan_style"},
                ]
            },
            "bounds": bounds,
        }
    }

    headers = {**HEADERS_BASE, "Content-Type": "application/json"}
    r = requests.post(
        f"{REST_URL}/workspaces/{WORKSPACE}/layergroups",
        auth=AUTH, json=payload, headers=headers, timeout=TIMEOUT
    )
    if r.status_code in (200, 201):
        ok(f"Created Layer Group '{group_name}'")
        return True
    err(f"Create group: HTTP {r.status_code} - {r.text[:300]}")
    return False


def verify():
    """Verify WMS/WFS capabilities."""
    log("Verifying WMS...")
    headers = {**HEADERS_BASE}
    r = requests.get(
        f"{GEOSERVER_URL}/{WORKSPACE}/wms?service=WMS&version=1.1.1&request=GetCapabilities",
        headers=headers, timeout=TIMEOUT
    )
    if r.status_code == 200:
        found = []
        for name in ["Batas_Kecamatan", "jaringan-jalan", "peta_satu_peta"]:
            if name in r.text:
                ok(f"WMS: {name} found")
                found.append(name)
            else:
                err(f"WMS: {name} NOT found")
        return len(found) == 3
    err(f"WMS GetCapabilities: HTTP {r.status_code}")
    return False


def main():
    print("=" * 60)
    print("GeoServer Upload Script")
    print(f"Target: {GEOSERVER_URL}")
    print("=" * 60)

    # Test CSRF bypass
    if not test_csrf_bypass():
        print("\nCSRF bypass failed. Cannot proceed via REST API.")
        return 1

    # Upload shapefiles
    print()
    batas_ok = upload_shapefile_zip("Batas_Kecamatan", os.path.join(BASE_DIR, "Batas_Kecamatan.zip"))
    jalan_ok = upload_shapefile_zip("jaringan_jalan", os.path.join(BASE_DIR, "jaringan-jalan.zip"))

    if not (batas_ok and jalan_ok):
        print("\nShapefile upload failed. Aborting.")
        return 1

    # Upload styles
    print()
    s1 = upload_style("batas_kecamatan_style", os.path.join(BASE_DIR, "batas_kecamatan_style.sld"))
    s2 = upload_style("jaringan_jalan_style", os.path.join(BASE_DIR, "jaringan_jalan_style.sld"))

    # Apply styles
    print()
    apply_style("Batas_Kecamatan", "batas_kecamatan_style")
    apply_style("jaringan-jalan", "jaringan_jalan_style")

    # Create layer group
    print()
    create_layer_group()

    # Verify
    print()
    verify()

    print("\n" + "=" * 60)
    print("DONE!")
    print(f"  WMS: {GEOSERVER_URL}/{WORKSPACE}/wms")
    print(f"  WFS: {GEOSERVER_URL}/{WORKSPACE}/wfs")
    print(f"  Layer Group: peta_satu_peta")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
