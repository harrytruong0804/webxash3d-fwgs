#!/usr/bin/env python3
"""Server gui DU du lieu per-player de replay dung moi goc nhin.

VI SAO: demo chi chua clientdata (goc nhin that, sung, giat, zoom, tu the) cua
NGUOI DANG DUOC BAM luc quay — kenh svc_clientdata la 1-dich. Nguoi khac chi co
entity_state. Replay doi camera sang ho la phai suy dien tung mang (banner, sung,
crosshair, pitch...) — moi mang thieu la mot bug (chuoi bug user bat 2026-08-07).
Quyet dinh: sua TAN NGUON — server gui that, client khoi doan.

entity_state_t co san cho: velocity, fov, health, vuser1/vuser2 (vec3 du phong).
delta.lst (config, Dockerfile sua) khai them cac truong nay cho player; client
tu hoc format moi qua svc_deltatable nen KHONG vo client cu. Nhung cs.so (game
dll dong) khong DO du lieu vao do — engine do ho ngay sau pfnAddToFullPack:

    velocity  = van toc (crosshair no khi chay)
    vuser1    = punchangle (giat sung)
    vuser2    = v_angle (GOC NHIN THAT — het suy tu blending)
    fov       = zoom (AWP/Scout)
    health    = mau (banner spectator)

Kem: co FCL_FULLVIS — client khai `setinfo fullvis 1` (chi may ghi REC dung)
duoc BO cat PVS rieng minh: demo chua moi nguoi moi luc, nguoi choi that van
bi cat binh thuong (khong lo du lieu wallhack). Thay the sv_novis toan cuc.
"""
import sys

ROOT = "/xash/engine"


def patch(path, find, replace, label):
    p = f"{ROOT}/{path}"
    s = open(p).read()
    if replace in s:
        print(f"  [{label}] da co, bo qua")
        return
    if find not in s:
        sys.exit(f"KHONG TIM THAY moc cho [{label}] trong {path}")
    s = s.replace(find, replace, 1)
    open(p, "w").write(s)
    print(f"  [{label}] xong")


# --- 1. Co FCL_FULLVIS (bit 30 — xa vung bit dang dung) ---
patch(
    "server/server.h",
    "#define FCL_HLTV_PROXY\tBIT( 8 )\t// this is a proxy for a HLTV client (spectator)",
    "#define FCL_HLTV_PROXY\tBIT( 8 )\t// this is a proxy for a HLTV client (spectator)\n"
    "#define FCL_FULLVIS\tBIT( 30 )\t// CSGA: client (may ghi) nhan MOI entity, bo cat PVS",
    "fcl-fullvis",
)

# --- 2. Nhan co tu userinfo luc connect (canh pattern hltv co san) ---
patch(
    "server/sv_client.c",
    '\t\tif( Q_atoi( Info_ValueForKey( cl->userinfo, "hltv" )))\n'
    "\t\t\tSetBits( cl->flags, FCL_HLTV_PROXY );",
    '\t\tif( Q_atoi( Info_ValueForKey( cl->userinfo, "hltv" )))\n'
    "\t\t\tSetBits( cl->flags, FCL_HLTV_PROXY );\n\n"
    '\t\tif( Q_atoi( Info_ValueForKey( cl->userinfo, "fullvis" )))\n'
    "\t\t\tSetBits( cl->flags, FCL_FULLVIS );",
    "userinfo-fullvis",
)

# --- 3. Ap co: client fullvis bo cat PVS (chi rieng no) ---
patch(
    "server/sv_frame.c",
    "\tsvgame.dllFuncs.pfnSetupVisibility( pViewEnt, pClient, &clientpvs, &clientphs );\n"
    "\tif( !clientpvs ) fullvis = true;",
    "\tsvgame.dllFuncs.pfnSetupVisibility( pViewEnt, pClient, &clientpvs, &clientphs );\n"
    "\tif( !clientpvs ) fullvis = true;\n\n"
    "\t{\n"
    "\t\t// CSGA: may ghi (userinfo fullvis=1) nhan het entity — demo du du lieu\n"
    "\t\t// de replay doi camera sang bat ky ai. Nguoi choi thuong van bi cat PVS.\n"
    "\t\tsv_client_t *fvcl = SV_ClientFromEdict( pClient, true );\n"
    "\t\tif( fvcl && FBitSet( fvcl->flags, FCL_FULLVIS ))\n"
    "\t\t\tfullvis = true;\n"
    "\t}",
    "apply-fullvis",
)

# --- 4. Do du lieu that vao entity_state cua player (cs.so khong tu do) ---
patch(
    "server/sv_frame.c",
    "\t\tif( svgame.dllFuncs.pfnAddToFullPack( state, e, ent, pClient, sv.hostflags, player, pset ))\n"
    "\t\t{\n"
    "\t\t\t// to prevent adds it twice through portals\n"
    "\t\t\tSETVISBIT( ents->sended, e );",
    "\t\tif( svgame.dllFuncs.pfnAddToFullPack( state, e, ent, pClient, sv.hostflags, player, pset ))\n"
    "\t\t{\n"
    "\t\t\t// to prevent adds it twice through portals\n"
    "\t\t\tSETVISBIT( ents->sended, e );\n\n"
    "\t\t\tif( player )\n"
    "\t\t\t{\n"
    "\t\t\t\t// CSGA: do du lieu replay can — delta.lst da khai cac truong nay\n"
    "\t\t\t\t// cho entity_state_player_t (xem serverfill.py dau file).\n"
    "\t\t\t\tVectorCopy( ent->v.velocity, state->velocity );\n"
    "\t\t\t\tVectorCopy( ent->v.punchangle, state->vuser1 );\n"
    "\t\t\t\tVectorCopy( ent->v.v_angle, state->vuser2 );\n"
    "\t\t\t\tstate->fov = ent->v.fov;\n"
    "\t\t\t\tstate->health = ent->v.health;\n"
    "\t\t\t}",
    "state-fill",
)

print("serverfill.py: tat ca patch da ap")
