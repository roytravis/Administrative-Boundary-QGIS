import struct
import sys

def read_dbf_header(filename):
    with open(filename, 'rb') as f:
        header = f.read(32)
        if len(header) < 32:
            return
        
        num_records = struct.unpack('<I', header[4:8])[0]
        header_len = struct.unpack('<H', header[8:10])[0]
        record_len = struct.unpack('<H', header[10:12])[0]
        
        fields = []
        f.seek(32)
        while True:
            field_desc = f.read(32)
            if len(field_desc) < 32 or field_desc[0] == 0x0D:
                break
            name = field_desc[:11].decode('ascii', errors='ignore').strip('\x00')
            fields.append(name)
            
        print(f"File: {filename}")
        print(f"Num records: {num_records}")
        print(f"Fields: {fields}")

read_dbf_header('jaringan_jalan.dbf')
read_dbf_header('As_Jalan.dbf')
