#!/bin/sh
# Khoi dong may ghi: gom cac thu vien engine ve /rec roi chay client xash.
#
# Cay build duoc chep nguyen ven vao /engine-build vi duong dan .so doi giua cac
# ban waf. Buoc gom nay chay luc KHOI DONG chu khong phai luc build, de sua duoc
# ma khong phai doi 90 phut build lai.
set -e

for f in $(find /engine-build -maxdepth 4 -type f -name '*.so'); do
    cp -n "$f" /rec/ 2>/dev/null || true
done
BIN=$(find /engine-build -maxdepth 4 -type f -name 'xash' -o -maxdepth 4 -type f -name 'xash3d' | head -1)
if [ -z "$BIN" ]; then
    echo "record.sh: KHONG tim thay binary client trong /engine-build:"
    find /engine-build -maxdepth 3 -type f | head -40
    exit 1
fi
cp -n "$BIN" /rec/xash-client 2>/dev/null || true
chmod +x /rec/xash-client

echo "record.sh: binary=$BIN"
echo "record.sh: thu vien da gom:"
ls /rec/*.so 2>/dev/null | head -20

# Man hinh nho nhat co the: render phan mem tren box 1 nhan, moi pixel deu tra
# bang CPU ma khong ai nhin khung hinh nay ca — chi can engine chay de no ghi
# duoc luong mang vao demo.
exec /rec/xash-client \
    -game cstrike \
    -ref soft \
    -width 320 -height 240 \
    -noborder \
    -nomouse \
    "$@"
