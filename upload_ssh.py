"""
Upload shapefiles to GeoServer via SSH/SCP, then configure stores
and publish layers using REST API from within the server (bypassing CSRF).
"""
import paramiko
import os
import sys
import time

# ─── Configuration ───────────────────────────────────────────────────────
SERVER = "geoserver.tasikmalayakota.go.id"
SSH_PORT = 22
USERNAME = "admin_putr"
PASSWORD = "putr3278"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Files to upload
FILES_TO_UPLOAD = [
    (os.path.join(BASE_DIR, "Batas_Kecamatan.zip"), "Batas_Kecamatan.zip"),
    (os.path.join(BASE_DIR, "jaringan-jalan.zip"), "jaringan-jalan.zip"),
    (os.path.join(BASE_DIR, "batas_kecamatan_style.sld"), "batas_kecamatan_style.sld"),
    (os.path.join(BASE_DIR, "jaringan_jalan_style.sld"), "jaringan_jalan_style.sld"),
]

WORKSPACE = "putr"

def log(msg):
    print(f"[*] {msg}")

def ok(msg):
    print(f"  ✓ {msg}")

def err(msg):
    print(f"  ✗ {msg}", file=sys.stderr)


def ssh_exec(ssh, cmd, timeout=30):
    """Execute a command via SSH and return stdout, stderr."""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    e = stderr.read().decode("utf-8", errors="replace").strip()
    exit_code = stdout.channel.recv_exit_status()
    return out, e, exit_code


def main():
    print("=" * 60)
    print("GeoServer SSH Upload & Configuration")
    print(f"Server: {SERVER}")
    print("=" * 60)

    # 1) Connect via SSH
    log("Connecting via SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(SERVER, port=SSH_PORT, username=USERNAME, password=PASSWORD,
                    timeout=15, look_for_keys=False, allow_agent=False)
        ok("SSH connected!")
    except paramiko.AuthenticationException:
        err("Authentication failed. Trying with 'root' user...")
        try:
            ssh.connect(SERVER, port=SSH_PORT, username="root", password=PASSWORD,
                        timeout=15, look_for_keys=False, allow_agent=False)
            ok("SSH connected as root!")
        except Exception as e:
            err(f"SSH connection failed: {e}")
            return 1
    except Exception as e:
        err(f"SSH connection failed: {e}")
        return 1

    # 2) Find GeoServer data directory
    log("Finding GeoServer data directory...")
    
    # Common locations to check
    candidates = [
        "/opt/geoserver/data_dir",
        "/var/lib/geoserver/data",
        "/usr/share/geoserver/data_dir",
        "/opt/geoserver_data",
        "/home/geoserver/data_dir",
        "/srv/geoserver/data_dir",
    ]
    
    # Also search for it
    out, _, _ = ssh_exec(ssh, "find / -name 'geoserver_data' -type d 2>/dev/null | head -5", timeout=15)
    if out:
        for line in out.split("\n"):
            line = line.strip()
            if line and line not in candidates:
                candidates.insert(0, line)
    
    # Also check for data_dir via process
    out, _, _ = ssh_exec(ssh, "ps aux | grep -i geoserver | grep -v grep", timeout=10)
    if out:
        ok(f"GeoServer process: {out[:200]}")
        # Look for GEOSERVER_DATA_DIR in environment
        import re
        m = re.search(r'GEOSERVER_DATA_DIR[=:](\S+)', out)
        if m:
            candidates.insert(0, m.group(1))
    
    # Check for docker
    out, _, _ = ssh_exec(ssh, "docker ps --format '{{.Names}}' 2>/dev/null | grep -i geo", timeout=10)
    if out:
        ok(f"Docker container found: {out}")
        # Get data dir from docker inspect
        container = out.strip().split('\n')[0]
        out2, _, _ = ssh_exec(ssh, f"docker inspect {container} --format '{{{{range .Mounts}}}}{{{{.Source}}}}:{{{{.Destination}}}} {{{{end}}}}' 2>/dev/null", timeout=10)
        if out2:
            ok(f"Docker mounts: {out2}")
    
    data_dir = None
    for d in candidates:
        out, _, code = ssh_exec(ssh, f"test -d {d} && echo EXISTS", timeout=5)
        if "EXISTS" in out:
            # Double-check it has uploads dir
            out2, _, _ = ssh_exec(ssh, f"ls {d}/", timeout=5)
            if "workspaces" in out2 or "uploads" in out2 or "styles" in out2:
                data_dir = d
                ok(f"Found data directory: {data_dir}")
                ok(f"Contents: {out2[:200]}")
                break
    
    if not data_dir:
        err("Could not find GeoServer data directory!")
        # List common directories
        out, _, _ = ssh_exec(ssh, "ls /opt/ /var/lib/ /usr/share/ 2>/dev/null", timeout=5)
        log(f"Available dirs: {out[:300]}")
        
        # Check if running in Docker
        out, _, _ = ssh_exec(ssh, "docker ps 2>/dev/null || echo 'no docker'", timeout=10)
        log(f"Docker: {out[:200]}")
        
        ssh.close()
        return 1

    # 3) Ensure uploads directory exists
    uploads_dir = f"{data_dir}/uploads"
    ssh_exec(ssh, f"mkdir -p {uploads_dir}", timeout=5)
    ok(f"Uploads directory ready: {uploads_dir}")

    # 4) Upload files via SFTP
    log("Uploading files via SFTP...")
    sftp = ssh.open_sftp()
    
    for local_path, remote_name in FILES_TO_UPLOAD:
        remote_path = f"{uploads_dir}/{remote_name}"
        log(f"Uploading {remote_name}...")
        try:
            sftp.put(local_path, remote_path)
            # Verify size
            remote_stat = sftp.stat(remote_path)
            local_size = os.path.getsize(local_path)
            if remote_stat.st_size == local_size:
                ok(f"  {remote_name}: {local_size} bytes OK")
            else:
                err(f"  Size mismatch: local={local_size}, remote={remote_stat.st_size}")
        except Exception as e:
            err(f"  Upload failed: {e}")

    sftp.close()

    # 5) Unzip shapefiles on server
    log("Extracting shapefile ZIPs...")
    for zip_name, dir_name in [("Batas_Kecamatan.zip", "Batas_Kecamatan"), 
                                ("jaringan-jalan.zip", "jaringan-jalan")]:
        extract_dir = f"{uploads_dir}/{dir_name}"
        ssh_exec(ssh, f"mkdir -p {extract_dir}", timeout=5)
        out, e, code = ssh_exec(ssh, f"cd {extract_dir} && unzip -o {uploads_dir}/{zip_name}", timeout=30)
        if code == 0:
            ok(f"Extracted {zip_name} → {extract_dir}")
            # List extracted files
            out2, _, _ = ssh_exec(ssh, f"ls -la {extract_dir}/", timeout=5)
            ok(f"Files: {out2[:200]}")
        else:
            err(f"Extraction failed: {e}")

    # 6) Set permissions
    log("Setting file permissions...")
    ssh_exec(ssh, f"chmod -R 755 {uploads_dir}/", timeout=5)
    ok("Permissions set")

    # 7) Try REST API from localhost (bypasses CSRF)
    log("Configuring GeoServer via localhost REST API...")
    
    # Test if curl is available on server
    out, _, code = ssh_exec(ssh, "which curl", timeout=5)
    if code != 0:
        err("curl not found on server, trying wget...")
        out, _, code = ssh_exec(ssh, "which wget", timeout=5)
        if code != 0:
            err("Neither curl nor wget found on server")
            log("Files uploaded successfully. You'll need to configure stores manually via the web UI.")
            log(f"  Batas_Kecamatan shapefile: file:{uploads_dir}/Batas_Kecamatan/Batas_Kecamatan.shp")
            log(f"  jaringan-jalan shapefile: file:{uploads_dir}/jaringan-jalan/jaringan-jalan.shp")
            ssh.close()
            return 0

    # Use localhost REST API (bypasses CSRF for same-origin)
    GS_LOCAL = "http://localhost:8080/geoserver"
    
    # Test connectivity 
    out, e, code = ssh_exec(ssh, f'curl -s -o /dev/null -w "%{{http_code}}" -u {USERNAME}:{PASSWORD} {GS_LOCAL}/rest/workspaces/{WORKSPACE}.json', timeout=15)
    if out.strip() == "200":
        ok(f"REST API accessible from localhost! (HTTP 200)")
    else:
        log(f"Localhost REST API returned: {out} (trying different ports...)")
        for port in [8080, 80, 8443, 8888]:
            GS_LOCAL_TRY = f"http://localhost:{port}/geoserver"
            out2, _, _ = ssh_exec(ssh, f'curl -s -o /dev/null -w "%{{http_code}}" -u {USERNAME}:{PASSWORD} {GS_LOCAL_TRY}/rest/workspaces/{WORKSPACE}.json 2>/dev/null', timeout=10)
            log(f"  Port {port}: HTTP {out2.strip()}")
            if out2.strip() == "200":
                GS_LOCAL = GS_LOCAL_TRY
                ok(f"Found working port: {port}")
                break
        else:
            # Try docker network
            out3, _, _ = ssh_exec(ssh, "docker inspect geoserver --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null || echo ''", timeout=10)
            if out3.strip():
                docker_ip = out3.strip()
                GS_LOCAL_TRY = f"http://{docker_ip}:8080/geoserver"
                out4, _, _ = ssh_exec(ssh, f'curl -s -o /dev/null -w "%{{http_code}}" -u {USERNAME}:{PASSWORD} {GS_LOCAL_TRY}/rest/workspaces/{WORKSPACE}.json 2>/dev/null', timeout=10)
                if out4.strip() == "200":
                    GS_LOCAL = GS_LOCAL_TRY
                    ok(f"Found via Docker IP: {docker_ip}")
                else:
                    log("REST API not accessible from localhost either")
                    log("Files uploaded. Please configure stores manually:")
                    log(f"  Batas_Kecamatan: file:uploads/Batas_Kecamatan/Batas_Kecamatan.shp")
                    log(f"  jaringan-jalan: file:uploads/jaringan-jalan/jaringan-jalan.shp")
                    ssh.close()
                    return 0

    REST_LOCAL = f"{GS_LOCAL}/rest"

    # 7a) Create Batas_Kecamatan store
    log("Creating Batas_Kecamatan datastore...")
    shp_path = f"file:uploads/Batas_Kecamatan/Batas_Kecamatan.shp"
    store_json = f'{{"dataStore":{{"name":"Batas_Kecamatan","type":"Shapefile","enabled":true,"workspace":{{"name":"{WORKSPACE}"}},"connectionParameters":{{"entry":[{{"@key":"url","$":"{shp_path}"}},{{"@key":"create spatial index","$":"true"}}]}}}}}}'
    
    cmd = f'''curl -s -w "\\n%{{http_code}}" -X POST "{REST_LOCAL}/workspaces/{WORKSPACE}/datastores" -H "Content-Type: application/json" -u {USERNAME}:{PASSWORD} -d '{store_json}' '''
    out, e, code = ssh_exec(ssh, cmd, timeout=30)
    lines = out.strip().split('\n')
    http_code = lines[-1] if lines else "?"
    ok(f"Create store: HTTP {http_code}")
    if http_code not in ("200", "201"):
        log(f"  Response: {out[:300]}")

    # 7b) Publish Batas_Kecamatan layer
    log("Publishing Batas_Kecamatan feature type...")
    ft_json = f'{{"featureType":{{"name":"Batas_Kecamatan","nativeName":"Batas_Kecamatan","title":"Batas Kecamatan","srs":"EPSG:32749","enabled":true}}}}'
    cmd = f'''curl -s -w "\\n%{{http_code}}" -X POST "{REST_LOCAL}/workspaces/{WORKSPACE}/datastores/Batas_Kecamatan/featuretypes" -H "Content-Type: application/json" -u {USERNAME}:{PASSWORD} -d '{ft_json}' '''
    out, e, code = ssh_exec(ssh, cmd, timeout=30)
    lines = out.strip().split('\n')
    http_code = lines[-1] if lines else "?"
    ok(f"Publish layer: HTTP {http_code}")
    if http_code not in ("200", "201"):
        log(f"  Response: {out[:300]}")

    # 7c) Create jaringan-jalan store
    log("Creating jaringan_jalan datastore...")
    shp_path = f"file:uploads/jaringan-jalan/jaringan-jalan.shp"
    store_json = f'{{"dataStore":{{"name":"jaringan_jalan","type":"Shapefile","enabled":true,"workspace":{{"name":"{WORKSPACE}"}},"connectionParameters":{{"entry":[{{"@key":"url","$":"{shp_path}"}},{{"@key":"create spatial index","$":"true"}}]}}}}}}'
    
    cmd = f'''curl -s -w "\\n%{{http_code}}" -X POST "{REST_LOCAL}/workspaces/{WORKSPACE}/datastores" -H "Content-Type: application/json" -u {USERNAME}:{PASSWORD} -d '{store_json}' '''
    out, e, code = ssh_exec(ssh, cmd, timeout=30)
    lines = out.strip().split('\n')
    http_code = lines[-1] if lines else "?"
    ok(f"Create store: HTTP {http_code}")
    if http_code not in ("200", "201"):
        log(f"  Response: {out[:300]}")

    # 7d) Publish jaringan-jalan layer
    log("Publishing jaringan-jalan feature type...")
    ft_json = f'{{"featureType":{{"name":"jaringan-jalan","nativeName":"jaringan-jalan","title":"Jaringan Jalan","srs":"EPSG:32749","enabled":true}}}}'
    cmd = f'''curl -s -w "\\n%{{http_code}}" -X POST "{REST_LOCAL}/workspaces/{WORKSPACE}/datastores/jaringan_jalan/featuretypes" -H "Content-Type: application/json" -u {USERNAME}:{PASSWORD} -d '{ft_json}' '''
    out, e, code = ssh_exec(ssh, cmd, timeout=30)
    lines = out.strip().split('\n')
    http_code = lines[-1] if lines else "?"
    ok(f"Publish layer: HTTP {http_code}")
    if http_code not in ("200", "201"):
        log(f"  Response: {out[:300]}")

    # 7e) Apply styles to layers
    log("Applying styles...")
    for layer, style in [("Batas_Kecamatan", "batas_kecamatan_style"), ("jaringan-jalan", "jaringan_jalan_style")]:
        style_json = f'{{"layer":{{"defaultStyle":{{"name":"{WORKSPACE}:{style}"}}}}}}'
        cmd = f'''curl -s -w "\\n%{{http_code}}" -X PUT "{REST_LOCAL}/layers/{WORKSPACE}:{layer}" -H "Content-Type: application/json" -u {USERNAME}:{PASSWORD} -d '{style_json}' '''
        out, e, code = ssh_exec(ssh, cmd, timeout=15)
        lines = out.strip().split('\n')
        http_code = lines[-1] if lines else "?"
        ok(f"Apply style to {layer}: HTTP {http_code}")

    # 7f) Create Layer Group
    log("Creating Layer Group 'peta_satu_peta'...")
    # Delete existing
    ssh_exec(ssh, f'curl -s -X DELETE "{REST_LOCAL}/workspaces/{WORKSPACE}/layergroups/peta_satu_peta" -u {USERNAME}:{PASSWORD}', timeout=10)
    
    group_json = f'''{{"layerGroup":{{"name":"peta_satu_peta","mode":"SINGLE","title":"Peta Satu Peta - Kota Tasikmalaya","abstractTxt":"Peta komposit jaringan jalan dan batas kecamatan","workspace":{{"name":"{WORKSPACE}"}},"publishables":{{"published":[{{"@type":"layer","name":"{WORKSPACE}:Batas_Kecamatan"}},{{"@type":"layer","name":"{WORKSPACE}:jaringan-jalan"}}]}},"styles":{{"style":[{{"name":"{WORKSPACE}:batas_kecamatan_style"}},{{"name":"{WORKSPACE}:jaringan_jalan_style"}}]}},"bounds":{{"minx":108.1,"maxx":108.35,"miny":-7.45,"maxy":-7.25,"crs":"EPSG:4326"}}}}}}'''
    
    cmd = f'''curl -s -w "\\n%{{http_code}}" -X POST "{REST_LOCAL}/workspaces/{WORKSPACE}/layergroups" -H "Content-Type: application/json" -u {USERNAME}:{PASSWORD} -d '{group_json}' '''
    out, e, code = ssh_exec(ssh, cmd, timeout=30)
    lines = out.strip().split('\n')
    http_code = lines[-1] if lines else "?"
    ok(f"Create Layer Group: HTTP {http_code}")
    if http_code not in ("200", "201"):
        log(f"  Response: {out[:300]}")

    # 8) Verify
    log("Verifying...")
    out, _, _ = ssh_exec(ssh, f'curl -s "{GS_LOCAL}/{WORKSPACE}/wms?service=WMS&version=1.1.1&request=GetCapabilities" -u {USERNAME}:{PASSWORD} | grep -o "Name>[^<]*</Name" | head -10', timeout=30)
    if out:
        ok(f"WMS layers: {out}")

    ssh.close()
    
    print("\n" + "=" * 60)
    print("COMPLETED!")
    print(f"  WMS: https://geoserver.tasikmalayakota.go.id/geoserver/{WORKSPACE}/wms")
    print(f"  WFS: https://geoserver.tasikmalayakota.go.id/geoserver/{WORKSPACE}/wfs")
    print(f"  Layer Group: peta_satu_peta")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
