#!/usr/bin/env python3
"""Guong dan/giap/tien cua MOI nguoi choi sang may ghi, CO GAN NHAN chu so huu.

VAN DE (do 2026-08-07): xem lai tran o goc nhin thu nhat thi o dan, o mau, o tien
deu la O RONG; nguoi choi that thi day du. Nguyen nhan o game dll:

    CBasePlayer::UpdateClientData()          // ReGameDLL player.cpp
        SendAmmoUpdate();                    // -> MSG_ONE, pev  (CHINH MINH)
        MESSAGE_BEGIN(MSG_ONE, gmsgFlashBattery, nullptr, pev);

Tat ca deu MSG_ONE toi chinh chu so huu va tinh tu KHO DO CUA NGUOI NHAN.
Spectator kho do rong -> khong nhan gi. KHONG phai client hien thi hong.

VI SAO KHONG LAM NHU health/fov: serverfill.py doc pev roi nhoi vao entity_state.
Khong ap dung duoc — `entvars_t` KHONG CO truong dan nao (chi armorvalue); so dan
nam trong m_rgAmmo/m_iClip thuoc vung rieng cua cs.so, engine khong voi toi.

VI SAO PHAI GAN NHAN CHU SO HUU (bai hoc, user hoi moi lo ra):
Ban dau chi guong du lieu cua nguoi may ghi DANG BAM (loc theo pev->iuser2).
Sai, vi luc QUAY va luc DUNG CLIP bam hai nguoi khac nhau:
  - daemon bam theo NGUOI VUA GIET (`stuffto REC follow`), phan ung sau moi pha;
  - autoclip5 chon NGUOI CAN N roi bam suot ca khung, ke ca 15 giay TRUOC pha
    kill dau — quang ma luc quay may ghi gan nhu chac chan dang bam nguoi khac.
Ma `CurWeapon(state,id,clip)` / `AmmoX(index,count)` KHONG mang thong tin chu so
huu, nen guong tat ca ma khong gan nhan thi client khong biet cua ai, cai sau de
cai truoc. => boc trong ban tin rieng `CSGAOwn` = [which][chi so nguoi][payload].

Chi client khai `setinfo fullvis 1` (tuc may ghi) nhan duoc — nguoi choi thuong
khong khai co do nen khong ai xem trom dan doi phuong. Cung mo hinh tin cay voi
FCL_FULLVIS san co.

Demo ghi goi THO nen ca bang du lieu nay nam trong .dem; phia client (patch
wasm-freecam) giu bang theo tung entity va phat lai khi democam doi nguoi.
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


# --- 1. Bien trang thai + ham guong, dat ngay truoc pfnMessageBegin ---
patch(
    "server/sv_game.c",
    "static void GAME_EXPORT pfnMessageBegin( int msg_dest, int msg_num, const float *pOrigin, edict_t *ed )\n{",
    "/* ==== CSGA: guong dan/giap/tien sang may ghi, co gan nhan chu so huu ==== */\n"
    "static int csga_which;\t\t// 1=CurWeapon 2=AmmoX 3=Battery 4=Money, 0=khong guong\n"
    "static int csga_pay_off;\t// vi tri byte dau payload trong sv.multicast\n"
    "static int csga_own_num;\t// so hieu ban tin CSGAOwn (0 = chua dang ky)\n"
    "\n"
    "/* PHAI goi TRUOC SV_Multicast: ham do MSG_Clear( &sv.multicast ) o cuoi. */\n"
    "static void CSGA_MirrorToWatchers( void )\n"
    "{\n"
    "\tsv_client_t\t*cl;\n"
    "\tedict_t\t*owner = svgame.msg_ent;\n"
    "\tbyte\t\tbuf[MAX_USERMSG_LENGTH];\n"
    "\tsizebuf_t\tsb;\n"
    "\tint\t\ti, paylen;\n"
    "\tbyte\t\t*pay;\n"
    "\n"
    "\tif( !csga_which || !csga_own_num || csga_own_num == svc_bad || !SV_IsValidEdict( owner ))\n"
    "\t\treturn;\n"
    "\n"
    "\tpaylen = MSG_GetNumBytesWritten( &sv.multicast ) - csga_pay_off;\n"
    "\tif( paylen <= 0 || paylen > 64 )\n"
    "\t\treturn;\t// bon ban tin nay deu vai byte; dai bat thuong thi bo qua\n"
    "\tpay = MSG_GetData( &sv.multicast ) + csga_pay_off;\n"
    "\n"
    "\tMSG_InitExt( &sb, \"CSGAOwn\", buf, sizeof( buf ), -1 );\n"
    "\tMSG_WriteCmdExt( &sb, csga_own_num, NS_SERVER, \"CSGAOwn\" );\n"
    "\tMSG_WriteWord( &sb, paylen + 2 );\t// ban tin bien: do dai payload di truoc\n"
    "\tMSG_WriteByte( &sb, csga_which );\n"
    "\tMSG_WriteByte( &sb, NUM_FOR_EDICT( owner ));\n"
    "\tMSG_WriteBytes( &sb, pay, paylen );\n"
    "\n"
    "\tfor( i = 0, cl = svs.clients; i < svs.maxclients; i++, cl++ )\n"
    "\t{\n"
    "\t\tif( cl->state != cs_spawned || !cl->edict )\n"
    "\t\t\tcontinue;\n"
    "\t\tif( FBitSet( cl->flags, FCL_FAKECLIENT ))\n"
    "\t\t\tcontinue;\n"
    "\t\t// chi may ghi (setinfo fullvis 1) — khong lo dan cua doi phuong\n"
    "\t\tif( !Q_atoi( Info_ValueForKey( cl->userinfo, \"fullvis\" )))\n"
    "\t\t\tcontinue;\n"
    "\t\tif( MSG_GetNumBytesLeft( &cl->netchan.message ) < paylen + 24 )\n"
    "\t\t\tcontinue;\n"
    "\t\tMSG_WriteBits( &cl->netchan.message, MSG_GetData( &sb ), MSG_GetNumBitsWritten( &sb ));\n"
    "\n"
    "\t\t// Kem ban tin GOC khi client nay dang bam DUNG nguoi so huu: client cu\n"
    "\t\t// (chua hieu CSGAOwn) van hien duoc dan/giap ngay o che do xem truc\n"
    "\t\t// tiep. Duong gan nhan o tren danh cho replay bam nguoi bat ky.\n"
    "\t\tif( cl->edict->v.iuser2 == NUM_FOR_EDICT( owner ) && cl->edict != owner )\n"
    "\t\t\tMSG_WriteBits( &cl->netchan.message, MSG_GetData( &sv.multicast ), MSG_GetNumBitsWritten( &sv.multicast ));\n"
    "\t}\n"
    "}\n"
    "/* ==== het guong ==== */\n"
    "\n"
    "static void GAME_EXPORT pfnMessageBegin( int msg_dest, int msg_num, const float *pOrigin, edict_t *ed )\n{",
    "mirror-fn",
)

# --- 2. Danh dau ban tin can guong (theo TEN: so hieu do gamedll cap) ---
patch(
    "server/sv_game.c",
    "\tMSG_WriteCmdExt( &sv.multicast, msg_num, NS_SERVER, svgame.msg_name );\n",
    "\tMSG_WriteCmdExt( &sv.multicast, msg_num, NS_SERVER, svgame.msg_name );\n"
    "\n"
    "\t// CSGA: bon ban tin mang du lieu rieng cua nguoi choi. Doi chieu theo TEN\n"
    "\t// vi so hieu do gamedll cap luc dang ky, khac nhau giua cac ban mod.\n"
    "\tcsga_which = 0;\n"
    "\tif(( msg_dest == MSG_ONE || msg_dest == MSG_ONE_UNRELIABLE ) && svgame.msg_name )\n"
    "\t{\n"
    "\t\tif( !Q_strcmp( svgame.msg_name, \"CurWeapon\" )) csga_which = 1;\n"
    "\t\telse if( !Q_strcmp( svgame.msg_name, \"AmmoX\" )) csga_which = 2;\n"
    "\t\telse if( !Q_strcmp( svgame.msg_name, \"Battery\" )) csga_which = 3;\n"
    "\t\telse if( !Q_strcmp( svgame.msg_name, \"Money\" )) csga_which = 4;\n"
    "\t}\n",
    "mirror-mark",
)

# --- 3. Ghi lai vi tri payload (sau cmd byte va word do dai neu co) ---
patch(
    "server/sv_game.c",
    "\tsvgame.msg_realsize = 0;\n"
    "\tsvgame.msg_dest = msg_dest;\n"
    "\tsvgame.msg_ent = ed;\n",
    "\tsvgame.msg_realsize = 0;\n"
    "\tsvgame.msg_dest = msg_dest;\n"
    "\tsvgame.msg_ent = ed;\n"
    "\n"
    "\t// CSGA: payload bat dau NGAY DAY — sau cmd byte, va sau word do dai neu la\n"
    "\t// ban tin bien. Chot moc o day de khoi phai doan cau truc luc guong.\n"
    "\tcsga_pay_off = MSG_GetNumBytesWritten( &sv.multicast );\n",
    "mirror-payoff",
)

# --- 4. Goi guong ngay truoc khi ban tin goc duoc phat ---
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

# --- 5. Dang ky ban tin CSGAOwn ngay lan dau gamedll dang ky ban tin cua no ---
# PHAI xong TRUOC khi client dau tien noi vao: danh sach ban tin di trong signon,
# dang ky muon thi client khong biet so hieu -> nhan duoc cung khong hieu.
patch(
    "server/sv_game.c",
    "\tif( sv.state == ss_active )\n"
    "\t{\n"
    "\t\t// tell the client about new user message\n"
    "\t\tSV_SendUserReg( &sv.multicast, &svgame.msg[i] );\n"
    "\t\tSV_Multicast( MSG_ALL, NULL, NULL, false, false );\n"
    "\t}\n"
    "\n"
    "\treturn svgame.msg[i].number;",
    "\tif( sv.state == ss_active )\n"
    "\t{\n"
    "\t\t// tell the client about new user message\n"
    "\t\tSV_SendUserReg( &sv.multicast, &svgame.msg[i] );\n"
    "\t\tSV_Multicast( MSG_ALL, NULL, NULL, false, false );\n"
    "\t}\n"
    "\n"
    "\t// CSGA: bam theo ngay lan dang ky dau tien cua gamedll (xem specmirror.py)\n"
    "\tif( !csga_own_num && Q_strcmp( pszName, \"CSGAOwn\" ))\n"
    "\t{\n"
    "\t\tcsga_own_num = svc_bad;\t\t// chan de quy truoc khi goi lai\n"
    "\t\tcsga_own_num = pfnRegUserMsg( \"CSGAOwn\", -1 );\n"
    "\t}\n"
    "\n"
    "\treturn svgame.msg[i].number;",
    "mirror-reg",
)

print("specmirror.py: tat ca patch da ap")
