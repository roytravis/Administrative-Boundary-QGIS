# Road Network Styling Instructions

Here are two ways you can apply the requested styling specification to your `jaringan-jalan.shp` shapefile in QGIS.

## Option 1: Automatic Approach (Recommended)
I have updated the Python script that will automatically apply **both** the line styling rules and the **cartographic road labeling standards**. It will automatically bold major roads, create a white text buffer, and curve labels along the lines.

1. Open your QGIS project and ensure your Road Network layer (`jaringan-jalan`) is selected in the Layers panel.
2. Click the **"Show Editor"** button in the Python Console (it looks like a notepad 📝 next to the broom 🧹). 
3. Open the script file `d:/2026/Satu Peta/UPLOAD/Jaringan Jalan/apply_style.py` on your computer, copy the entire file contents, and paste it into that large text editor on the right side of the QGIS Python Console.
4. Click the green **"Run script"** ▶️ button at the top of the editor.
5. The styles and labels will be instantly applied.

## Option 2: Manual Approach (as per your specifications)
If you prefer to apply them manually in QGIS:

### Part 1: Line Symbology
1. Right-click the layer and go to **Properties** -> **Symbology**.
2. Change the top dropdown to **Categorized**.
3. Set the **Value** to the `Fungsi` field and Click **Classify**.
4. Apply specs to each class:
   - **Kolektor Sekunder**: Color `#FFC04C`, Stroke width `0.6 mm`.
   - **Jalan Lingkungan**: Color `#999999`, Stroke width `0.3 mm`.
   - **Landasan**: Color `#333333`, Stroke width `1.8 mm`. Under Cap style, change to `Flat`.
   - **Kolektor Primer**: Color `#FFA500`, Stroke width `0.8 mm`.
   - **Rencana Kolektor Primer**: Color `#FFA500`, Stroke width `0.8 mm`. Change Stroke style to `Dash Line`.
   - **Lokal Sekunder**: Color `#FFFF00`, Stroke width `0.4 mm`.
   - **Jalur Kereta Api**: Double-click, under Symbol Layer Type select `topo railway`.

### Part 2: Labeling Standards
1. In the same Properties window, click the **Labels** tab on the left.
2. Change the top dropdown from "No Labels" to **Single Labels**.
3. Set **Value** to `Nama_Jalan` (or whichever field contains your street names).
4. **Text Tab**: 
   - Set Font to **Arial**.
   - Set Size and Units to **8 pt**.
   - Set Color to Black `#000000`.
   - *(Optional: To automatically bold Kolektor roads, click the Data-Defined Override icon next to "Style" -> Edit -> Paste: `if("Fungsi" LIKE '%Kolektor%', 'Bold', 'Regular')`)*
5. **Buffer Tab** (icon "a" with white shadow):
   - Check **Draw text buffer**.
   - Set Size to **0.6 mm**.
   - Set Color to White `#FFFFFF`.
6. **Placement Tab** (icon "a" over curved line):
   - Choose the **Curved** mode.
   - Under Allowed Positions, check **On line**.
7. Click **OK** to apply the styling and labeling rules!
