import geopandas as gpd
import os
import sys

def main():
    base_dir = r"d:\2026\Satu Peta\UPLOAD"
    
    # Define file paths
    # Found from previous search:
    files = {
        'lahan': os.path.join(base_dir, r"Presentase\PENGGUNAAN LAHAN\PENGGUNAAN_LAHAN.shp"),
        'polaruang1': os.path.join(base_dir, r"Presentase\RDTR\Polaruang_Tasikmalaya.shp"),
        'polaruang2': os.path.join(base_dir, r"Presentase\RTRW\Pola_Ruang_Final_Perda_PUSDATIN.shp"),
        'kecamatan': os.path.join(base_dir, r"Batas Administrasi\batas_kecamatan_1.shp")
    }

    print("Loading shapefiles...")
    try:
        gdf_lahan = gpd.read_file(files['lahan'])
        gdf_pol1 = gpd.read_file(files['polaruang1'])
        gdf_pol2 = gpd.read_file(files['polaruang2'])
        gdf_kec = gpd.read_file(files['kecamatan'])
    except Exception as e:
        print(f"Error loading shapefiles: {e}")
        return

    print("Fixing geometries (make_valid)...")
    gdf_lahan['geometry'] = gdf_lahan.geometry.make_valid()
    gdf_pol1['geometry'] = gdf_pol1.geometry.make_valid()
    gdf_pol2['geometry'] = gdf_pol2.geometry.make_valid()
    gdf_kec['geometry'] = gdf_kec.geometry.make_valid()

    print("Filtering attributes...")
    # Helper to check if column exists, returns first match
    def get_existing_cols(df, candidates):
        return [c for c in df.columns if c in candidates]

    col_lahan = get_existing_cols(gdf_lahan, ['Unsur', 'Sub_Kelas', 'Kelas', 'geometry'])
    # ensure geometry is there
    if 'geometry' not in col_lahan: col_lahan.append('geometry')
    gdf_lahan = gdf_lahan[col_lahan]

    col_pol1 = get_existing_cols(gdf_pol1, ['Hirarki_I', 'Hirarki_II', 'Kode', 'geometry'])
    if 'geometry' not in col_pol1: col_pol1.append('geometry')
    gdf_pol1 = gdf_pol1[col_pol1]

    col_pol2 = get_existing_cols(gdf_pol2, ['Ket', 'geometry'])
    if 'geometry' not in col_pol2: col_pol2.append('geometry')
    gdf_pol2 = gdf_pol2[col_pol2]

    col_kec = get_existing_cols(gdf_kec, ['KECAMATAN', 'LABEL_KEC', 'geometry'])
    if 'geometry' not in col_kec: col_kec.append('geometry')
    gdf_kec = gdf_kec[col_kec]

    # Harmonize CRS to the first one just in case
    target_crs = gdf_lahan.crs
    if target_crs is None:
        print("Warning: PENGGUNAAN_LAHAN has no CRS defined.")
        target_crs = gdf_kec.crs
    
    # Project all to target_crs to be safe
    if gdf_pol1.crs != target_crs: gdf_pol1 = gdf_pol1.to_crs(target_crs)
    if gdf_pol2.crs != target_crs: gdf_pol2 = gdf_pol2.to_crs(target_crs)
    if gdf_kec.crs != target_crs: gdf_kec = gdf_kec.to_crs(target_crs)

    print("Intersecting geometries...")
    # Iterative intersection
    try:
        print("  Intersecting Lahan and PolaRuang_Tasikmalaya...")
        overlay1 = gdf_lahan.overlay(gdf_pol1, how='intersection')
        print("  Intersecting result with PolaRuang_Perda...")
        overlay2 = overlay1.overlay(gdf_pol2, how='intersection')
        print("  Intersecting result with Kecamatan...")
        final_gdf = overlay2.overlay(gdf_kec, how='intersection')
    except Exception as e:
        print(f"Error during intersection: {e}")
        return

    print("Area recalculation...")
    # Ensure any default area fields are dropped (the overlay and subsetting above probably handled this,
    # but we will check)
    drop_cols = [c for c in final_gdf.columns if c.lower() in ['shape_area', 'luas_ha', 'luas']]
    if drop_cols:
        final_gdf = final_gdf.drop(columns=drop_cols)
    
    # Calculate Area using equal area projection if current is latlon, but let's just use current CRS area
    # If the user's data is UTM (m), then $area / 10000 gives Hectares.
    # We will use the native geometry area divided by 10000 as requested
    final_gdf['Luas_Ha'] = final_gdf.geometry.area / 10000.0

    output_path = os.path.join(base_dir, "Tasikmalaya_Merged_Suitability.shp")
    print(f"Saving merged shapefile to {output_path}...")
    try:
        final_gdf.to_file(output_path, driver='ESRI Shapefile')
        print(f"Successfully saved to {output_path}.")
    except Exception as e:
        print(f"Error saving to file: {e}")

if __name__ == "__main__":
    main()
