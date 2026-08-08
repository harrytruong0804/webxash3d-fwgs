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

LO HONG THU HAI — "anh chup ban dau" (do tren demo #18, 2026-08-08):
gamedll chi gui Health/Money/AmmoX KHI GIA TRI DOI. Nguoi choi vao truoc may
ghi ~17 giay nen ban tin mau=100 luc spawn da bay qua truoc khi may ghi noi
vao; ai khong dinh dan thi bang du lieu RONG suot tran. Demo #18 chi co DUNG
MOT ban tin w=5 va la cua chinh may ghi. Chua bang cach cho engine CACHE ban
tin cuoi cua tung nguoi roi phat lai (keyframe) cho client fullvis luc vao va
moi 5 giay sau do. Chi tiet o khoi 1 va 6.
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
#
# LO HONG "ANH CHUP BAN DAU" (do tren demo #18, 2026-08-08): Health/Money/AmmoX
# chi duoc gamedll gui KHI GIA TRI DOI. Nguoi choi vao truoc may ghi ~17 giay,
# nen ban tin mau=100 luc spawn da bay qua TRUOC khi may ghi noi vao -> bang du
# lieu cua nguoi do RONG suot ca tran neu ho khong dinh dan. Demo #18 chi co
# DUNG MOT ban tin w=5, va la cua chinh may ghi.
#
# Chua bang KEYFRAME: engine tu CACHE ban tin cuoi cua tung nguoi (khoa = chi so
# nguoi + loai; rieng AmmoX khoa them theo chi so dan vi moi loai dan mot ban
# tin), roi phat lai TOAN BO cho client fullvis luc no vao va dinh ky sau do.
# Nho vay may ghi vao luc nao cung dung duoc, va demo tu lanh o moi diem.
#
# VI SAO PHAI RAI RA NHIEU KHUNG: mot anh chup day du la ~130 ban tin (16 nguoi
# x [4 loai + vai loai dan]) ~ 2.3KB. Nhoi het vao `cl->netchan.message` trong
# mot khung la TRAN — va SV_SendClientMessages xu ly tran bang SV_DropClient,
# tuc tu tay da may ghi ra. Nen dung con tro chay, moi khung vai ban tin.
MIRROR_C = """/* ==== CSGA: guong dan/giap/tien sang may ghi, co gan nhan chu so huu ==== */
#define CSGA_OWN_SIZE\t16\t// [which][chi so nguoi][payload...] — CO DINH
#define CSGA_MAXPL\t33\t// chi so edict cua nguoi choi: 1..32
#define CSGA_NWHICH\t6\t// which chay 1..5
#define CSGA_PER_PL\t36\t// 4 o thuong + 32 o dan, cho mot nguoi
#define CSGA_SPACE\t( CSGA_MAXPL * CSGA_PER_PL )
#define CSGA_KEY_SEC\t5.0\t// bao lau phat lai anh chup mot lan
#define CSGA_PER_TICK\t4\t// so ban tin toi da nhoi trong mot khung

static int csga_which;\t\t// 1=CurWeapon 2=AmmoX 3=Battery 4=Money 5=Health, 0=khong guong
static int csga_pay_off;\t// vi tri byte dau payload trong sv.multicast
static int csga_own_num;\t// so hieu ban tin CSGAOwn (0 = chua dang ky)

// Bang anh chup. AmmoX de rieng vi moi chi so dan la mot ban tin doc lap —
// gop chung vao csga_snap thi loai dan sau de mat loai dan truoc.
static byte\tcsga_snap[CSGA_MAXPL][CSGA_NWHICH][CSGA_OWN_SIZE - 2];
static byte\tcsga_snaplen[CSGA_MAXPL][CSGA_NWHICH];
static byte\tcsga_ammo[CSGA_MAXPL][32];
static byte\tcsga_ammoseen[CSGA_MAXPL][32];
static int\tcsga_cursor[CSGA_MAXPL];\t// con tro rai anh chup cho tung client; -1 = xong
static byte\tcsga_seen_cl[CSGA_MAXPL];\t// client nay da duoc phat anh chup lan dau chua
static double\tcsga_next_key;

static void CSGA_WriteOwn( sv_client_t *cl, int which, int owner, const byte *pay, int paylen )
{
\tbyte\t\tbuf[MAX_USERMSG_LENGTH];
\tsizebuf_t\tsb;
\tint\t\ti;

\tif( paylen <= 0 || paylen > CSGA_OWN_SIZE - 2 )
\t\treturn;
\tif( MSG_GetNumBytesLeft( &cl->netchan.message ) < CSGA_OWN_SIZE + 64 )
\t\treturn;

\tMSG_InitExt( &sb, "CSGAOwn", buf, sizeof( buf ), -1 );
\tMSG_WriteCmdExt( &sb, csga_own_num, NS_SERVER, "CSGAOwn" );
\t// KHONG dung ban tin bien: truong do dai duoc ma hoa KHAC NHAU theo giao
\t// thuc — cl_parse.c: proto GoldSrc doc BYTE, xash goc doc WORD. Client web
\t// chay proto GoldSrc (49); ghi word thi no doc lech 1 byte va TOAN BO luong
\t// goi sau do sai, client dung im khong bao loi (may ghi chet cam 2026-08-08).
\tMSG_WriteByte( &sb, which );
\tMSG_WriteByte( &sb, owner );
\tMSG_WriteBytes( &sb, pay, paylen );
\tfor( i = paylen; i < CSGA_OWN_SIZE - 2; i++ )
\t\tMSG_WriteByte( &sb, 0 );\t// dem cho du kich thuoc co dinh

\tMSG_WriteBits( &cl->netchan.message, MSG_GetData( &sb ), MSG_GetNumBitsWritten( &sb ));
}

static void CSGA_SnapStore( int owner, int which, const byte *pay, int paylen )
{
\tif( owner < 1 || owner >= CSGA_MAXPL || paylen <= 0 || paylen > CSGA_OWN_SIZE - 2 )
\t\treturn;
\tif( which == 2 )\t// AmmoX = [chi so dan][so vien]
\t{
\t\tif( paylen >= 2 && pay[0] < 32 )
\t\t{
\t\t\tcsga_ammo[owner][pay[0]] = pay[1];
\t\t\tcsga_ammoseen[owner][pay[0]] = 1;
\t\t}
\t\treturn;
\t}
\tif( which < 1 || which >= CSGA_NWHICH )
\t\treturn;
\tmemcpy( csga_snap[owner][which], pay, paylen );
\tcsga_snaplen[owner][which] = paylen;
}

// Gui MOT o trong khong gian anh chup. Tra ve true neu that su co gui.
static qboolean CSGA_SendSlot( sv_client_t *cl, int idx )
{
\tint\tp = idx / CSGA_PER_PL;
\tint\tk = idx % CSGA_PER_PL;
\tbyte\tax[2];

\tif( p < 1 || p >= CSGA_MAXPL )
\t\treturn false;

\tif( k < 4 )\t// o thuong: k 0,1,2,3 <-> which 1,3,4,5 (2 la AmmoX, di duong rieng)
\t{
\t\tint w = ( k == 0 ) ? 1 : k + 2;
\t\tif( !csga_snaplen[p][w] )
\t\t\treturn false;
\t\tCSGA_WriteOwn( cl, w, p, csga_snap[p][w], csga_snaplen[p][w] );
\t\treturn true;
\t}

\tif( !csga_ammoseen[p][k - 4] )
\t\treturn false;
\tax[0] = k - 4;
\tax[1] = csga_ammo[p][k - 4];
\tCSGA_WriteOwn( cl, 2, p, ax, 2 );
\treturn true;
}

/* PHAI goi TRUOC SV_Multicast: ham do MSG_Clear( &sv.multicast ) o cuoi. */
static void CSGA_MirrorToWatchers( void )
{
\tsv_client_t\t*cl;
\tedict_t\t*owner = svgame.msg_ent;
\tint\t\ti, paylen, ownidx;
\tbyte\t\t*pay;

\tif( !csga_which || !csga_own_num || csga_own_num == svc_bad || !SV_IsValidEdict( owner ))
\t\treturn;

\tpaylen = MSG_GetNumBytesWritten( &sv.multicast ) - csga_pay_off;
\tif( paylen <= 0 || paylen > CSGA_OWN_SIZE - 2 )
\t\treturn;\t// bon ban tin nay deu vai byte; dai bat thuong thi bo qua
\tpay = MSG_GetData( &sv.multicast ) + csga_pay_off;
\townidx = NUM_FOR_EDICT( owner );

\t// Luu vao anh chup TRUOC — phai luu ke ca khi chua co may ghi nao noi vao,
\t// vi dung cai lo hong ban dau la o cho do.
\tCSGA_SnapStore( ownidx, csga_which, pay, paylen );

\tfor( i = 0, cl = svs.clients; i < svs.maxclients; i++, cl++ )
\t{
\t\tif( cl->state != cs_spawned || !cl->edict )
\t\t\tcontinue;
\t\tif( FBitSet( cl->flags, FCL_FAKECLIENT ))
\t\t\tcontinue;
\t\t// chi may ghi (setinfo fullvis 1) — khong lo dan cua doi phuong
\t\tif( !Q_atoi( Info_ValueForKey( cl->userinfo, "fullvis" )))
\t\t\tcontinue;
\t\tCSGA_WriteOwn( cl, csga_which, ownidx, pay, paylen );

\t\t// Kem ban tin GOC khi client nay dang bam DUNG nguoi so huu: client cu
\t\t// (chua hieu CSGAOwn) van hien duoc dan/giap ngay o che do xem truc
\t\t// tiep. Duong gan nhan o tren danh cho replay bam nguoi bat ky.
\t\tif( cl->edict->v.iuser2 == ownidx && cl->edict != owner )
\t\t{
\t\t\tif( MSG_GetNumBytesLeft( &cl->netchan.message ) >= paylen + 24 )
\t\t\t\tMSG_WriteBits( &cl->netchan.message, MSG_GetData( &sv.multicast ), MSG_GetNumBitsWritten( &sv.multicast ));
\t\t}
\t}
}

/* Goi MOI KHUNG tu SV_SendClientMessages. Rai anh chup cho client fullvis. */
void CSGA_KeyframeTick( void );	// khai bao truoc: tranh -Wmissing-prototypes
void CSGA_KeyframeTick( void )
{
\tsv_client_t\t*cl;
\tint\t\ti, sent;
\tqboolean\tdue;

\tif( !csga_own_num || csga_own_num == svc_bad )
\t\treturn;

\tdue = ( host.realtime >= csga_next_key );
\tif( due )
\t\tcsga_next_key = host.realtime + CSGA_KEY_SEC;

\t// Nguoi da roi di thi xoa bang, keo o cua ho bi nguoi vao sau dung nham.
\tif( due )
\t{
\t\tfor( i = 1; i < CSGA_MAXPL; i++ )
\t\t{
\t\t\tif( i <= svs.maxclients && svs.clients[i - 1].state == cs_spawned )
\t\t\t\tcontinue;
\t\t\tmemset( csga_snaplen[i], 0, sizeof( csga_snaplen[i] ));
\t\t\tmemset( csga_ammoseen[i], 0, sizeof( csga_ammoseen[i] ));
\t\t}
\t}

\tfor( i = 0, cl = svs.clients; i < svs.maxclients && i < CSGA_MAXPL; i++, cl++ )
\t{
\t\tif( cl->state != cs_spawned || FBitSet( cl->flags, FCL_FAKECLIENT ) ||
\t\t\t!Q_atoi( Info_ValueForKey( cl->userinfo, "fullvis" )))
\t\t{
\t\t\tcsga_seen_cl[i] = 0;
\t\t\tcsga_cursor[i] = -1;
\t\t\tcontinue;
\t\t}

\t\tif( due || !csga_seen_cl[i] )
\t\t{
\t\t\tcsga_seen_cl[i] = 1;
\t\t\tcsga_cursor[i] = CSGA_PER_PL;\t// bo qua nguoi 0 (world)
\t\t}
\t\tif( csga_cursor[i] < 0 )
\t\t\tcontinue;

\t\tsent = 0;
\t\twhile( csga_cursor[i] < CSGA_SPACE && sent < CSGA_PER_TICK )
\t\t{
\t\t\tif( MSG_GetNumBytesLeft( &cl->netchan.message ) < CSGA_OWN_SIZE + 64 )
\t\t\t\tbreak;\t// het cho — cho khung sau, KHONG duoc de tran
\t\t\tif( CSGA_SendSlot( cl, csga_cursor[i] ))
\t\t\t\tsent++;
\t\t\tcsga_cursor[i]++;
\t\t}
\t\tif( csga_cursor[i] >= CSGA_SPACE )
\t\t\tcsga_cursor[i] = -1;
\t}
}
/* ==== het guong ==== */

"""

patch(
    "server/sv_game.c",
    "static void GAME_EXPORT pfnMessageBegin( int msg_dest, int msg_num, const float *pOrigin, edict_t *ed )\n{",
    MIRROR_C
    + "static void GAME_EXPORT pfnMessageBegin( int msg_dest, int msg_num, const float *pOrigin, edict_t *ed )\n{",
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
    "\t\t// Health (w=5): banner spectator phai hien MAU CUA NGUOI DANG BAM.\n"
    "\t\t// entity_state.health = 0 o MOI demo (do #13 va #16) nen khong the\n"
    "\t\t// lay tu do; va TUYET DOI khong duoc de client ghi cl.local.health=0\n"
    "\t\t// — engine an viewmodel+crosshair bang `cl.local.health <= 0`.\n"
    "\t\telse if( !Q_strcmp( svgame.msg_name, \"Health\" )) csga_which = 5;\n"
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
    "\t\tcsga_own_num = pfnRegUserMsg( \"CSGAOwn\", CSGA_OWN_SIZE );\n"
    "\t}\n"
    "\n"
    "\treturn svgame.msg[i].number;",
    "mirror-reg",
)


# --- 6. Goi keyframe MOI KHUNG ---
# Khai bao prototype ngay tai cho goi thay vi sua header: mot moc, khong dung
# den file .h nao — it be mat va de doc lai khi upstream doi.
patch(
    "server/sv_frame.c",
    "\tSV_UpdateToReliableMessages ();\n",
    "\tSV_UpdateToReliableMessages ();\n"
    "\n"
    "\t// CSGA: rai lai anh chup dan/giap/tien/mau cho may ghi (xem specmirror.py)\n"
    "\t{ extern void CSGA_KeyframeTick( void ); CSGA_KeyframeTick(); }\n",
    "mirror-tick",
)

print("specmirror.py: tat ca patch da ap")
