import zipfile, os

base = r'd:\2026\Satu Peta\UPLOAD'

# Batas_Kecamatan
batas_dir = os.path.join(base, 'Batas Administrasi')
out1 = os.path.join(base, 'Batas_Kecamatan.zip')
with zipfile.ZipFile(out1, 'w', zipfile.ZIP_DEFLATED) as zf:
    for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
        f = os.path.join(batas_dir, 'Batas_Kecamatan' + ext)
        if os.path.exists(f):
            zf.write(f, 'Batas_Kecamatan' + ext)
            print(f'Added Batas_Kecamatan{ext}')
print(f'Created: {out1} ({os.path.getsize(out1)} bytes)')

# jaringan-jalan
jalan_dir = os.path.join(base, 'Jaringan Jalan')
out2 = os.path.join(base, 'jaringan-jalan.zip')
with zipfile.ZipFile(out2, 'w', zipfile.ZIP_DEFLATED) as zf:
    for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
        f = os.path.join(jalan_dir, 'jaringan-jalan' + ext)
        if os.path.exists(f):
            zf.write(f, 'jaringan-jalan' + ext)
            print(f'Added jaringan-jalan{ext}')
print(f'Created: {out2} ({os.path.getsize(out2)} bytes)')
print('Done!')
