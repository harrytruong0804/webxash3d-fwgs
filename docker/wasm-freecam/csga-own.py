#!/usr/bin/env python3
"""Client doc ban tin CSGAOwn — dan/giap/tien cua MOI nguoi khi phat demo.

Server fork (specmirror.py) guong CurWeapon/AmmoX/Battery/Money cua TUNG nguoi
choi sang may ghi trong ban tin CSGAOwn = [which(1)][owner(1)][payload...] (co
dinh 16 byte). Demo ghi goi tho nen du lieu nam san trong .dem — phia client:

  1. cl_parse.c: nuot CSGAOwn (client dll khong biet no), luu BANG THEO ENTITY.
     PHAI co bang luu chu khong chi phat-khi-nhan: AmmoX/Money chi gui luc gia
     tri DOI — democam sang nguoi dang dung yen thi khong co gi de nhan.
  2. cl_frame.c: khi democam doi nguoi -> phat lai CurWeapon/AmmoX/Battery/Money
     cua nguoi do tu bang. CurWeapon gia (clip=1, tong hop tu weaponmodel) chi
     con la fallback cho demo CU chua co CSGAOwn.

Dung python thay vi .patch: sua bang anchor-replace giong serverfill.py, khong
vo khi csga-client.patch xe dich vai dong (git apply doi context chinh xac).
Chay SAU git apply csga-client.patch (Dockerfile).
"""
import os
import sys

ROOT = os.environ.get("CSGA_ENGINE_ROOT", "/xash")


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


# --- 1. Bang luu + store + replay, dat truoc CL_ParseUserMessage ---
patch(
    "engine/client/cl_parse.c",
    "CL_ParseUserMessage\n\nhandles all user messages\n",
    """CSGA_Own — bang dan/giap/tien theo entity (ban tin CSGAOwn tu server fork)
====================
*/
/* GIU NGUYEN BYTE THO, khong giai ma roi ma hoa lai. Bai hoc 8/8: ban replay
 * dau tach Health ra `int` roi phat lai bang 1 byte, trong khi ban tin that dai
 * 2 byte -> client doc short tu dem 1 byte, tran, ra 0. HUD hien icon ma khong
 * co so, dung hien tuong user bat duoc. Cu chep nguyen payload + do dai roi
 * phat lai y het thi khong con cho nao de doan sai dinh dang. */
#define CSGA_RAWMAX\t8
typedef struct {
\tbyte has;
\tbyte len[6];\t\t\t/* which 1..5; which 2 (AmmoX) di duong rieng ben duoi */
\tbyte raw[6][CSGA_RAWMAX];
\tbyte ammolen[64];\t\t/* moi loai dan mot ban tin -> phai luu rieng tung loai */
\tbyte ammoraw[64][CSGA_RAWMAX];
} csga_own_t;
static csga_own_t csga_own[65];
static int csga_own_view;
static const char *csga_nm[] = { "", "CurWeapon", "AmmoX", "Battery", "Money", "Health" };

void CSGA_OwnStore( const byte *b, int len )
{
\tint which = b[0], owner = b[1];
\tconst byte *p = b + 2;
\tcsga_own_t *o;

\tlen -= 2;
\tif( owner < 1 || owner > 64 || which < 1 || which > 5 || len < 1 )
\t\treturn;
\tif( len > CSGA_RAWMAX )
\t\tlen = CSGA_RAWMAX;
\to = &csga_own[owner];
\to->has = 1;
\t/* DEBUG tam (go sau khi chot khong gian chi so): doi chieu owner voi
\t * [HLKILL] de bat lech chi so — bug trao du lieu A<->B user bat 8/8. */
\tif( cls.demoplayback )
\t\tCon_Printf( "[CSGAOWN] w=%d own=%d view=%d len=%d p0=%d p1=%d\\n", which, owner, csga_own_view, len, p[0], len >= 2 ? p[1] : -1 );

\tif( which == 2 )
\t{
\t\tif( p[0] < 64 )
\t\t{
\t\t\tmemcpy( o->ammoraw[p[0]], p, len );
\t\t\to->ammolen[p[0]] = len;
\t\t}
\t}
\telse
\t{
\t\tmemcpy( o->raw[which], p, len );
\t\to->len[which] = len;
\t}

\t/* dang xem dung nguoi nay -> phat ban tin goc ngay, HUD cap nhat tuc thi */
\tif( owner == csga_own_view && cls.demoplayback )
\t\tCL_DispatchUserMessage( csga_nm[which], len, (void *)p );
}

void CSGA_OwnReplay( int ent )
{
\tcsga_own_t *o;
\tint i, w;

\tcsga_own_view = ent;
\tif( ent < 1 || ent > 64 )
\t\treturn;
\to = &csga_own[ent];
\tif( !o->has )
\t\treturn;

\tif( o->len[1] )
\t\tCL_DispatchUserMessage( csga_nm[1], o->len[1], (void *)o->raw[1] );
\tfor( i = 0; i < 64; i++ )
\t\tif( o->ammolen[i] )
\t\t\tCL_DispatchUserMessage( csga_nm[2], o->ammolen[i], (void *)o->ammoraw[i] );
\tfor( w = 3; w <= 5; w++ )
\t\tif( o->len[w] )
\t\t\tCL_DispatchUserMessage( csga_nm[w], o->len[w], (void *)o->raw[w] );
}

/* Mau da giai ma — CHI de vá banner spectator (xem patch own-banner-health).
 * Luong phat lai cho HUD van la byte tho, khong dung ham nay. */
int CSGA_OwnHealth( int ent )
{
\tcsga_own_t *o;

\tif( ent < 1 || ent > 64 )
\t\treturn 0;
\to = &csga_own[ent];
\tif( o->len[5] < 1 )
\t\treturn 0;
\treturn o->len[5] >= 2 ? ( o->raw[5][0] | ( o->raw[5][1] << 8 )) : o->raw[5][0];
}

int CSGA_OwnHas( int ent )
{
	return ent >= 1 && ent <= 64 && csga_own[ent].has;
}

/*
====================
CL_ParseUserMessage

handles all user messages
""",
    "own-store",
)

# --- 2. Nuot CSGAOwn trong CL_ParseUserMessage (canh hook HLKILL cua patch cu) ---
patch(
    "engine/client/cl_parse.c",
    '\tif( cls.demoplayback && !Q_strcmp( clgame.msg[i].name, "DeathMsg" ) && iSize >= 2 )\n'
    '\t\tCon_Printf( "[HLKILL] killer=%d victim=%d\\n", pbuf[0], pbuf[1] );\n',
    '\tif( cls.demoplayback && !Q_strcmp( clgame.msg[i].name, "DeathMsg" ) && iSize >= 2 )\n'
    '\t\tCon_Printf( "[HLKILL] killer=%d victim=%d\\n", pbuf[0], pbuf[1] );\n'
    '\n'
    '\t/* CSGA: nuot CSGAOwn — client dll khong dang ky no; luu bang theo entity */\n'
    '\tif( !Q_strcmp( clgame.msg[i].name, "CSGAOwn" ) && iSize >= 3 )\n'
    '\t{\n'
    '\t\tCSGA_OwnStore( pbuf, iSize );\n'
    '\t\treturn;\n'
    '\t}\n'
    '\n'
    '\t/* Demo: NUOT bon ban tin dan/giap/tien KHONG nhan tu luong goc — chung la\n'
    '\t * cua nguoi may ghi bam LUC GHI (duong live-mirror + clientdata cua chinh\n'
    '\t * REC), phat len luc xem se DE len bang cua nguoi dang xem (bug user bat\n'
    '\t * 8/8: dan/tien cua zzzz hien khi dang bam nguoi khac). Bang CSGAOwn la\n'
    '\t * nguon DUY NHAT khi phat demo; synth cua ta di duong CL_DispatchUserMessage\n'
    '\t * nen khong bi chan o day. */\n'
    '\tif( cls.demoplayback && ( !Q_strcmp( clgame.msg[i].name, "CurWeapon" )\n'
    '\t\t|| !Q_strcmp( clgame.msg[i].name, "AmmoX" ) || !Q_strcmp( clgame.msg[i].name, "Battery" )\n'
    '\t\t|| !Q_strcmp( clgame.msg[i].name, "Money" ) || !Q_strcmp( clgame.msg[i].name, "ArmorType" )\n'
    '\t\t|| !Q_strcmp( clgame.msg[i].name, "Health" )))\n'
    '\t/* KHONG nuot HideWeapon: no la CONG TAC bat/tat HUD chu khong phai du lieu\n'
    '\t * per-player. Nuot ca goi = nuot luon lenh BO AN -> sung an vinh vien\n'
    '\t * (do 8/8: nuot xong la mat tay sung ngay khi doi cam). */\n'
    '\t\treturn;\n',
    "own-consume",
)

# --- 3. cl_frame.c: phat lai khi democam doi nguoi + tat synth gia khi co data that ---
patch(
    "engine/client/cl_frame.c",
    "\t\t\t\tif( dte )\n"
    "\t\t\t\t{\n"
    "\t\t\t\t\tstatic int dc_last_ent, dc_last_wm = -1;",
    "\t\t\t\t{\n"
    "\t\t\t\t\t/* CSGA: demo moi co bang dan/giap/tien that (CSGAOwn) — doi nguoi\n"
    "\t\t\t\t\t * la phat lai tron bo. Demo cu khong co thi bang rong, vo hai. */\n"
    "\t\t\t\t\textern void CSGA_OwnReplay( int );\n"
    "\t\t\t\t\tstatic int dc_own_view = -1;\n"
    "\t\t\t\t\tif( dc_view != dc_own_view ) { CSGA_OwnReplay( dc_view ); dc_own_view = dc_view; }\n"
    "\t\t\t\t}\n"
    "\t\t\t\tif( dte )\n"
    "\t\t\t\t{\n"
    "\t\t\t\t\tstatic int dc_last_ent, dc_last_wm = -1;",
    "own-replay",
)

# --- 4. CurWeapon gia (clip=1) chi con la fallback ---
patch(
    "engine/client/cl_frame.c",
    "\t\t\t\t\t\t/* wm=0 (chet/khong sung) -> state 0: an crosshair, dung nhu that */\n"
    "\t\t\t\t\t\tCL_DispatchUserMessage( \"CurWeapon\", 3, wbuf );",
    "\t\t\t\t\t\t/* wm=0 (chet/khong sung) -> state 0: an crosshair, dung nhu that.\n"
    "\t\t\t\t\t\t * Co CSGAOwn (demo moi) thi thoi — data that da phat o tren. */\n"
    "\t\t\t\t\t\t{\n"
    "\t\t\t\t\t\t\textern int CSGA_OwnHas( int );\n"
    "\t\t\t\t\t\t\tif( !CSGA_OwnHas( dc_view ))\n"
    "\t\t\t\t\t\t\t\tCL_DispatchUserMessage( \"CurWeapon\", 3, wbuf );\n"
    "\t\t\t\t\t\t}",
    "own-fallback",
)

# --- 5. (GO BO) Banner mau: TUYET DOI khong ghi cl.local.health = 0 ---
# Ban truoc bo chot ">0" de banner theo nguoi xem. SAI NANG: entity_state.health
# LUON = 0 trong demo (da do o ca #13 lan #16), ma engine/renderer an viewmodel +
# crosshair bang dung idiom:
#     if( cl.local.health <= 0 || cl.viewentity != cl.playernum + 1 ) return;
# (thay o cl_game.c:875 CL_DrawCrosshair; renderer R_DrawViewModel giong het).
# => copy health=0 la TU TAY an tay sung. Do chinh la hoi quy "mat tay sung khi
# doi cam" user bat 8/8. Banner mau dung nguoi se giai bang duong KHAC: them
# Health vao specmirror phia server (w=5) roi replay theo view.

# --- 6. DEBUG tam: [DTE] moi giay — do hull/vel/hp/wm cua nguoi dang bam ---
# Chot cau hoi crosshair di/ngoi: neu hull luon 0 va vel luon 0 thi du lieu
# KHONG toi (delta/parse), con neu nhay dung thi loi nam o duong flags->dll.
patch(
    "engine/client/cl_frame.c",
    "\t\t\t\tif( dte )\n"
    "\t\t\t\t{\n"
    "\t\t\t\t\tstatic int dc_last_ent, dc_last_wm = -1;",
    "\t\t\t\tif( dte )\n"
    "\t\t\t\t{\n"
    "\t\t\t\t\tstatic float dc_dbg_t;\n"
    "\t\t\t\t\tif( cl.time - dc_dbg_t > 1.0 )\n"
    "\t\t\t\t\t{\n"
    "\t\t\t\t\t\tdc_dbg_t = (float)cl.time;\n"
    "\t\t\t\t\t\tCon_Printf( \"[DTE] e=%d hull=%d vel=%d hp=%d wm=%d\\n\", dc_view,\n"
    "\t\t\t\t\t\t\tdte->curstate.usehull, (int)VectorLength( dte->curstate.velocity ),\n"
    "\t\t\t\t\t\t\t(int)dte->curstate.health, dte->curstate.weaponmodel );\n"
    "\t\t\t\t\t}\n"
    "\t\t\t\t}\n"
    "\t\t\t\tif( dte )\n"
    "\t\t\t\t{\n"
    "\t\t\t\t\tstatic int dc_last_ent, dc_last_wm = -1;",
    "own-dte-debug",
)

# --- 7. VIEWMODEL: sung cua nguoi dang bam, do ENGINE cap moi frame ---
# User bat quy luat vang: /replay (engine cu, chua nuot untagged) doi cam KHONG
# mat sung — vi luong CurWeapon untagged lam dll tuong MINH cam sung va tu ve.
# Ta nuot luong do (dung, vi no la sung nguoi khac) thi phai CAP LAI chu dong:
# map weaponmodel p_ -> v_ (nhu V_FindViewModelByWeaponModel cua cs16-client)
# roi dat clientdata.viewmodel — cl_pmove copy vao cl.local.viewmodel, cl_view
# ve moi frame => de len ca viec dll NULL gunModel. wm=0 (chet) -> 0 = an sung.
patch(
    "engine/client/cl_frame.c",
    "\t\t\t\t\tint wm = dte->curstate.weaponmodel;\n",
    "\t\t\t\t\tint wm = dte->curstate.weaponmodel;\n"
    "\t\t\t\t\t{\n"
    "\t\t\t\t\t\tstatic int vm_last_wm = -1, vm_last_idx, vm_dbg_wm = -1;\n"
    "\t\t\t\t\t\tif( wm != vm_last_wm )\n"
    "\t\t\t\t\t\t{\n"
    "\t\t\t\t\t\t\tmodel_t *pm2 = wm ? CL_ModelHandle( wm ) : NULL;\n"
    "\t\t\t\t\t\t\tvm_last_idx = 0;\n"
    "\t\t\t\t\t\t\tif( pm2 && pm2->name[0] )\n"
    "\t\t\t\t\t\t\t{\n"
    "\t\t\t\t\t\t\t\tconst char *sub2 = Q_strstr( pm2->name, \"/p_\" );\n"
    "\t\t\t\t\t\t\t\tif( sub2 )\n"
    "\t\t\t\t\t\t\t\t{\n"
    "\t\t\t\t\t\t\t\t\tchar vname[64];\n"
    "\t\t\t\t\t\t\t\t\tint vj;\n"
    "\t\t\t\t\t\t\t\t\tQ_strncpy( vname, pm2->name, sizeof( vname ));\n"
    "\t\t\t\t\t\t\t\t\tvname[sub2 - pm2->name + 1] = 'v';\n"
    "\t\t\t\t\t\t\t\t\tfor( vj = 1; vj < MAX_MODELS; vj++ )\n"
    "\t\t\t\t\t\t\t\t\t{\n"
    "\t\t\t\t\t\t\t\t\t\tmodel_t *mv = CL_ModelHandle( vj );\n"
    "\t\t\t\t\t\t\t\t\t\tif( mv && mv->name[0] && !Q_stricmp( mv->name, vname )) { vm_last_idx = vj; break; }\n"
    "\t\t\t\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t\tvm_last_wm = wm;\n"
    "\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t/* CHI dat khi tim thay v_ model. Dat 0 la EP AN sung — te hon\n"
    "\t\t\t\t\t\t * de dll tu lo (V_CalcSpectatorRefdef cua cs16-client cung map\n"
    "\t\t\t\t\t\t * p_->v_ va se ve neu no tim duoc). */\n"
    "\t\t\t\t\t\tif( vm_last_idx )\n"
    "\t\t\t\t\t\t\tframe->clientdata.viewmodel = vm_last_idx;\n"
    "\t\t\t\t\t\tif( wm != vm_dbg_wm )\n"
    "\t\t\t\t\t\t{\n"
    "\t\t\t\t\t\t\tvm_dbg_wm = wm;\n"
    "\t\t\t\t\t\t\tCon_Printf( \"[VM] wm=%d -> vmidx=%d\\n\", wm, vm_last_idx );\n"
    "\t\t\t\t\t\t}\n"
    "\t\t\t\t\t}\n",
    "own-viewmodel",
)

# --- 8. DUCK: usehull cua nguoi dang bam, dat vao playerstate[playernum] ---
# cl_pmove.c:1027 lay `cl.local.usehull = frame->playerstate[cl.playernum]
# .usehull` — tuc tu the cua CHINH MAY GHI (khan gia bay, khong bao gio ngoi),
# khong phai nguoi dang bam. Ban va cu chi dat clientdata.flags |= FL_DUCKING:
# SAI TRUONG, dll khong bao gio thay => crosshair "ngoi to hon dung" (thuc ra
# la khong phan ung gi, chay theo tu the may ghi).
patch(
    "engine/client/cl_frame.c",
    "\t\t\t\t\t\tif( dte->curstate.usehull == 1 )\n"
    "\t\t\t\t\t\t\tframe->clientdata.flags |= FL_DUCKING;\n",
    "\t\t\t\t\t\tif( dte->curstate.usehull == 1 )\n"
    "\t\t\t\t\t\t\tframe->clientdata.flags |= FL_DUCKING;\n"
    "\t\t\t\t\t\t/* cl_pmove doc usehull tu playerstate cua MAY GHI — dat luon vao\n"
    "\t\t\t\t\t\t * do thi cl.local.usehull moi mang tu the nguoi dang bam. */\n"
    "\t\t\t\t\t\tframe->playerstate[cl.playernum].usehull = dte->curstate.usehull;\n",
    "own-duck",
)

print("csga-own.py: tat ca patch da ap")


# --- 8. BANNER spectator: "<ten> (<mau>)" doc entity_state.health, KHONG doc
# ban tin Health ---
# Do duoc 8/8 tren demo #20: bang csga_own co mau=100 dung, HUD phat lai dung,
# nhung banner van hien "(0)" — vi no lay tu `curstate.health` cua entity chu
# khong phai tu ban tin Health. Server CO nhoi state->health (serverfill.py) ma
# toi client van bang 0, chua ro tac nhan; va sua o client thi khong phai doi
# ca image server nen vong lap kiem chung ngan hon.
# CHI ghi de khi co du lieu that (>0) de khong bao gio tu tay dat mau ve 0.
patch(
    "engine/client/cl_frame.c",
    "\t\t\t\tif( dte )\n"
    "\t\t\t\t{\n"
    "\t\t\t\t\tstatic float dc_dbg_t;\n",
    "\t\t\t\tif( dte )\n"
    "\t\t\t\t{\n"
    "\t\t\t\t\tstatic float dc_dbg_t;\n"
    "\t\t\t\t\t{\n"
    "\t\t\t\t\t\textern int CSGA_OwnHealth( int ent );\n"
    "\t\t\t\t\t\tint csga_hp = CSGA_OwnHealth( dc_view );\n"
    "\t\t\t\t\t\tif( csga_hp > 0 )\n"
    "\t\t\t\t\t\t\tdte->curstate.health = csga_hp;\n"
    "\t\t\t\t\t}\n",
    "own-banner-health",
)
