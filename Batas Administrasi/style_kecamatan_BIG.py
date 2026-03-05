"""
=============================================================
  QGIS Python Console Script
  District Map Styling — BIG (Badan Informasi Geospasial) Standard
  Kota Tasikmalaya — 10 Kecamatan
=============================================================

HOW TO USE:
  1. Open QGIS and load "Batas_Kecamatan.shp"
  2. Open Python Console: Plugins > Python Console
  3. Click "Show Editor" (the notepad icon)
  4. Open this script file, then click "Run Script"
  
  The script will automatically find the Batas_Kecamatan layer
  and apply all BIG-standard styling.
=============================================================
"""

from qgis.core import (
    QgsProject,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsSymbol,
    QgsFillSymbol,
    QgsSimpleLineSymbolLayer,
    QgsSimpleFillSymbolLayer,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling,
    QgsProperty,
    QgsMapUnitScale,
    QgsField,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import Qt, QSizeF
from qgis.PyQt.QtGui import QColor, QFont
import re


# ─────────────────────────────────────────────────────────────
# 1. CONFIGURATION
# ─────────────────────────────────────────────────────────────

# Layer name (as it appears in the QGIS Layers panel)
LAYER_NAME = "Batas_Kecamatan"

# Field used for categorization
FIELD_NAME = "KECAMATAN"

# 5 Pastel colors (BIG standard)
PASTEL_YELLOW = "#FFFDE7"
PASTEL_GREEN  = "#E8F5E9"
PASTEL_BLUE   = "#E3F2FD"
PASTEL_PINK   = "#FCE4EC"
PASTEL_ORANGE = "#FFF3E0"

# Color assignment per district (no adjacent districts share the same color)
DISTRICT_COLORS = {
    "Kec. Cihideung":   PASTEL_YELLOW,
    "Kec. Cipedes":     PASTEL_BLUE,
    "Kec. Tawang":      PASTEL_GREEN,
    "Kec. Mangkubumi":  PASTEL_PINK,
    "Kec. Bungursari":  PASTEL_YELLOW,
    "Kec. Purbaratu":   PASTEL_ORANGE,
    "Kec. Indihiang":   PASTEL_BLUE,
    "Kec. Kawalu":      PASTEL_PINK,
    "Kec. Cibeureum":   PASTEL_GREEN,
    "Kec. Tamansari":   PASTEL_ORANGE,
}

# Boundary line settings
STROKE_COLOR   = "#333333"
STROKE_WIDTH   = 0.46        # mm
DASH_PATTERN   = [4, 1.5, 1, 1.5, 1, 1.5]  # dash-dot-dot

# Label settings
LABEL_FONT_FAMILY = "Arial"
LABEL_FONT_STYLE  = "Bold"
LABEL_FONT_SIZE   = 11       # pt
LABEL_COLOR       = "#000000"
BUFFER_COLOR      = "#FFFFFF"
BUFFER_SIZE       = 0.7      # mm
BUFFER_OPACITY     = 85      # percent (0–100)


# ─────────────────────────────────────────────────────────────
# 2. FIND THE LAYER
# ─────────────────────────────────────────────────────────────

def find_layer(name):
    """Find the layer by name in the current QGIS project."""
    layers = QgsProject.instance().mapLayersByName(name)
    if not layers:
        # Try partial match
        for lyr in QgsProject.instance().mapLayers().values():
            if name.lower() in lyr.name().lower():
                return lyr
        return None
    return layers[0]


layer = find_layer(LAYER_NAME)
if layer is None:
    raise Exception(
        f'Layer "{LAYER_NAME}" not found! '
        f'Please load Batas_Kecamatan.shp first.'
    )

print(f"✔ Found layer: {layer.name()}")


# ─────────────────────────────────────────────────────────────
# 3. BUILD CATEGORIZED RENDERER (Fill + Boundary)
# ─────────────────────────────────────────────────────────────

from qgis.core import QgsUnitTypes

categories = []

for district_name, fill_hex in DISTRICT_COLORS.items():
    # --- Create fill symbol ---
    symbol = QgsFillSymbol.createSimple({})

    # Configure the fill layer (color only, NO stroke)
    fill_layer = symbol.symbolLayer(0)
    fill_layer.setColor(QColor(fill_hex))
    fill_layer.setStrokeStyle(Qt.NoPen)  # disable stroke on fill layer

    # --- Add a separate line symbol layer for the boundary ---
    line_layer = QgsSimpleLineSymbolLayer()
    line_layer.setColor(QColor(STROKE_COLOR))
    line_layer.setWidth(STROKE_WIDTH)
    line_layer.setWidthUnit(QgsUnitTypes.RenderMillimeters)
    line_layer.setPenJoinStyle(Qt.RoundJoin)
    line_layer.setPenStyle(Qt.CustomDashLine)
    line_layer.setUseCustomDashPattern(True)
    line_layer.setCustomDashVector(DASH_PATTERN)

    symbol.appendSymbolLayer(line_layer)

    # --- Create category ---
    # Label for legend: strip "Kec. " prefix and convert to UPPER CASE
    legend_label = re.sub(r'^Kec\.\s*', '', district_name).upper()

    cat = QgsRendererCategory(district_name, symbol, legend_label)
    categories.append(cat)

# Apply categorized renderer
renderer = QgsCategorizedSymbolRenderer(FIELD_NAME, categories)
layer.setRenderer(renderer)

print("✔ Categorized fill colors applied (5 pastel colors, BIG standard)")
print("✔ Dash-dot-dot boundary lines applied")


# ─────────────────────────────────────────────────────────────
# 4. ADD VIRTUAL FIELD FOR SLD-COMPATIBLE LABELS
# ─────────────────────────────────────────────────────────────

# SLD cannot export expressions — only plain field references.
# So we create a virtual field with the pre-computed label text.
LABEL_FIELD = "LABEL_KEC"

# Remove old virtual field if it exists (from a previous run)
idx = layer.fields().indexOf(LABEL_FIELD)
if idx >= 0:
    layer.removeExpressionField(idx)

# Add virtual field: strip "Kec. " prefix and convert to UPPER CASE
label_expr = "upper(regexp_replace(\"KECAMATAN\", '^Kec\\\\.\\\\s*', ''))"
layer.addExpressionField(label_expr, QgsField(LABEL_FIELD, 10))  # 10 = QString

print(f"✔ Virtual field '{LABEL_FIELD}' created for SLD-compatible labels")


# ─────────────────────────────────────────────────────────────
# 5. CONFIGURE LABELS
# ─────────────────────────────────────────────────────────────

label_settings = QgsPalLayerSettings()

# --- Use the virtual field (plain field reference = SLD-compatible) ---
label_settings.fieldName = LABEL_FIELD
label_settings.isExpression = False

# --- Text format ---
text_format = QgsTextFormat()

# Font
font = QFont(LABEL_FONT_FAMILY)
font.setBold(True)
font.setPointSizeF(LABEL_FONT_SIZE)
text_format.setFont(font)

# Font color
text_format.setColor(QColor(LABEL_COLOR))

# --- Text buffer (halo) ---
buffer_settings = QgsTextBufferSettings()
buffer_settings.setEnabled(True)
buffer_settings.setSize(BUFFER_SIZE)
buffer_settings.setSizeUnit(QgsUnitTypes.RenderMillimeters)
buffer_settings.setColor(QColor(BUFFER_COLOR))
buffer_settings.setOpacity(BUFFER_OPACITY / 100.0)

text_format.setBuffer(buffer_settings)
label_settings.setFormat(text_format)

# --- Placement: over centroid, horizontal ---
try:
    label_settings.placement = Qgis.LabelPlacement.OverPoint
except AttributeError:
    label_settings.placement = QgsPalLayerSettings.OverPoint
label_settings.centroidWhole = True

# Apply labeling
labeling = QgsVectorLayerSimpleLabeling(label_settings)
layer.setLabeling(labeling)
layer.setLabelsEnabled(True)

print("✔ District labels applied (Arial Bold, ALL CAPS, white halo)")


# ─────────────────────────────────────────────────────────────
# 6. REFRESH
# ─────────────────────────────────────────────────────────────

layer.triggerRepaint()
iface.layerTreeView().refreshLayerSymbology(layer.id())

print("")
print("═══════════════════════════════════════════════════════")
print("  ✔ ALL STYLING APPLIED SUCCESSFULLY (BIG Standard)")
print("═══════════════════════════════════════════════════════")
print(f"  Layer   : {layer.name()}")
print(f"  Field   : {FIELD_NAME}")
print(f"  Districts: {len(DISTRICT_COLORS)}")
print(f"  Colors  : 5 pastel (Yellow, Green, Blue, Pink, Orange)")
print(f"  Boundary: Dash-dot-dot, {STROKE_WIDTH}mm, {STROKE_COLOR}")
print(f"  Labels  : {LABEL_FONT_FAMILY} {LABEL_FONT_STYLE} {LABEL_FONT_SIZE}pt")
print(f"  Halo    : {BUFFER_COLOR}, {BUFFER_SIZE}mm, {BUFFER_OPACITY}%")
print("═══════════════════════════════════════════════════════")
