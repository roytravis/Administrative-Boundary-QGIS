from qgis.core import (
    QgsCategorizedSymbolRenderer, QgsRendererCategory,
    QgsLineSymbol, QgsStyle, QgsPalLayerSettings, 
    QgsVectorLayerSimpleLabeling, QgsTextFormat,
    QgsTextBufferSettings
)
from qgis.utils import iface
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

layer = iface.activeLayer()

if not layer:
    print("Please select the jaringan-jalan layer in the Layers panel first.")
else:
    field_name = 'Fungsi'
    categories = []

    # 1. Kolektor Sekunder
    symbol_ks = QgsLineSymbol.createSimple({'color': '#FFC04C', 'line_width': '0.6'})
    category_ks = QgsRendererCategory('Kolektor Sekunder', symbol_ks, 'Kolektor Sekunder')
    categories.append(category_ks)

    # 2. Jalan Lingkungan
    symbol_jl = QgsLineSymbol.createSimple({'color': '#999999', 'line_width': '0.3'})
    category_jl = QgsRendererCategory('Jalan Lingkungan', symbol_jl, 'Jalan Lingkungan')
    categories.append(category_jl)

    # 3. Landasan
    symbol_ld = QgsLineSymbol.createSimple({'color': '#333333', 'line_width': '1.8'})
    if symbol_ld.symbolLayerCount() > 0:
        symbol_ld.symbolLayer(0).setPenCapStyle(Qt.FlatCap)
    category_ld = QgsRendererCategory('Landasan', symbol_ld, 'Landasan')
    categories.append(category_ld)

    # 4. Kolektor Primer
    symbol_kp = QgsLineSymbol.createSimple({'color': '#FFA500', 'line_width': '0.8'})
    category_kp = QgsRendererCategory('Kolektor Primer', symbol_kp, 'Kolektor Primer')
    categories.append(category_kp)

    # 5. Lokal Sekunder
    symbol_ls = QgsLineSymbol.createSimple({'color': '#FFFF00', 'line_width': '0.4'})
    category_ls = QgsRendererCategory('Lokal Sekunder', symbol_ls, 'Lokal Sekunder')
    categories.append(category_ls)

    # 6. Jalur Kereta Api (topo railway from QGIS predefined styles)
    style = QgsStyle.defaultStyle()
    symbol_jka = style.symbol('topo railway')
    if not symbol_jka:
        symbol_jka = style.symbol('Railway')
    if not symbol_jka:
        symbol_jka = QgsLineSymbol.createSimple({'color': '#000000', 'line_width': '0.5'})
    category_jka = QgsRendererCategory('Jalur Kereta Api', symbol_jka, 'Jalur Kereta Api')
    categories.append(category_jka)

    # Apply categorized renderer
    renderer = QgsCategorizedSymbolRenderer(field_name, categories)
    layer.setRenderer(renderer)
    
    # Apply Labeling Settings (using 'Nama_Jalan' as the label field assuming it exists)
    label_settings = QgsPalLayerSettings()
    label_settings.fieldName = "Nama_Jalan"
    
    # Text Formatting
    text_format = QgsTextFormat()
    font = QFont("Arial", 8)
    text_format.setFont(font)
    text_format.setSize(8) # 8 pt
    text_format.setColor(QColor("#000000")) # Black
    
    # Buffer (Halo) Settings
    buffer_settings = QgsTextBufferSettings()
    buffer_settings.setEnabled(True)
    buffer_settings.setSize(0.6) # 0.5 - 0.8 mm
    buffer_settings.setColor(QColor("#FFFFFF")) # White halo
    text_format.setBuffer(buffer_settings)
    
    # Data defined properties for bolding Kolektor roads
    # If the function is Kolektor Primary or Secondary, make it bold
    # Otherwise keep regular
    from qgis.core import QgsProperty
    bold_expression = "if(\"Fungsi\" LIKE '%Kolektor%', True, False)"
    text_format.dataDefinedProperties().setProperty(QgsPalLayerSettings.Bold, QgsProperty.fromExpression(bold_expression))
    
    label_settings.setFormat(text_format)
    
    # Placement Settings
    label_settings.placement = QgsPalLayerSettings.Line
    label_settings.placementFlags = QgsPalLayerSettings.OnLine
    
    # Create the labeling configuration
    labeling = QgsVectorLayerSimpleLabeling(label_settings)
    layer.setLabelsEnabled(True)
    layer.setLabeling(labeling)

    layer.triggerRepaint()
    print("Styling and Labeling applied successfully!")
