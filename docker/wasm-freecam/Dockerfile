# Engine wasm CO VA — dung RIENG cho cong cu dung clip highlight.
#
# KHONG dung cho csga.cc. Trang chinh van chay goi npm goc; ban nay chi de mo
# demo roi chon goc quay.
#
# Hai cho va, deu mot dong, va deu NAM NGOAI duong giai ma goi tin:
#
#  1. pfnIsSpectateOnly() tra them cls.demoplayback.
#     Client dll (cs16-client) chi xu ly spec_mode / doi nguoi bam CUC BO khi ham
#     nay dung; neu khong no `return` va cho server quyet — ma xem demo thi lam gi
#     co server. Day la ly do bam nut spec_mode luc phat lai khong an gi.
#
#  2. Bo CL_DemoInterpolateAngles() khi dang phat demo.
#     Ham do ep cl.viewangles theo dung goc da ghi, moi khung hinh — tuc la khoa
#     cung huong nhin. Bo di thi xoay chuot duoc.
#
# VI SAO KHONG gan thang cls.spectator = true (cach hien nhien hon): cl_parse.c
# re nhanh theo chinh co do khi doc svc_clientdata (doc vao cls.spectator_state
# thay vi du lieu thuong). Demo cua minh ghi o luong "khong phai spectator", bat
# co len la engine doc sai cau truc -> svc_bad, dung nhu luc thu cho may ghi vao
# bang hltv 1. Hai cho tren nam ngoai duong do nen khong dung toi.

FROM emscripten/emsdk:4.0.23 AS build

ARG XASH_REPO=https://github.com/yohimik/xash3d-fwgs
ARG XASH_BRANCH=merged

WORKDIR /xash3d-fwgs
RUN git clone --branch "$XASH_BRANCH" --single-branch "$XASH_REPO" . \
    && git submodule update --init --recursive

# TOAN BO ban va client gop trong MOT file patch (xuat tu git diff cay build
# da nghiem thu 2026-08-07). Truoc day la chuoi sed + democam.py — cang nhieu
# buoc cang de lech nhau; patch la anh chup chinh xac cay da chay that.
# Noi dung: IsSpectateOnly+demoplayback, bo khoa goc khi phat demo, democam
# (+REC-skip), hook [HLKILL], dong bo spectator-state cho client dll (iuser/
# CurWeapon/SetFOV/duck-speed-punch tu du lieu that cua server fork).
COPY docker/wasm-freecam/csga-client.patch /tmp/csga-client.patch
RUN git apply --check /tmp/csga-client.patch && git apply /tmp/csga-client.patch

ENV EMCC_CFLAGS="-s USE_SDL=2"
RUN emconfigure ./waf configure --emscripten && \
    emmake ./waf build && \
    emmake ./waf install --destdir ./out
RUN mv ./out/xash.js ./out/raw.js && ls -la ./out

# Stage cuoi chi chua ket qua, de `docker build --output type=local` lay ra.
FROM scratch AS artifact
COPY --from=build /xash3d-fwgs/out /
