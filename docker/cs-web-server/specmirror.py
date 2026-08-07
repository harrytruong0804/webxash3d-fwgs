#!/usr/bin/env python3
"""Guong dan/giap/tien cua nguoi bi bam sang MAY GHI (spectator fullvis).

VAN DE (do 2026-08-07): xem lai tran o goc nhin thu nhat thi o dan, o mau, o tien
deu la O RONG. Nguoi choi that thi day du. Nguyen nhan nam o game dll:

    CBasePlayer::UpdateClientData()          // ReGameDLL player.cpp
        SendAmmoUpdate();                    // -> MSG_ONE, pev  (CHINH MINH)
        m_rgpPlayerItems[i]->UpdateClientData(this);
        MESSAGE_BEGIN(MSG_ONE, gmsgFlashBattery, nullptr, pev);

Tat ca deu MSG_ONE toi chinh chu so huu va tinh tu KHO DO CUA NGUOI NHAN.
Spectator kho do rong -> khong nhan gi -> HUD trong. KHONG phai client hong.

VI SAO KHONG LAM NHU health/fov: cach da dung hom qua la engine doc pev roi nhoi
vao entity_state (serverfill.py). Khong ap dung duoc o day — `entvars_t` KHONG CO
truong dan nao ca (chi armorvalue). So dan nam trong m_rgAmmo / m_iClip thuoc
vung rieng cua cs.so, engine khong voi toi.

CACH NAY: nhan ban CHINH ban tin goc sang client dang bam nguoi do. Server da
biet ai bam ai — ReGameDLL dat `pev->iuser2` = chi so nguoi bi bam (player.cpp:
`GetObserverMode() == OBS_IN_EYE && pev->iuser2 == playerIndex`). Loc them
`setinfo fullvis 1` nen CHI may ghi nhan duoc: nguoi choi thuong khong khai co
do, khong ai xem trom dan cua doi phuong. Cung mo hinh tin cay voi FCL_FULLVIS.

LOI: demo ghi goi THO nen clip highlight tu dong co dan/giap/tien, KHONG phai
build lai engine wasm phia client.
"""
import os
import sys

ROOT = os.environ.get("CSGA_ENGINE_ROOT", "/xash/engine")


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


# --- 1. Ham guong + co danh dau, dat ngay truoc pfnMessageBegin ---
patch(
    "server/sv_game.c",
    "static void GAME_EXPORT pfnMessageBegin( int msg_dest, int msg_num, const float *pOrigin, edict_t *ed )\n{",
    "/* ==== CSGA: guong dan/giap/tien sang may ghi dang bam nguoi do ==== */\n"
    "static qboolean csga_mirror_msg;\n"
    "\n"
    "/* PHAI goi TRUOC SV_Multicast: ham do MSG_Clear( &sv.multicast ) o cuoi. */\n"
    "static void CSGA_MirrorToWatchers( void )\n"
    "{\n"
    "\tsv_client_t\t*cl;\n"
    "\tedict_t\t*owner = svgame.msg_ent;\n"
    "\tint\ti, oidx;\n"
    "\n"
    "\tif( !csga_mirror_msg || !SV_IsValidEdict( owner ))\n"
    "\t\treturn;\n"
    "\n"
    "\toidx = NUM_FOR_EDICT( owner );\n"
    "\n"
    "\tfor( i = 0, cl = svs.clients; i < svs.maxclients; i++, cl++ )\n"
    "\t{\n"
    "\t\tif( cl->state != cs_spawned || !cl->edict || cl->edict == owner )\n"
    "\t\t\tcontinue;\n"
    "\t\tif( FBitSet( cl->flags, FCL_FAKECLIENT ))\n"
    "\t\t\tcontinue;\n"
    "\t\t// ReGameDLL: iuser2 = chi so nguoi dang bi bam\n"
    "\t\tif( cl->edict->v.iuser2 != oidx )\n"
    "\t\t\tcontinue;\n"
    "\t\t// chi may ghi (setinfo fullvis 1) — khong lo dan cua doi phuong\n"
    "\t\tif( !Q_atoi( Info_ValueForKey( cl->userinfo, \"fullvis\" )))\n"
    "\t\t\tcontinue;\n"
    "\t\tMSG_WriteBits( &cl->netchan.message, MSG_GetData( &sv.multicast ), MSG_GetNumBitsWritten( &sv.multicast ));\n"
    "\t}\n"
    "}\n"
    "/* ==== het guong ==== */\n"
    "\n"
    "static void GAME_EXPORT pfnMessageBegin( int msg_dest, int msg_num, const float *pOrigin, edict_t *ed )\n{",
    "mirror-fn",
)

# --- 2. Danh dau ban tin can guong (theo TEN, khong theo so: so do gamedll cap) ---
patch(
    "server/sv_game.c",
    "\tMSG_WriteCmdExt( &sv.multicast, msg_num, NS_SERVER, svgame.msg_name );\n",
    "\tMSG_WriteCmdExt( &sv.multicast, msg_num, NS_SERVER, svgame.msg_name );\n"
    "\n"
    "\t// CSGA: bon ban tin mang du lieu rieng cua nguoi choi. Doi chieu theo TEN\n"
    "\t// vi so hieu do gamedll cap luc dang ky, khac nhau giua cac ban mod.\n"
    "\tcsga_mirror_msg = ( msg_dest == MSG_ONE || msg_dest == MSG_ONE_UNRELIABLE ) && svgame.msg_name\n"
    "\t\t&& ( !Q_strcmp( svgame.msg_name, \"CurWeapon\" ) || !Q_strcmp( svgame.msg_name, \"AmmoX\" )\n"
    "\t\t|| !Q_strcmp( svgame.msg_name, \"Battery\" ) || !Q_strcmp( svgame.msg_name, \"Money\" ));\n",
    "mirror-mark",
)

# --- 3. Goi guong ngay truoc khi ban tin goc duoc phat ---
patch(
    "server/sv_game.c",
    "\tsvgame.msg_dest = bound( MSG_BROADCAST, svgame.msg_dest, MSG_SPEC );\n"
    "\n"
    "\tSV_Multicast( svgame.msg_dest, org, svgame.msg_ent, true, false );",
    "\tsvgame.msg_dest = bound( MSG_BROADCAST, svgame.msg_dest, MSG_SPEC );\n"
    "\n"
    "\tCSGA_MirrorToWatchers();\n"
    "\n"
    "\tSV_Multicast( svgame.msg_dest, org, svgame.msg_ent, true, false );",
    "mirror-call",
)

print("specmirror.py: tat ca patch da ap")
