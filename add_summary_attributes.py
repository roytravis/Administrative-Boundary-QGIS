"""
Add City-Wide and Per-Kecamatan summary attributes
Run this inside the QGIS Python Console!
"""

from qgis.core import QgsProject, QgsField, QgsExpression, QgsExpressionContext, QgsExpressionContextUtils
from PyQt5.QtCore import QVariant
from qgis.utils import iface

def main():
    # Find the conformity layer
    conf_layer = None
    for layer in QgsProject.instance().mapLayers().values():
        name = layer.name().lower()
        if "kesesuaian" in name or "conformity" in name:
            conf_layer = layer
            break

    if not conf_layer:
        print("ERROR: Could not find the Kesesuaian/Conformity layer.")
        return

    print(f"Found layer: {conf_layer.name()} ({conf_layer.featureCount()} features)")

    # ── A. CITY-WIDE STATS ──
    total_sesuai = 0.0
    total_tidak = 0.0
    for feat in conf_layer.getFeatures():
        luas = feat['Luas_Ha'] or 0
        if feat['KESESUAIAN'] == 'Sesuai':
            total_sesuai += luas
        else:
            total_tidak += luas
    total_all = total_sesuai + total_tidak
    city_ses_pct = round((total_sesuai / total_all) * 100, 2) if total_all > 0 else 0
    city_tdk_pct = round((total_tidak / total_all) * 100, 2) if total_all > 0 else 0

    print(f"  City-Wide: Sesuai={total_sesuai:.2f} Ha ({city_ses_pct}%), Tidak Sesuai={total_tidak:.2f} Ha ({city_tdk_pct}%)")

    # ── B. PER-KECAMATAN STATS ──
    kec_stats = {}
    for feat in conf_layer.getFeatures():
        kec = feat['LABEL_KEC']
        luas = feat['Luas_Ha'] or 0
        kes = feat['KESESUAIAN']
        if kec not in kec_stats:
            kec_stats[kec] = {'Sesuai': 0.0, 'Tidak Sesuai': 0.0}
        if kes == 'Sesuai':
            kec_stats[kec]['Sesuai'] += luas
        else:
            kec_stats[kec]['Tidak Sesuai'] += luas

    for kec, vals in sorted(kec_stats.items()):
        tot = vals['Sesuai'] + vals['Tidak Sesuai']
        pct = round((vals['Sesuai'] / tot) * 100, 2) if tot > 0 else 0
        print(f"  {kec}: Sesuai={vals['Sesuai']:.2f} Ha ({pct}%)")

    # ── ADD NEW FIELDS ──
    provider = conf_layer.dataProvider()

    # Check which fields already exist
    existing = [f.name() for f in conf_layer.fields()]
    new_fields = []
    field_names = ['C_Ses_Ha', 'C_Tdk_Ha', 'C_Ses_Pct', 'C_Tdk_Pct',
                   'K_Ses_Ha', 'K_Tdk_Ha', 'K_Ses_Pct', 'K_Tdk_Pct']

    for fn in field_names:
        if fn not in existing:
            new_fields.append(QgsField(fn, QVariant.Double))

    if new_fields:
        provider.addAttributes(new_fields)
        conf_layer.updateFields()
        print(f"  Added {len(new_fields)} new fields.")
    else:
        print("  Fields already exist, updating values...")

    # ── POPULATE VALUES ──
    field_idx = {fn: conf_layer.fields().indexOf(fn) for fn in field_names}

    conf_layer.startEditing()

    for feat in conf_layer.getFeatures():
        kec = feat['LABEL_KEC']
        k_ses = kec_stats.get(kec, {}).get('Sesuai', 0)
        k_tdk = kec_stats.get(kec, {}).get('Tidak Sesuai', 0)
        k_tot = k_ses + k_tdk
        k_ses_pct = round((k_ses / k_tot) * 100, 2) if k_tot > 0 else 0
        k_tdk_pct = round((k_tdk / k_tot) * 100, 2) if k_tot > 0 else 0

        attrs = {
            field_idx['C_Ses_Ha']:  round(total_sesuai, 4),
            field_idx['C_Tdk_Ha']:  round(total_tidak, 4),
            field_idx['C_Ses_Pct']: city_ses_pct,
            field_idx['C_Tdk_Pct']: city_tdk_pct,
            field_idx['K_Ses_Ha']:  round(k_ses, 4),
            field_idx['K_Tdk_Ha']:  round(k_tdk, 4),
            field_idx['K_Ses_Pct']: k_ses_pct,
            field_idx['K_Tdk_Pct']: k_tdk_pct,
        }
        provider.changeAttributeValues({feat.id(): attrs})

    conf_layer.commitChanges()

    # ── SET FIELD ALIASES (displayed in Attribute Table) ──
    aliases = {
        'C_Ses_Ha':  'Total luas',
        'C_Tdk_Ha':  'Total luas tidak sesuai',
        'C_Ses_Pct': 'Persentase sesuai (%)',
        'C_Tdk_Pct': 'Persentase tidak sesuai (%)',
        'K_Ses_Ha':  'Luas sesuai kecamatan (Ha)',
        'K_Tdk_Ha':  'Luas tidak sesuai kecamatan (Ha)',
        'K_Ses_Pct': 'Persentase sesuai kecamatan (%)',
        'K_Tdk_Pct': 'Persentase tidak sesuai kecamatan (%)',
    }
    for short_name, alias in aliases.items():
        idx = conf_layer.fields().indexOf(short_name)
        if idx >= 0:
            conf_layer.setFieldAlias(idx, alias)

    conf_layer.triggerRepaint()
    iface.mapCanvas().refresh()

    print("\nDone! Open the Attribute Table to see the new columns.")
    print("Column aliases set:")
    for short_name, alias in aliases.items():
        print(f"  {short_name:10s} → {alias}")

main()
