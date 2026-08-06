# May ghi demo — client xash chay khong man hinh, dat ngay tren box game.
#
# Vi sao phai co image rieng: image server build engine voi `waf configure -d`
# (dedicated), co nay LOAI HAN code client khoi engine. Da do tren binary that
# 2026-08-06: khong co "Usage: record <demoname>", khong co CL_StartDemos_f,
# khong co cl_demo.c. Ghi demo la viec cua client, nen server tu no khong ghi
# duoc — day la image thu hai, build CHINH nguon do nhung KHONG co `-d`.
#
# Duong vao: container server phai bat UDP_GATE_PORT (xem src/server/udpgate.go).
# Ban dung thi engine trong container KHONG mo socket UDP nao ngoai cong media
# ICE, nen may ghi khong co cach nao noi vao.
#
# Vi sao khong dung HLTV (co san trong image server): server bao protocol 49
# (do bang goi `info`), do la protocol rieng cua xash. HLTV la GoldSrc 48.

FROM debian:trixie-slim AS engine

RUN dpkg --add-architecture i386
RUN apt update && apt upgrade -y && apt -y --no-install-recommends install aptitude
RUN aptitude -y --without-recommends install git ca-certificates build-essential gcc-multilib g++-multilib libbsd-dev:i386 libsdl2-dev:i386 libfreetype-dev:i386 libopus-dev:i386 libbz2-dev:i386 libvorbis-dev:i386 libopusfile-dev:i386 libogg-dev:i386

ENV PKG_CONFIG_PATH=/usr/lib/i386-linux-gnu/pkgconfig

WORKDIR /xash

# GHIM dung commit ma goi npm `xash3d-fwgs` cua client web duoc build tu do.
#
# Vi sao quan trong: demo do may ghi tao ra phai MO DUOC bang engine trong
# trinh duyet (do la thu render clip). Do 2026-08-06: build tu nhanh `merged`
# HEAD thi demo phat duoc ~10-15 giay roi dut, trong khi demo do chinh trinh
# duyet ghi thi phat tron. Header giong nhau (IDEM ver=3) nen nhin file khong
# thay gi sai — chi lech o noi dung khung.
#
# So commit lay tu chinh phien ban goi: "1.2.2+commit.7c58854".
ARG ENGINE_COMMIT=7c58854
RUN git clone https://github.com/FWGS/xash3d-fwgs . \
    && git checkout $ENGINE_COMMIT \
    && git submodule update --init --recursive

# KHONG co `-d`: can day du phan client. `--enable-all-renderers` de chac chan
# co ref_soft — may nay khong co GPU, render phan mem la duong duy nhat.
RUN ./waf configure -T release --enable-openmp --enable-all-renderers && ./waf build

# In ra cay ket qua build: duong dan cac .so/binary khac nhau giua cac ban waf,
# doan sai la COPY o duoi hong ma khong biet vi sao.
RUN find build -maxdepth 3 -type f \( -name 'xash*' -o -name '*.so' \) -printf '%p\n'


# client.so cua CS. KHONG dung duoc ban Valve trong goi HLDS: da thu 2026-08-06,
# engine nap duoc roi sap ngay trong BuyPresetManager::Reset -> KeyValues::new
# (client.so:buy_presets.cpp:151). Do la thu vien GoldSrc 2013, ABI khong khop
# xash. cs16-client la ban viet lai ma nguon mo, va chinh la thu ma client web
# dang chay — chi khac o day build ra i386 native thay vi wasm.
FROM debian:trixie-slim AS csclient

RUN dpkg --add-architecture i386
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates build-essential gcc-multilib g++-multilib cmake python3 \
    && apt-get clean

WORKDIR /cs
# Cung ly do: goi npm `cs16-client` la "0.1.2+commit.15278ca" tren repo Velaron.
ARG CSCLIENT_COMMIT=15278ca
RUN git clone https://github.com/Velaron/cs16-client.git . \
    && git checkout $CSCLIENT_COMMIT \
    && git submodule update --init --recursive
# Chi can client: phan server (ReGameDLL/yapb) va menu da co san tu cay xash.
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SERVER=OFF -DBUILD_MAINUI=OFF \
        -DCMAKE_C_FLAGS=-m32 -DCMAKE_CXX_FLAGS=-m32 \
        -DCMAKE_INSTALL_PREFIX=/out \
    && cmake --build build --target install -j"$(nproc)"
RUN find /out -type f -name '*.so' -printf '%p\n'


FROM debian:trixie-slim AS hlds

ARG hlds_build=8308
ARG hlds_url="https://github.com/DevilBoy-eXe/hlds/releases/download/$hlds_build/hlds_build_$hlds_build.zip"

RUN apt-get -y update && apt-get install -y --no-install-recommends ca-certificates curl unzip && apt-get -y clean
WORKDIR /opt/xash
RUN mkdir -p /opt/xash/xashds
RUN curl -sLJO "$hlds_url" \
    && unzip -q "hlds_build_$hlds_build.zip" -d "/opt/xash/hlds_build_$hlds_build" \
    && cp -R "hlds_build_$hlds_build/hlds"/* xashds/ \
    && rm -rf "hlds_build_$hlds_build" "hlds_build_$hlds_build.zip"


FROM debian:trixie-slim AS final

RUN dpkg --add-architecture i386
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsdl2-2.0-0:i386 \
    libgcc-s1:i386 \
    libstdc++6:i386 \
    libgomp1:i386 \
    libfreetype6:i386 \
    libopus0:i386 \
    libopusfile0:i386 \
    libvorbis0a:i386 \
    libvorbisfile3:i386 \
    libogg0:i386 \
    libbz2-1.0:i386 \
    ca-certificates \
    && apt-get clean

RUN groupadd xashrec && useradd -m -g xashrec xashrec

WORKDIR /rec
# Du lieu game (map, model, client.so cua CS) — giong het image server.
COPY --from=hlds /opt/xash/xashds .
# Ca cay build, khong loc: duong dan .so doi giua cac ban waf, chep tron roi
# tim luc chay thi de sua hon la doan sai rồi phai build lai 90 phut.
COPY --from=engine /xash/build /engine-build
# Cung ly do: khong doan duong dan cai dat cua cmake.
COPY --from=csclient /out /csclient-out

COPY docker/cs-web-server-rec/record.sh /rec/record.sh
RUN chmod +x /rec/record.sh && chown -R xashrec:xashrec /rec

USER xashrec
ENV XASH3D_BASEDIR=/rec
ENV LD_LIBRARY_PATH=/rec
# Khong co man hinh, khong co card am thanh.
ENV SDL_VIDEODRIVER=dummy
ENV SDL_AUDIODRIVER=dummy

ENTRYPOINT ["/rec/record.sh"]
