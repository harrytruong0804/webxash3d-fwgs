FROM debian:trixie-slim AS engine

RUN dpkg --add-architecture i386
RUN apt update && apt upgrade -y && apt -y --no-install-recommends install aptitude
RUN aptitude -y --without-recommends install git ca-certificates build-essential gcc-multilib g++-multilib libbsd-dev:i386 libsdl2-dev:i386 libfreetype-dev:i386 libopus-dev:i386 libbz2-dev:i386 libvorbis-dev:i386 libopusfile-dev:i386 libogg-dev:i386

ENV PKG_CONFIG_PATH=/usr/lib/i386-linux-gnu/pkgconfig

WORKDIR /xash

# ⚠️ NEN ENGINE: fork CUA MINH + GHIM COMMIT.
# Truoc day clone thang `yohimik/xash3d-fwgs` nhanh `merged` — KHONG ghim, KHONG
# phai repo cua minh. Upstream doi mot dong la MOI MO NEO va cua csga-own.py /
# csga-client.patch VO, ma minh khong kiem soat duoc luc nao no doi.
# Toan bo ban va cua CSGA la anchor-replace tren ma nguon nay nen day la rui ro
# that, khong phai gia dinh. Fork + ghim => build hom nay va build sau nay giong
# nhau; muon nang nen thi doi COMMIT o day mot cach co y thuc.
ARG XASH_REPO=https://github.com/harrytruong0804/xash3d-fwgs
ARG XASH_COMMIT=f85aa0c8f7d4
RUN git clone "$XASH_REPO" . && git checkout "$XASH_COMMIT" \
    && git submodule update --init --recursive

# Them lenh server `stuffto` — bao mot client chay mot lenh (svc_stufftext).
# Can de bao may ghi (client) doi muc tieu `follow` giua tran; xem stuffto.py.
# python3 co san vi waf can no.
COPY docker/cs-web-server/stuffto.py /tmp/stuffto.py
RUN python3 /tmp/stuffto.py

# Server gui DU du lieu per-player (velocity/punch/v_angle/fov/health) + co
# fullvis cho may ghi — replay doi camera sang bat ky ai khong phai suy dien.
# Di kem patch delta.lst o stage hlds. Xem serverfill.py.
COPY docker/cs-web-server/serverfill.py /tmp/serverfill.py
RUN python3 /tmp/serverfill.py
# Guong dan/giap/tien sang may ghi. Rieng biet voi serverfill.py vi khac han co
# che: serverfill nhoi truong vao entity_state (doc duoc tu pev), con dan/tien
# KHONG co trong pev — phai nhan ban ban tin MSG_ONE. Xem specmirror.py.
COPY docker/cs-web-server/specmirror.py /tmp/specmirror.py
RUN python3 /tmp/specmirror.py

RUN ./waf configure -T release -d --enable-openmp && ./waf build

FROM golang:1.25.1 AS go

WORKDIR /go
COPY docker/cs-web-server/go.mod go.mod
COPY docker/cs-web-server/go.sum go.sum
RUN go mod download
RUN mkdir -p ../github.com/yohimik/goxash3d-fwgs
RUN cp -r $(go list -m -f '{{.Dir}}' github.com/yohimik/goxash3d-fwgs)/* ../github.com/yohimik/goxash3d-fwgs
RUN echo 'replace github.com/yohimik/goxash3d-fwgs => ../github.com/yohimik/goxash3d-fwgs' >> go.mod

COPY docker/cs-web-server/src/server src/server
COPY --from=engine /xash/build/engine/libxash.a ../github.com/yohimik/goxash3d-fwgs/pkg/libxash.a
COPY --from=engine /xash/build/public/libbuild_vcs.a ../github.com/yohimik/goxash3d-fwgs/pkg/libbuild_vcs.a
COPY --from=engine /xash/build/public/libpublic.a ../github.com/yohimik/goxash3d-fwgs/pkg/libpublic.a
COPY --from=engine /xash/build/3rdparty/libbacktrace/libbacktrace.a ../github.com/yohimik/goxash3d-fwgs/pkg/libbacktrace.a
COPY --from=engine /xash/build/3rdparty/library_suffix/liblibrary_suffix.a ../github.com/yohimik/goxash3d-fwgs/pkg/liblibrary_suffix.a

ENV GOARCH=386
ENV CC="gcc -m32 -D__i386__"
ENV CGO_CFLAGS="-fopenmp -m32 -fno-ipa-cp"
ENV CGO_LDFLAGS="-fopenmp -m32"
RUN go build -o ./xash ./src/server


FROM debian:trixie-slim AS hlds

ARG hlds_build=8308
ARG hlds_url="https://github.com/DevilBoy-eXe/hlds/releases/download/$hlds_build/hlds_build_$hlds_build.zip"

RUN groupadd -r xash && useradd -r -g xash -m -d /opt/xash xash
RUN usermod -a -G games xash

RUN apt-get -y update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    unzip \
    python3 \
    && apt-get -y clean

USER xash
WORKDIR /opt/xash
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN mkdir -p /opt/xash/xashds

RUN curl -sLJO "$hlds_url" \
    && unzip "hlds_build_$hlds_build.zip" -d "/opt/xash/hlds_build_$hlds_build" \
    && cp -R "hlds_build_$hlds_build/hlds"/* xashds/ \
    && rm -rf "hlds_build_$hlds_build" "hlds_build_$hlds_build.zip"

# Khai them truong per-player trong delta.lst (velocity/punch/v_angle/fov/health)
# — nua config cua serverfill.py (stage engine). Xem deltapatch.py.
COPY docker/cs-web-server/deltapatch.py /tmp/deltapatch.py
RUN python3 /tmp/deltapatch.py

# Fix warnings:
# couldn't exec listip.cfg
# couldn't exec banned.cfg
RUN touch /opt/xash/xashds/valve/listip.cfg
RUN touch /opt/xash/xashds/valve/banned.cfg

WORKDIR /opt/xash/xashds

# Copy default config
COPY docker/cs-web-server/configs/valve valve
COPY docker/cs-web-server/configs/cstrike cstrike

FROM --platform=linux/amd64 node:22-alpine AS client

RUN npm install -g pnpm

WORKDIR /client

COPY docker/cs-web-server/package.json docker/cs-web-server/package.json
COPY docker/cs-web-server/wasm/package.json docker/cs-web-server/wasm/package.json
COPY package.json package.json
COPY pnpm-lock.yaml pnpm-lock.yaml
COPY pnpm-workspace.yaml pnpm-workspace.yaml
RUN pnpm install --frozen-lockfile
COPY docker/cs-web-server/vite.config.ts docker/cs-web-server/vite.config.ts
COPY docker/cs-web-server/tsconfig.json docker/cs-web-server/tsconfig.json
COPY docker/cs-web-server/src/client docker/cs-web-server/src/client

WORKDIR /client/docker/cs-web-server

RUN pnpm run build


FROM debian:trixie-slim AS final

ENV XASH3D_BASEDIR=/xashds

RUN dpkg --add-architecture i386
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgcc-s1:i386 \
    libstdc++6:i386 \
    libgomp1:i386 \
    ca-certificates \
    openssl \
    && apt-get clean

RUN groupadd xashds && useradd -m -g xashds xashds
USER xashds
WORKDIR /xashds
ENV LD_LIBRARY_PATH=/xashds

COPY --from=hlds /opt/xash/xashds .
COPY --from=go /go/xash ./xash
COPY --from=client /client/docker/cs-web-server/src/client/dist ./public
COPY --from=client /client/docker/cs-web-server/wasm/node_modules/cs16-client/dist/cstrike/ ./public/cstrike
COPY --from=client /client/docker/cs-web-server/wasm/node_modules/xash3d-fwgs/dist/filesystem_stdio.wasm ./public/filesystem_stdio.wasm
COPY --from=engine /xash/build/filesystem/filesystem_stdio.so ./filesystem_stdio.so
COPY --from=engine "/usr/lib/i386-linux-gnu/libstdc++.so.6" "./libstdc++.so.6"
COPY --from=engine "/usr/lib/i386-linux-gnu/libgcc_s.so.1" "./libgcc_s.so.1"
EXPOSE 27015/udp

# Engine configuration
ENV GAME_DIR="cstrike"
ENV ENGINE_ARGS="-windowed,-game,cstrike"
ENV ENGINE_CONSOLE="_vgui_menus 0"

# Library paths
ENV CLIENT_WASM_PATH="cstrike/cl_dlls/client_emscripten_wasm32.wasm"
ENV SERVER_WASM_PATH="cstrike/dlls/cs_emscripten_wasm32.wasm"
ENV MENU_WASM_PATH="cstrike/cl_dlls/menu_emscripten_wasm32.wasm"
ENV EXTRAS_PATH="cstrike/extras.pk3"
ENV FILESYSTEM_WASM_PATH="filesystem_stdio.wasm"
ENV DYNAMIC_LIBRARIES="dlls/cs_emscripten_wasm32.wasm,/rodir/filesystem_stdio.wasm"
ENV FILES_MAP="dlls/cs_emscripten_wasm32.wasm:cstrike/dlls/cs_emscripten_wasm32.wasm,/rodir/filesystem_stdio.wasm:filesystem_stdio.wasm"

# Start server
ENTRYPOINT ["./xash", "+ip", "0.0.0.0", "-port", "27015", "-game", "cstrike"]

# Default start parameters
CMD ["+map de_dust2", "+maxplayers", "16"]