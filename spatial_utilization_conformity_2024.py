"""
Spatial Utilization Conformity Analysis 2024
(Kesesuaian Pemanfaatan Ruang — Kota Tasikmalaya)

Produces:
  - spatial_utilization_conformity_2024.shp
  - Summary table (console output)

Run with:
  & "C:\Program Files\QGIS 3.44.7\bin\python-qgis.bat" <this_script>
"""

import geopandas as gpd
import pandas as pd
import os
import warnings
warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────
# 1. CONFORMITY MAPPING
# ──────────────────────────────────────────────
# Key = RTRW Ket value  →  Value = set of conforming Unsur values
CONFORMITY_MAP = {
    # Residential zones
    "Berkepadatan Rendah":  {"Permukiman"},
    "Berkepadatan Sedang":  {"Permukiman"},
    "Berkepadatan Tinggi":  {"Permukiman"},

    # Commercial / Trade
    "Perdagangan dan Jasa": {"Pasar", "Bangunan Industri"},

    # Government offices
    "Perkantoran":          {"Bangunan Pemerintahan"},

    # Industry
    "Industri Pergudangan": {"Bangunan Industri"},

    # Tourism
    "Pariwisata":           {"Kawasan Pariwisata"},

    # Forestry
    "Hutan Produksi":       {"Hutan"},
    "Hutan Rakyat":         {"Hutan", "Belukar", "Semak Belukar"},

    # Agriculture
    "Pertaninan":           {"sawah", "Ladang"},
    "Pertanian Lainnya":    {"sawah", "Ladang"},

    # Fisheries
    "Minapolitan":          {"Empang"},

    # Protection / Conservation
    "Resapan air":          {"Hutan", "Belukar", "Semak Belukar", "Ladang"},
    "Rawan Gerakan Tanah":  {"Hutan", "Belukar", "Semak Belukar", "Ladang"},

    # Riparian / Buffer zones
    "Sempadan Sungai":      {"Sungai", "Belukar", "Semak Belukar"},
    "Sempadan Situ":        {"Danau/Situ", "Belukar", "Semak Belukar"},
    "Sempadan Rel":         {"Lahan Tidak Terbangun"},

    # Hazard
    "Aliran Lahar":         {"Lahan Tidak Terbangun", "Belukar", "Semak Belukar"},

    # Water body
    "Danau/Situ":           {"Danau/Situ"},

    # Mixed use
    "Kawasan Terpadu":      {"Permukiman", "Pasar", "Bangunan Industri", "Bangunan Pemerintahan"},

    # Public facilities
    "TPU":                  {"Pemakaman"},
    "TPPAS":                {"Lahan Tidak Terbangun"},
    "Hankam":               {"Bangunan Pemerintahan", "Lahan Tidak Terbangun", "Lapangan"},

    # Infrastructure / Utilities
    "Gardu Induk":          {"Lahan Tidak Terbangun", "Bangunan Industri"},
    "Pertamina":            {"Lahan Tidak Terbangun", "Bangunan Industri"},
    "Pertambangan":         {"Lahan Tidak Terbangun", "Bangunan Industri"},
    "Sutet":                {"Lahan Tidak Terbangun", "Bangunan Industri"},

    # Evacuation
    "Ruang Evakuasi":       {"Lapangan", "Lahan Tidak Terbangun"},
}


def classify_conformity(row):
    """Return 'Sesuai' or 'Tidak Sesuai'."""
    ket = row.get("Ket", "")
    unsur = row.get("Unsur", "")
    if pd.isna(ket) or pd.isna(unsur):
        return "Tidak Sesuai"
    allowed = CONFORMITY_MAP.get(ket)
    if allowed is None:
        return "Tidak Sesuai"
    return "Sesuai" if unsur in allowed else "Tidak Sesuai"


def main():
    base_dir = r"d:\2026\Satu Peta\UPLOAD"

    paths = {
        "lahan":  os.path.join(base_dir, r"Presentase\PENGGUNAAN LAHAN\PENGGUNAAN_LAHAN.shp"),
        "rtrw":   os.path.join(base_dir, r"Presentase\RTRW\Pola_Ruang_Final_Perda_PUSDATIN.shp"),
        "kec":    os.path.join(base_dir, r"Batas Administrasi\batas_kecamatan_1.shp"),
    }

    # ──────────────────────────────────────────
    # 2. LOAD
    # ──────────────────────────────────────────
    print("Loading shapefiles ...")
    gdf_lahan = gpd.read_file(paths["lahan"])
    gdf_rtrw  = gpd.read_file(paths["rtrw"])
    gdf_kec   = gpd.read_file(paths["kec"])

    # ──────────────────────────────────────────
    # 3. FIX GEOMETRY
    # ──────────────────────────────────────────
    print("Fixing geometries (make_valid) ...")
    gdf_lahan["geometry"] = gdf_lahan.geometry.make_valid()
    gdf_rtrw["geometry"]  = gdf_rtrw.geometry.make_valid()
    gdf_kec["geometry"]   = gdf_kec.geometry.make_valid()

    # ──────────────────────────────────────────
    # 4. CRS HARMONISATION → EPSG:32749
    # ──────────────────────────────────────────
    TARGET_CRS = "EPSG:32749"
    print(f"Reprojecting all layers to {TARGET_CRS} ...")
    if gdf_lahan.crs != TARGET_CRS:
        gdf_lahan = gdf_lahan.to_crs(TARGET_CRS)
    if gdf_rtrw.crs != TARGET_CRS:
        gdf_rtrw = gdf_rtrw.to_crs(TARGET_CRS)
    if gdf_kec.crs != TARGET_CRS:
        gdf_kec = gdf_kec.to_crs(TARGET_CRS)

    # ──────────────────────────────────────────
    # 5. TRIM ATTRIBUTES BEFORE OVERLAY
    # ──────────────────────────────────────────
    gdf_lahan = gdf_lahan[["Unsur", "Kelas", "geometry"]]
    gdf_rtrw  = gdf_rtrw[["Ket", "geometry"]]
    gdf_kec   = gdf_kec[["LABEL_KEC", "geometry"]]

    # ──────────────────────────────────────────
    # 6. INTERSECTION: RTRW × Land Use
    # ──────────────────────────────────────────
    print("Intersecting RTRW × Land Use ...")
    overlay1 = gdf_rtrw.overlay(gdf_lahan, how="intersection", keep_geom_type=True)

    # ──────────────────────────────────────────
    # 7. INTERSECTION: Result × Kecamatan
    # ──────────────────────────────────────────
    print("Intersecting result × Kecamatan ...")
    overlay2 = overlay1.overlay(gdf_kec, how="intersection", keep_geom_type=True)

    # ──────────────────────────────────────────
    # 8. CLASSIFY CONFORMITY
    # ──────────────────────────────────────────
    print("Classifying conformity ...")
    overlay2["KESESUAIAN"] = overlay2.apply(classify_conformity, axis=1)

    # ──────────────────────────────────────────
    # 9. AREA RECALCULATION
    # ──────────────────────────────────────────
    print("Calculating area (Luas_Ha) ...")
    overlay2["Luas_Ha"] = overlay2.geometry.area / 10_000.0

    # ──────────────────────────────────────────
    # 10. KEEP ONLY REQUIRED FIELDS
    # ──────────────────────────────────────────
    keep_cols = ["Ket", "Unsur", "Kelas", "LABEL_KEC", "KESESUAIAN", "Luas_Ha", "geometry"]
    overlay2 = overlay2[[c for c in keep_cols if c in overlay2.columns]]

    # ──────────────────────────────────────────
    # 11. SAVE SHAPEFILE
    # ──────────────────────────────────────────
    out_path = os.path.join(base_dir, "spatial_utilization_conformity_2024.shp")
    print(f"Saving to {out_path} ...")
    overlay2.to_file(out_path, driver="ESRI Shapefile")
    print(f"  ✔ Shapefile saved ({len(overlay2)} features).")

    # ──────────────────────────────────────────
    # 12. SUMMARY TABLE
    # ──────────────────────────────────────────
    print("\n" + "=" * 80)
    print("  SUMMARY TABLE — Spatial Utilization Conformity 2024 (Kota Tasikmalaya)")
    print("=" * 80)

    # ---- A. City-wide summary ----
    city_summary = (
        overlay2.groupby("KESESUAIAN")["Luas_Ha"]
        .sum()
        .reset_index()
        .rename(columns={"Luas_Ha": "Luas_Ha"})
    )
    total_area = city_summary["Luas_Ha"].sum()
    city_summary["Persen (%)"] = (city_summary["Luas_Ha"] / total_area * 100).round(2)
    city_summary["Luas_Ha"] = city_summary["Luas_Ha"].round(4)

    print("\n  A. City-Wide (Kota Tasikmalaya)")
    print("  " + "-" * 50)
    print(f"  {'Kesesuaian':<20} {'Luas (Ha)':>12} {'Persen (%)':>12}")
    print("  " + "-" * 50)
    for _, r in city_summary.iterrows():
        print(f"  {r['KESESUAIAN']:<20} {r['Luas_Ha']:>12,.4f} {r['Persen (%)']:>11.2f}%")
    print("  " + "-" * 50)
    print(f"  {'TOTAL':<20} {total_area:>12,.4f} {'100.00':>11}%")

    # ---- B. Per-kecamatan summary ----
    kec_summary = (
        overlay2.groupby(["LABEL_KEC", "KESESUAIAN"])["Luas_Ha"]
        .sum()
        .reset_index()
    )
    kec_total = overlay2.groupby("LABEL_KEC")["Luas_Ha"].sum().reset_index().rename(columns={"Luas_Ha": "Total_Ha"})
    kec_summary = kec_summary.merge(kec_total, on="LABEL_KEC")
    kec_summary["Persen (%)"] = (kec_summary["Luas_Ha"] / kec_summary["Total_Ha"] * 100).round(2)
    kec_summary["Luas_Ha"] = kec_summary["Luas_Ha"].round(4)

    print(f"\n\n  B. Per Kecamatan")
    print("  " + "-" * 70)
    print(f"  {'Kecamatan':<18} {'Kesesuaian':<18} {'Luas (Ha)':>12} {'Persen (%)':>12}")
    print("  " + "-" * 70)
    for kec_name in sorted(kec_summary["LABEL_KEC"].unique()):
        subset = kec_summary[kec_summary["LABEL_KEC"] == kec_name]
        tot = subset["Total_Ha"].iloc[0]
        for _, r in subset.iterrows():
            print(f"  {r['LABEL_KEC']:<18} {r['KESESUAIAN']:<18} {r['Luas_Ha']:>12,.4f} {r['Persen (%)']:>11.2f}%")
        print(f"  {'':<18} {'Sub-total':<18} {tot:>12,.4f} {'100.00':>11}%")
        print("  " + "-" * 70)

    # ---- C. Export summary to CSV ----
    csv_path = os.path.join(base_dir, "spatial_utilization_conformity_2024_summary.csv")
    # Build a nice CSV with city-wide + per-kecamatan
    rows = []
    for _, r in city_summary.iterrows():
        rows.append({
            "Kecamatan": "KOTA TASIKMALAYA (Total)",
            "Kesesuaian": r["KESESUAIAN"],
            "Luas_Ha": round(r["Luas_Ha"], 4),
            "Persen": round(r["Persen (%)"], 2),
        })
    for _, r in kec_summary.iterrows():
        rows.append({
            "Kecamatan": r["LABEL_KEC"],
            "Kesesuaian": r["KESESUAIAN"],
            "Luas_Ha": round(r["Luas_Ha"], 4),
            "Persen": round(r["Persen (%)"], 2),
        })
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    print(f"\n  ✔ Summary CSV saved to {csv_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
