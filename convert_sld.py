import re, os

def convert_sld(sld_content):
    text = sld_content
    text = text.replace('version="1.1.0"', 'version="1.0.0"')
    text = text.replace("http://schemas.opengis.net/sld/1.1.0/StyledLayerDescriptor.xsd",
                        "http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd")
    text = re.sub(r"<se:", "<", text)
    text = re.sub(r"</se:", "</", text)
    text = re.sub(r'\s*xmlns:se="http://www.opengis.net/se"', "", text)
    text = text.replace("SvgParameter", "CssParameter")
    text = re.sub(r"<Gap>\s*<ogc:Literal>([^<]+)</ogc:Literal>\s*</Gap>", r"<Gap>\1</Gap>", text)
    text = re.sub(r"\s*<GeneralizeLine>[^<]*</GeneralizeLine>", "", text)
    return text

base = r'd:\2026\Satu Peta\UPLOAD'

# Convert jaringan_jalan.sld
with open(os.path.join(base, 'Jaringan Jalan', 'jaringan_jalan.sld'), 'r', encoding='utf-8') as f:
    sld = f.read()
converted = convert_sld(sld)
out = os.path.join(base, 'jaringan_jalan_style.sld')
with open(out, 'w', encoding='utf-8') as f:
    f.write(converted)
print(f'Created: {out}')

# Convert batas_administrasi.sld
with open(os.path.join(base, 'Batas Administrasi', 'batas_administrasi.sld'), 'r', encoding='utf-8') as f:
    sld = f.read()
converted = convert_sld(sld)
out = os.path.join(base, 'batas_kecamatan_style.sld')
with open(out, 'w', encoding='utf-8') as f:
    f.write(converted)
print(f'Created: {out}')
print('Done!')
