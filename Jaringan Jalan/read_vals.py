import dbf

table1 = dbf.Table('jaringan_jalan.dbf')
table1.open(mode=dbf.READ_ONLY)
fungsi_vals1 = set()
for r in table1:
    fungsi_vals1.add(r.fungsi.strip() if hasattr(r, 'fungsi') and r.fungsi else None)

table2 = dbf.Table('As_Jalan.dbf')
table2.open(mode=dbf.READ_ONLY)
fungsi_vals2 = set()
for r in table2:
    fungsi_vals2.add(r.fungsi.strip() if hasattr(r, 'fungsi') and r.fungsi else None)

print("jaringan_jalan.dbf Fungsi values:", fungsi_vals1)
print("As_Jalan.dbf Fungsi values:", fungsi_vals2)
