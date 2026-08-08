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

# ⚠️ NEN ENGINE: fork CUA MINH + GHIM COMMIT.
# Truoc day clone thang `yohimik/xash3d-fwgs` nhanh `merged` — KHONG ghim, KHONG
# phai repo cua minh. Upstream doi mot dong la MOI MO NEO va cua csga-own.py /
# csga-client.patch VO, ma minh khong kiem soat duoc luc nao no doi.
# Toan bo ban va cua CSGA la anchor-replace tren ma nguon nay nen day la rui ro
# that, khong phai gia dinh. Fork + ghim => build hom nay va build sau nay giong
# nhau; muon nang nen thi doi COMMIT o day mot cach co y thuc.
ARG XASH_REPO=https://github.com/harrytruong0804/xash3d-fwgs
ARG XASH_COMMIT=f85aa0c8f7d4

WORKDIR /xash3d-fwgs
RUN git clone "$XASH_REPO" . && git checkout "$XASH_COMMIT" \
    && git submodule update --init --recursive

# TOAN BO ban va client gop trong MOT file patch (xuat tu git diff cay build
# da nghiem thu 2026-08-07). Truoc day la chuoi sed + democam.py — cang nhieu
# buoc cang de lech nhau; patch la anh chup chinh xac cay da chay that.
# Noi dung: IsSpectateOnly+demoplayback, bo khoa goc khi phat demo, democam
# (+REC-skip), hook [HLKILL], dong bo spectator-state cho client dll (iuser/
# CurWeapon/SetFOV/duck-speed-punch tu du lieu that cua server fork).
COPY docker/wasm-freecam/csga-client.patch /tmp/csga-client.patch
RUN git apply --check /tmp/csga-client.patch && git apply /tmp/csga-client.patch
# Doc ban tin CSGAOwn (dan/giap/tien moi nguoi tu server fork specmirror):
# bang luu theo entity + phat lai khi democam doi nguoi. Anchor-replace kieu
# python (nhu serverfill.py) de khong vo khi csga-client.patch xe dich.
COPY docker/wasm-freecam/csga-own.py /tmp/csga-own.py
RUN CSGA_ENGINE_ROOT=/xash3d-fwgs python3 /tmp/csga-own.py

ENV EMCC_CFLAGS="-s USE_SDL=2"
RUN emconfigure ./waf configure --emscripten && \
    emmake ./waf build && \
    emmake ./waf install --destdir ./out
RUN mv ./out/xash.js ./out/raw.js && ls -la ./out

# Stage cuoi chi chua ket qua, de `docker build --output type=local` lay ra.
FROM scratch AS artifact
COPY --from=build /xash3d-fwgs/out /
