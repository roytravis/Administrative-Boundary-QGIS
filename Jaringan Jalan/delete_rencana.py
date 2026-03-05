"""
Delete all features with Fungsi == 'Rencana Kolektor Primer' from jaringan-jalan.shp

Uses QGIS native API – no external libraries needed.
"""
import os
import shutil
from qgis.core import QgsVectorLayer, QgsProject

SHP_DIR = r'D:\2026\Satu Peta\UPLOAD\Jaringan Jalan'
SHP_FILE = os.path.join(SHP_DIR, 'jaringan-jalan.shp')
FIELD_NAME = 'Fungsi'
VALUE_TO_DELETE = 'Rencana Kolektor Primer'

# ---------- backup ----------
base = os.path.join(SHP_DIR, 'jaringan-jalan')
for ext in ('.shp', '.shx', '.dbf', '.prj', '.cpg', '.qmd'):
    src = base + ext
    if os.path.exists(src):
        shutil.copy2(src, base + ext + '.bak')
print("Backup created (.bak files)")

# ---------- load layer ----------
layer = QgsVectorLayer(SHP_FILE, 'jaringan-jalan', 'ogr')
if not layer.isValid():
    print(f"ERROR: Could not load layer from {SHP_FILE}")
else:
    # Find field index
    field_idx = layer.fields().indexFromName(FIELD_NAME)
    if field_idx == -1:
        print(f"ERROR: Field '{FIELD_NAME}' not found. Available: {[f.name() for f in layer.fields()]}")
    else:
        # Find features to delete
        ids_to_delete = []
        for feat in layer.getFeatures():
            val = str(feat[FIELD_NAME]).strip()
            if val == VALUE_TO_DELETE:
                ids_to_delete.append(feat.id())

        total = layer.featureCount()
        removed = len(ids_to_delete)
        print(f"Total features : {total}")
        print(f"To remove      : {removed}")
        print(f"To keep        : {total - removed}")

        if removed == 0:
            print("Nothing to remove – no features matched 'Rencana Kolektor Primer'.")
        else:
            # Delete features
            layer.startEditing()
            layer.deleteFeatures(ids_to_delete)
            layer.commitChanges()
            print(f"\nDone! Removed {removed} features. {total - removed} features remain.")

            # Refresh any matching layer in the current QGIS project
            for lyr in QgsProject.instance().mapLayers().values():
                if lyr.source() == layer.source():
                    lyr.reload()
                    lyr.triggerRepaint()
                    print("Layer refreshed in QGIS.")
