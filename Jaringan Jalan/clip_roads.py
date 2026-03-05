"""
Clip jaringan-jalan road features to the Batas Kecamatan boundary.

Removes or trims any road geometry that extends beyond the official
administrative area.  Run this script inside the QGIS Python Console.
"""

import os
import shutil
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsGeometry,
    QgsFeatureRequest,
    QgsWkbTypes,
)

# ───────── paths ─────────
ROAD_DIR = r'D:\2026\Satu Peta\UPLOAD\Jaringan Jalan'
ROAD_SHP = os.path.join(ROAD_DIR, 'jaringan-jalan.shp')

BOUNDARY_DIR = r'D:\2026\Satu Peta\UPLOAD\Batas Administrasi'
BOUNDARY_SHP = os.path.join(BOUNDARY_DIR, 'Batas_Kecamatan.shp')

# ───────── backup ─────────
base = os.path.join(ROAD_DIR, 'jaringan-jalan')
for ext in ('.shp', '.shx', '.dbf', '.prj', '.cpg', '.qmd'):
    src = base + ext
    if os.path.exists(src):
        shutil.copy2(src, base + ext + '.clip_bak')
print("✔ Backup created (.clip_bak files)")

# ───────── load layers ─────────
road_layer = QgsVectorLayer(ROAD_SHP, 'jaringan-jalan', 'ogr')
boundary_layer = QgsVectorLayer(BOUNDARY_SHP, 'Batas_Kecamatan', 'ogr')

if not road_layer.isValid():
    raise RuntimeError(f"Cannot load road layer: {ROAD_SHP}")
if not boundary_layer.isValid():
    raise RuntimeError(f"Cannot load boundary layer: {BOUNDARY_SHP}")

total_roads = road_layer.featureCount()
print(f"Road features loaded    : {total_roads}")
print(f"Boundary polygons loaded: {boundary_layer.featureCount()}")

# ───────── dissolve boundary into one polygon ─────────
combined_geom = QgsGeometry()
for feat in boundary_layer.getFeatures():
    g = feat.geometry()
    if combined_geom.isNull() or combined_geom.isEmpty():
        combined_geom = g
    else:
        combined_geom = combined_geom.combine(g)

if combined_geom.isNull() or combined_geom.isEmpty():
    raise RuntimeError("Failed to create combined boundary geometry.")

print("✔ Boundary dissolved into single polygon")

# ───────── clip roads ─────────
ids_to_delete = []     # features fully outside
trimmed_count = 0      # features that were partially clipped
unchanged_count = 0    # features fully inside

road_layer.startEditing()

for feat in road_layer.getFeatures():
    road_geom = feat.geometry()

    # Skip empty/null geometries
    if road_geom.isNull() or road_geom.isEmpty():
        ids_to_delete.append(feat.id())
        continue

    # Check if the road is fully within the boundary
    if combined_geom.contains(road_geom):
        unchanged_count += 1
        continue

    # Check if the road has any intersection at all
    if not combined_geom.intersects(road_geom):
        # Fully outside — mark for deletion
        ids_to_delete.append(feat.id())
        continue

    # Partially inside — clip (intersect) with boundary
    clipped = road_geom.intersection(combined_geom)

    if clipped.isNull() or clipped.isEmpty():
        ids_to_delete.append(feat.id())
        continue

    # Ensure the result is still a line geometry (not a point from touching)
    result_type = QgsWkbTypes.geometryType(clipped.wkbType())
    if result_type != QgsWkbTypes.LineGeometry:
        # Intersection produced a point or polygon — treat as outside
        ids_to_delete.append(feat.id())
        continue

    # Update the feature geometry with the clipped version
    road_layer.changeGeometry(feat.id(), clipped)
    trimmed_count += 1

# Delete features that are fully outside
if ids_to_delete:
    road_layer.deleteFeatures(ids_to_delete)

# Commit all changes
success = road_layer.commitChanges()

if success:
    print("\n═══════ RESULTS ═══════")
    print(f"Total features before  : {total_roads}")
    print(f"Unchanged (fully inside): {unchanged_count}")
    print(f"Trimmed (clipped)       : {trimmed_count}")
    print(f"Removed (fully outside) : {len(ids_to_delete)}")
    print(f"Total features after    : {road_layer.featureCount()}")
    print("═══════════════════════")
    print("\n✔ All road features are now constrained within the administrative boundary.")
else:
    road_layer.rollBack()
    errors = road_layer.commitErrors()
    print(f"ERROR: Failed to commit changes. Errors: {errors}")

# ───────── refresh in QGIS ─────────
for lyr in QgsProject.instance().mapLayers().values():
    src = lyr.source().replace('\\', '/').lower()
    target = ROAD_SHP.replace('\\', '/').lower()
    if target in src:
        lyr.reload()
        lyr.triggerRepaint()
        print("✔ Layer refreshed in QGIS canvas.")
        break

print("\nDone! Inspect the map to verify — no roads should extend beyond the boundary.")
