"""
Upload shapefiles and SLD styles to GeoServer REST API.
Creates datastores, publishes layers with styling, and creates a Layer Group.

Target: http://geoserver.tasikmalayakota.go.id/geoserver
Workspace: putr
"""

import requests
import zipfile
import os
import io
import re
import json
import sys
import xml.etree.ElementTree as ET

# ─── Configuration ───────────────────────────────────────────────────────────
GEOSERVER_URL = "http://geoserver.tasikmalayakota.go.id/geoserver"
REST_URL = f"{GEOSERVER_URL}/rest"
AUTH = ("admin_putr", "putr3278")

WORKSPACE = "putr"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JALAN_DIR = os.path.join(BASE_DIR, "Jaringan Jalan")
BATAS_DIR = os.path.join(BASE_DIR, "Batas Administrasi")

# Layer definitions
LAYERS = [
    {
        "name": "Batas_Kecamatan",
        "store_name": "Batas_Kecamatan",
        "shapefile_dir": BATAS_DIR,
        "shapefile_base": "Batas_Kecamatan",
        "sld_file": os.path.join(BATAS_DIR, "batas_administrasi.sld"),
        "style_name": "batas_kecamatan_style",
        "native_crs": "EPSG:32749",
    },
    {
        "name": "jaringan-jalan",
        "store_name": "jaringan_jalan",
        "shapefile_dir": JALAN_DIR,
        "shapefile_base": "jaringan-jalan",
        "sld_file": os.path.join(JALAN_DIR, "jaringan_jalan.sld"),
        "style_name": "jaringan_jalan_style",
        "native_crs": "EPSG:32749",
    },
]

LAYER_GROUP_NAME = "peta_satu_peta"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[INFO] {msg}")

def log_ok(msg):
    print(f"  ✓ {msg}")

def log_err(msg):
    print(f"  ✗ {msg}", file=sys.stderr)

def check_response(resp, action, acceptable=(200, 201)):
    if resp.status_code in acceptable:
        log_ok(f"{action} — HTTP {resp.status_code}")
        return True
    else:
        log_err(f"{action} — HTTP {resp.status_code}")
        log_err(f"  Response: {resp.text[:500]}")
        return False


def create_shapefile_zip(shapefile_dir, base_name):
    """Create an in-memory ZIP of shapefile components."""
    extensions = [".shp", ".shx", ".dbf", ".prj", ".cpg"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext in extensions:
            filepath = os.path.join(shapefile_dir, base_name + ext)
            if os.path.exists(filepath):
                zf.write(filepath, base_name + ext)
                log_ok(f"Added {base_name}{ext} to ZIP")
            else:
                if ext in (".shp", ".shx", ".dbf"):
                    log_err(f"Required file missing: {base_name}{ext}")
                    return None
    buf.seek(0)
    return buf.read()


def convert_sld_110_to_100(sld_content):
    """
    Convert SLD 1.1.0 / SE 1.0 format to SLD 1.0.0 format for GeoServer compatibility.
    This handles the namespace differences between the two versions.
    """
    text = sld_content

    # Replace SLD 1.1.0 schema location with 1.0.0
    text = text.replace(
        'version="1.1.0"', 'version="1.0.0"'
    )
    text = text.replace(
        "http://schemas.opengis.net/sld/1.1.0/StyledLayerDescriptor.xsd",
        "http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd",
    )

    # Remove se: namespace prefix from element names
    # Replace <se:ElementName> with <ElementName> and </se:ElementName> with </ElementName>
    text = re.sub(r"<se:", "<", text)
    text = re.sub(r"</se:", "</", text)

    # Remove the se namespace declaration
    text = re.sub(r'\s*xmlns:se="http://www.opengis.net/se"', "", text)

    # Replace SvgParameter with CssParameter (SLD 1.0.0 naming)
    text = text.replace("SvgParameter", "CssParameter")

    # Fix ogc:Literal wrapping around Gap value — SLD 1.0.0 Gap should be a plain element
    # <Gap><ogc:Literal>11</ogc:Literal></Gap> → <Gap>11</Gap>
    text = re.sub(
        r"<Gap>\s*<ogc:Literal>([^<]+)</ogc:Literal>\s*</Gap>",
        r"<Gap>\1</Gap>",
        text,
    )

    # Ensure GeneralizeLine element is removed (not supported in SLD 1.0.0)
    text = re.sub(r"\s*<GeneralizeLine>[^<]*</GeneralizeLine>", "", text)

    return text


# ─── Main Operations ─────────────────────────────────────────────────────────

def ensure_workspace():
    """Verify the workspace exists."""
    log(f"Checking workspace '{WORKSPACE}'...")
    resp = requests.get(
        f"{REST_URL}/workspaces/{WORKSPACE}.json",
        auth=AUTH,
    )
    if resp.status_code == 200:
        log_ok(f"Workspace '{WORKSPACE}' exists")
        return True
    else:
        log(f"Creating workspace '{WORKSPACE}'...")
        resp = requests.post(
            f"{REST_URL}/workspaces",
            auth=AUTH,
            json={"workspace": {"name": WORKSPACE}},
            headers={"Content-Type": "application/json"},
        )
        return check_response(resp, f"Create workspace '{WORKSPACE}'", (201,))


def upload_shapefile(layer_cfg):
    """Upload shapefile ZIP as a new datastore and auto-publish."""
    store = layer_cfg["store_name"]
    log(f"Uploading shapefile for store '{store}'...")

    zip_data = create_shapefile_zip(layer_cfg["shapefile_dir"], layer_cfg["shapefile_base"])
    if zip_data is None:
        return False

    # Upload ZIP to create datastore + auto-publish layer
    url = (
        f"{REST_URL}/workspaces/{WORKSPACE}/datastores/{store}/file.shp"
        f"?update=overwrite"
    )
    resp = requests.put(
        url,
        auth=AUTH,
        data=zip_data,
        headers={"Content-Type": "application/zip"},
    )
    return check_response(resp, f"Upload shapefile '{store}'", (200, 201, 202))


def upload_style(layer_cfg):
    """Upload SLD style to GeoServer."""
    style_name = layer_cfg["style_name"]
    sld_file = layer_cfg["sld_file"]
    log(f"Uploading style '{style_name}' from {os.path.basename(sld_file)}...")

    with open(sld_file, "r", encoding="utf-8") as f:
        sld_content = f.read()

    # Convert SLD 1.1.0 → 1.0.0
    sld_100 = convert_sld_110_to_100(sld_content)
    log_ok("Converted SLD 1.1.0 → 1.0.0")

    # First, try to create the style entry
    resp = requests.post(
        f"{REST_URL}/workspaces/{WORKSPACE}/styles",
        auth=AUTH,
        json={"style": {"name": style_name, "filename": f"{style_name}.sld"}},
        headers={"Content-Type": "application/json"},
    )
    if resp.status_code == 500 and "already exists" in resp.text:
        log_ok(f"Style '{style_name}' already exists, will update")
    elif resp.status_code not in (200, 201):
        # Try without workspace scope (global styles)
        resp = requests.post(
            f"{REST_URL}/styles",
            auth=AUTH,
            json={"style": {"name": style_name, "filename": f"{style_name}.sld"}},
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code == 500 and "already exists" in resp.text:
            log_ok(f"Style '{style_name}' already exists globally, will update")
        elif resp.status_code not in (200, 201):
            log_err(f"Failed to create style entry: HTTP {resp.status_code} - {resp.text[:300]}")

    # Upload the SLD body to the workspace-scoped style
    resp = requests.put(
        f"{REST_URL}/workspaces/{WORKSPACE}/styles/{style_name}",
        auth=AUTH,
        data=sld_100.encode("utf-8"),
        headers={"Content-Type": "application/vnd.ogc.sld+xml"},
    )
    ok = check_response(resp, f"Upload SLD body for '{style_name}'")
    if not ok:
        # Fallback: try global style
        resp = requests.put(
            f"{REST_URL}/styles/{style_name}",
            auth=AUTH,
            data=sld_100.encode("utf-8"),
            headers={"Content-Type": "application/vnd.ogc.sld+xml"},
        )
        ok = check_response(resp, f"Upload SLD body globally for '{style_name}'")
    return ok


def apply_style_to_layer(layer_cfg):
    """Set the uploaded SLD as the default style for the layer."""
    layer_name = layer_cfg["name"]
    style_name = layer_cfg["style_name"]
    log(f"Applying style '{style_name}' to layer '{layer_name}'...")

    # Try workspace-qualified style reference first
    payload = {
        "layer": {
            "defaultStyle": {
                "name": f"{WORKSPACE}:{style_name}",
            }
        }
    }
    resp = requests.put(
        f"{REST_URL}/layers/{WORKSPACE}:{layer_name}",
        auth=AUTH,
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    if resp.status_code not in (200, 201):
        # Retry with non-qualified style name
        payload["layer"]["defaultStyle"]["name"] = style_name
        resp = requests.put(
            f"{REST_URL}/layers/{WORKSPACE}:{layer_name}",
            auth=AUTH,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
    return check_response(resp, f"Apply style to '{layer_name}'")


def get_layer_bbox(layer_cfg):
    """Get native bounding box from the published layer."""
    layer_name = layer_cfg["name"]
    store_name = layer_cfg["store_name"]
    resp = requests.get(
        f"{REST_URL}/workspaces/{WORKSPACE}/datastores/{store_name}/featuretypes/{layer_name}.json",
        auth=AUTH,
    )
    if resp.status_code == 200:
        ft = resp.json().get("featureType", {})
        return ft.get("nativeBoundingBox", {}), ft.get("latLonBoundingBox", {})
    return None, None


def create_layer_group():
    """Create a Layer Group combining both layers."""
    log(f"Creating Layer Group '{LAYER_GROUP_NAME}'...")

    # Calculate merged bounds from both layers
    all_native_bboxes = []
    all_latlon_bboxes = []
    for layer_cfg in LAYERS:
        native_bb, latlon_bb = get_layer_bbox(layer_cfg)
        if native_bb:
            all_native_bboxes.append(native_bb)
        if latlon_bb:
            all_latlon_bboxes.append(latlon_bb)

    # Merge bounding boxes
    if all_latlon_bboxes:
        bounds = {
            "minx": min(b.get("minx", 0) for b in all_latlon_bboxes),
            "maxx": max(b.get("maxx", 0) for b in all_latlon_bboxes),
            "miny": min(b.get("miny", 0) for b in all_latlon_bboxes),
            "maxy": max(b.get("maxy", 0) for b in all_latlon_bboxes),
            "crs": "EPSG:4326",
        }
    else:
        # Fallback: approximate Tasikmalaya bounds
        bounds = {
            "minx": 108.1,
            "maxx": 108.3,
            "miny": -7.4,
            "maxy": -7.2,
            "crs": "EPSG:4326",
        }

    log_ok(f"Merged bounds: {bounds}")

    payload = {
        "layerGroup": {
            "name": LAYER_GROUP_NAME,
            "mode": "SINGLE",
            "title": "Peta Satu Peta - Kota Tasikmalaya",
            "abstractTxt": "Peta komposit jaringan jalan dan batas kecamatan Kota Tasikmalaya",
            "workspace": {"name": WORKSPACE},
            "publishables": {
                "published": [
                    {
                        "@type": "layer",
                        "name": f"{WORKSPACE}:Batas_Kecamatan",
                    },
                    {
                        "@type": "layer",
                        "name": f"{WORKSPACE}:jaringan-jalan",
                    },
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

    # Try to delete existing layer group first
    requests.delete(
        f"{REST_URL}/workspaces/{WORKSPACE}/layergroups/{LAYER_GROUP_NAME}",
        auth=AUTH,
    )

    resp = requests.post(
        f"{REST_URL}/workspaces/{WORKSPACE}/layergroups",
        auth=AUTH,
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    return check_response(resp, f"Create Layer Group '{LAYER_GROUP_NAME}'", (200, 201))


def verify_wms():
    """Quick verification via WMS GetCapabilities."""
    log("Verifying WMS capabilities...")
    resp = requests.get(
        f"{GEOSERVER_URL}/{WORKSPACE}/wms?service=WMS&version=1.1.1&request=GetCapabilities",
        auth=AUTH,
    )
    if resp.status_code == 200:
        content = resp.text
        checks = [
            ("Batas_Kecamatan" in content, "Batas_Kecamatan listed in WMS"),
            ("jaringan-jalan" in content or "jaringan_jalan" in content, "jaringan-jalan listed in WMS"),
            (LAYER_GROUP_NAME in content, f"{LAYER_GROUP_NAME} listed in WMS"),
        ]
        for ok, desc in checks:
            if ok:
                log_ok(desc)
            else:
                log_err(f"NOT FOUND: {desc}")
        return all(c[0] for c in checks)
    else:
        log_err(f"WMS GetCapabilities failed: HTTP {resp.status_code}")
        return False


def verify_wfs():
    """Quick verification via WFS GetCapabilities."""
    log("Verifying WFS capabilities...")
    resp = requests.get(
        f"{GEOSERVER_URL}/{WORKSPACE}/wfs?service=WFS&version=1.0.0&request=GetCapabilities",
        auth=AUTH,
    )
    if resp.status_code == 200:
        content = resp.text
        if "Batas_Kecamatan" in content and ("jaringan-jalan" in content or "jaringan_jalan" in content):
            log_ok("Both layers available via WFS")
            return True
        else:
            log_err("Not all layers found in WFS capabilities")
            return False
    else:
        log_err(f"WFS GetCapabilities failed: HTTP {resp.status_code}")
        return False


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("GeoServer Upload & Publishing Script")
    print(f"Target: {GEOSERVER_URL}")
    print(f"Workspace: {WORKSPACE}")
    print("=" * 60)
    print()

    errors = []

    # Step 1: Verify workspace
    if not ensure_workspace():
        errors.append("Workspace creation failed")
        print("\n[FATAL] Cannot proceed without workspace. Aborting.")
        return 1

    # Step 2: Upload shapefiles
    print()
    for layer_cfg in LAYERS:
        if not upload_shapefile(layer_cfg):
            errors.append(f"Shapefile upload failed: {layer_cfg['name']}")
        print()

    # Step 3: Upload SLD styles
    for layer_cfg in LAYERS:
        if not upload_style(layer_cfg):
            errors.append(f"Style upload failed: {layer_cfg['style_name']}")
        print()

    # Step 4: Apply styles to layers
    for layer_cfg in LAYERS:
        if not apply_style_to_layer(layer_cfg):
            errors.append(f"Style apply failed: {layer_cfg['name']}")
        print()

    # Step 5: Create Layer Group
    if not create_layer_group():
        errors.append("Layer Group creation failed")
    print()

    # Step 6: Verify
    print("-" * 60)
    print("VERIFICATION")
    print("-" * 60)
    wms_ok = verify_wms()
    print()
    wfs_ok = verify_wfs()
    print()

    # Summary
    print("=" * 60)
    if not errors:
        print("ALL OPERATIONS COMPLETED SUCCESSFULLY")
        print()
        print("Published endpoints:")
        print(f"  WMS: {GEOSERVER_URL}/{WORKSPACE}/wms")
        print(f"  WFS: {GEOSERVER_URL}/{WORKSPACE}/wfs")
        print(f"  Layer Preview: {GEOSERVER_URL}/web/wicket/bookmarkable/")
        print(f"      org.geoserver.web.demo.MapPreviewPage")
        print()
        print(f"  Layer Group: {LAYER_GROUP_NAME}")
        print(f"  GetMap URL (example):")
        print(f"    {GEOSERVER_URL}/{WORKSPACE}/wms?service=WMS&version=1.1.1"
              f"&request=GetMap&layers={WORKSPACE}:{LAYER_GROUP_NAME}"
              f"&width=800&height=600&srs=EPSG:4326"
              f"&bbox=108.1,-7.4,108.3,-7.2&format=image/png")
    else:
        print(f"COMPLETED WITH {len(errors)} ERROR(S):")
        for e in errors:
            print(f"  - {e}")
    print("=" * 60)

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
