#!/bin/sh
# Khoi dong may ghi demo: dung xong bo do rồi chay client xash khong man hinh.
#
# Ba viec duoi day deu la LOI DA GAP THAT khi thu 2026-08-06, khong phai phong xa:
#
# 1. Thu vien engine phai DE LEN goi HLDS. Goi HLDS 8308 mang theo ban
#    filesystem_stdio.so cua nam 2013; de no thang thi engine chet voi
#    "FS_LoadProgs: can't find GetFSAPI entry point".
# 2. Phai XOA libstdc++.so.6 / libgcc_s.so.1 cua goi HLDS. LD_LIBRARY_PATH tro
#    vao /rec nen ban co 2013 duoc uu tien hon ban he thong, va libxash.so moi
#    doi CXXABI_1.3.9 khong co trong do.
# 3. client.so phai la ban cs16-client, khong phai ban Valve — ban Valve sap
#    ngay trong BuyPresetManager::Reset.
#
# Gom luc KHOI DONG chu khong phai luc build vi duong dan ket qua cua waf/cmake
# doi giua cac ban; doan sai o Dockerfile thi 90 phut sau moi biet.
set -e

find /engine-build -maxdepth 4 -type f -name '*.so' -exec cp -f {} /rec/ \;
rm -f /rec/libstdc++.so.6 /rec/libgcc_s.so.1

mkdir -p /rec/cstrike/cl_dlls
find /csclient-out -type f -name 'client*.so' -exec cp -f {} /rec/cstrike/cl_dlls/ \;
# xash tim theo ten co hau to kien truc truoc, roi moi den ten tran — de ca hai.
if [ -f /rec/cstrike/cl_dlls/client_i386.so ] && [ ! -f /rec/cstrike/cl_dlls/client.so ]; then
    cp -f /rec/cstrike/cl_dlls/client_i386.so /rec/cstrike/cl_dlls/client.so
fi

BIN=$(find /engine-build -maxdepth 4 -type f \( -name 'xash3d' -o -name 'xash' \) | head -1)
if [ -z "$BIN" ]; then
    echo "record.sh: KHONG tim thay binary client trong /engine-build:"
    find /engine-build -maxdepth 3 -type f | head -40
    exit 1
fi
cp -f "$BIN" /rec/xash-client
chmod +x /rec/xash-client

echo "record.sh: binary=$BIN"
echo "record.sh: client dll: $(ls /rec/cstrike/cl_dlls/ 2>/dev/null | tr '\n' ' ')"

# -ref null: ban build co san libref_null.so — renderer rong. May nay khong ai
# nhin khung hinh, chi can engine chay de ghi luong mang vao demo, nen ve ra
# pixel la dot CPU vo ich tren box 1 nhan.
exec /rec/xash-client \
    -game cstrike \
    -ref soft \
    -width 320 -height 240 \
    -noborder \
    "$@"
