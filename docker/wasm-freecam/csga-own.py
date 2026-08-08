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

int CSGA_OwnHealth( int ent );	/* dinh nghia ben duoi */

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
\t\t/* In DU 4 byte dau: voi CurWeapon thi SO DAN TRONG BANG nam o byte THU BA
\t\t * (state, id, clip). Ban dau chi in p0/p1 nen do "ban ma dan khong doi"
\t\t * bang mot cong cu mu dung cho can nhin (8/8). AmmoX la dan DU TRU, chi
\t\t * doi khi thay bang — khong phai thu tut moi phat ban. */
\t\tCon_Printf( "[CSGAOWN] w=%d own=%d view=%d len=%d p0=%d p1=%d p2=%d p3=%d\\n", which, owner, csga_own_view, len,
\t\t\tp[0], len >= 2 ? p[1] : -1, len >= 3 ? p[2] : -1, len >= 4 ? p[3] : -1 );

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

\t/* Banner doc g_PlayerExtraInfo[g_iUser2].health — mot BANG, khong phai doc
\t * lai moi khung nhu cum HUD goc trai. Neu chi bom luc doi cam thi banner
\t * dong bang o gia tri CO LUC DO: keyframe rai theo con tro nen nguoi thu hai
\t * toi SAU luc doi cam -> banner cua ho ket o 0 (do 8/8 tren demo #20).
\t * Nen bom NGAY khi nhan duoc mau, cho dung nguoi do. */
\tif( which == 5 && cls.demoplayback )
\t{
\t\tbyte sh2[2];
\t\tint hp = CSGA_OwnHealth( owner );
\t\tif( hp > 0 )
\t\t{
\t\t\tsh2[0] = (byte)hp;
\t\t\tsh2[1] = (byte)owner;
\t\t\tCL_DispatchUserMessage( "SpecHealth2", 2, (void *)sh2 );
\t\t}
\t}
}

int CSGA_OwnHealth( int ent );	/* dinh nghia ben duoi */

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

\t/* Banner "<ten> (<mau>)" doc g_PlayerExtraInfo[i].health (cs16-client
\t * hud/spectator_gui.cpp). Co HAI ban tin ghi vao mang do:
\t *   SpecHealth  = [mau]            -> g_PlayerExtraInfo[g_iUser2].health
\t *   SpecHealth2 = [mau][chi so]    -> g_PlayerExtraInfo[client].health
\t * PHAI dung SpecHealth2: luc phat demo, g_iUser2 la nguoi MAY GHI bam luc
\t * quay, khac nguoi democam dang bam — gui SpecHealth la ghi dung gia tri
\t * vao SAI O (do 8/8: banner van "(0)"). SpecHealth2 chi dinh duoc o.
\t * Gui cho MOI nguoi co du lieu, khong chi nguoi dang bam, de doi cam sang
\t * ai cung dung ngay. */
\t{
\t\tint pi;
\t\tfor( pi = 1; pi <= 64; pi++ )
\t\t{
\t\t\tbyte sh2[2];
\t\t\tint hp = CSGA_OwnHealth( pi );
\t\t\tif( hp <= 0 )
\t\t\t\tcontinue;
\t\t\tsh2[0] = (byte)hp;
\t\t\tsh2[1] = (byte)pi;
\t\t\tCL_DispatchUserMessage( "SpecHealth2", 2, (void *)sh2 );
\t\t}
\t}
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
    # Nuot lai "Health" (thu nghiem 8/8 da xong): cum mau khong hien la do
    # IsSpectateOnly, KHONG phai do thieu kich hoat — bo nuot van khong ra icon.
    # Gio cong da mo, neu khong nuot thi ban tin Health cua CHINH MAY GHI se de
    # len mau cua nguoi dang bam.
    '\t\t|| !Q_strcmp( clgame.msg[i].name, "Health" )\n'

    # SpecHealth: BANNER spectator "<ten> (<mau>)" doc RIENG ban tin nay — khong
    # phai Health, cung khong phai entity_state.health (do 8/8: da ep
    # curstate.health = 100 ma banner van "(0)"). Ban ghi lai mang mau cua nguoi
    # MAY GHI bam luc quay, khac nguoi luc replay bam, nen phai nuot.
    '\t\t|| !Q_strcmp( clgame.msg[i].name, "SpecHealth" )\n'
    '\t\t|| !Q_strcmp( clgame.msg[i].name, "SpecHealth2" )))\n'
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
    "\t\t\t\t\t\tCon_Printf( \"[DTE] e=%d hull=%d vel=%d hp=%d wm=%d | cd: vel=%d duck=%d fov=%d\\n\",\n"
    "\t\t\t\t\t\t\tdc_view, dte->curstate.usehull, (int)VectorLength( dte->curstate.velocity ),\n"
    "\t\t\t\t\t\t\t(int)dte->curstate.health, dte->curstate.weaponmodel,\n"
    "\t\t\t\t\t\t\t(int)VectorLength( frame->clientdata.velocity ),\n"
    "\t\t\t\t\t\t\t( frame->clientdata.flags & FL_DUCKING ) ? 1 : 0,\n"
    "\t\t\t\t\t\t\t(int)frame->clientdata.fov );\n"
    "\t\t\t\t\t\t/* Do cao goc nhin: NGOI thi thap hon ~18 don vi. Day la cach\n"
    "\t\t\t\t\t\t * DUY NHAT khong the cai de biet hull=1 that su la ngoi hay\n"
    "\t\t\t\t\t\t * dung — gia dinh chua bao gio kiem cua ta (8/8). */\n"
    "\t\t\t\t\t\tCon_Printf( \"[Z] hull=%d org_z=%d view_z=%d\\n\", dte->curstate.usehull,\n"
    "\t\t\t\t\t\t\t(int)dte->origin[2], (int)( dte->origin[2] + frame->clientdata.view_ofs[2] ));\n"
    "\t\t\t\t\t\t#if 0\n"
    "\t\t\t\t\t\tCon_Printf( \"[DTE] e=%d hull=%d vel=%d hp=%d wm=%d\\n\", dc_view,\n"
    "\t\t\t\t\t\t\tdte->curstate.usehull, (int)VectorLength( dte->curstate.velocity ),\n"
    "\t\t\t\t\t\t\t(int)dte->curstate.health, dte->curstate.weaponmodel );\n"
    "\t\t\t\t\t\t#endif\n"
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
    "\t\t\t\t\t\t/* FL_ONGROUND: may ghi la spectator BAY nen co nay khong bao gio\n"
    "\t\t\t\t\t\t * bat. Ma ammo.cpp chan CA NHANH NGOI bang chinh no:\n"
    "\t\t\t\t\t\t *   if( flags & FL_ONGROUND || !(wflags & ACCURACY_AIR) ) { ngoi *0.5 }\n"
    "\t\t\t\t\t\t *   else iDistance *= 2;\n"
    "\t\t\t\t\t\t * => thieu no thi ngoi khong bao gio duoc tinh, con luon an *2.\n"
    "\t\t\t\t\t\t * Nguoi dang bam dung tren dat (van toc doc = 0 va khong roi) nen\n"
    "\t\t\t\t\t\t * dat co la dung voi thuc te ta dang mo phong. */\n"
    "\t\t\t\t\t\tframe->clientdata.flags |= FL_ONGROUND;\n"
    "\t\t\t\t\t\t/* cl_pmove doc usehull tu playerstate cua MAY GHI — dat luon vao\n"
    "\t\t\t\t\t\t * do thi cl.local.usehull moi mang tu the nguoi dang bam. */\n"
    "\t\t\t\t\t\tframe->playerstate[cl.playernum].usehull = dte->curstate.usehull;\n"
    "\t\t\t\t\t\t/* VAN TOC cho do rong tam ngam. cs16-client cs_wpn/cs_weapons.cpp:\n"
    "\t\t\t\t\t\t *   g_iPlayerFlags  = from->client.flags;\n"
    "\t\t\t\t\t\t *   g_flPlayerSpeed = from->client.velocity.Length();\n"
    "\t\t\t\t\t\t * ca hai deu lay tu clientdata — tuc cua MAY GHI. Chi ghi de co\n"
    "\t\t\t\t\t\t * FL_DUCKING ma bo van toc thi nhanh \"chay nhanh -> gian x1.5\"\n"
    "\t\t\t\t\t\t * (ammo.cpp) van an theo may ghi — con bot bay va bi day\n"
    "\t\t\t\t\t\t * +moveleft moi 120s de chong autokick. Do 8/8: ngoi 22px > dung\n"
    "\t\t\t\t\t\t * 16px, nguoc han le thuong (ngoi phai *0.5). */\n"
    "\t\t\t\t\t\tVectorCopy( dte->curstate.velocity, frame->clientdata.velocity );\n"
    "\t\t\t\t\t\t/* BANNER \"<ten> (<mau>)\": dll doc muc tieu dang bam tu iuser2 cua\n"
    "\t\t\t\t\t\t * CHINH NO, ma trong demo do la nguoi MAY GHI bam luc quay — khac\n"
    "\t\t\t\t\t\t * nguoi democam dang bam, nen no tra mau cua o sai (do 8/8: ep\n"
    "\t\t\t\t\t\t * curstate.health=100 va phat lai SpecHealth deu khong len so).\n"
    "\t\t\t\t\t\t * Keo iuser2 ve dung nguoi dang bam. */\n"
    "\t\t\t\t\t\tframe->playerstate[cl.playernum].iuser2 = dc_view;\n"
    "\t\t\t\t\t\t/* WEAPONDATA ngay tai KHUNG PHAN TICH — nhoi o predicted-from\n"
    "\t\t\t\t\t\t * (muc 13) chua toi cho dll doc: do [XH] van thay he so x1.4\n"
    "\t\t\t\t\t\t * cua che do BAN LOAT Glock khi ngoi (khe 17.5 = 8*1.4*1.375+2,\n"
    "\t\t\t\t\t\t * dung 13 = 8*1.375+2). m_iWeaponState rac lam GetWeaponAccuracy\n"
    "\t\t\t\t\t\t * Flags tra bo co ban loat: them x1.4 va MAT ACCURACY_DUCK. */\n"
    "\t\t\t\t\t\t{\n"
    "\t\t\t\t\t\t\textern int CSGA_OwnCurWeapon( int ent, int *st, int *id, int *clip );\n"
    "\t\t\t\t\t\t\tint st2, id2, clip2;\n"
    "\t\t\t\t\t\t\tif( CSGA_OwnCurWeapon( dc_view, &st2, &id2, &clip2 ))\n"
    "\t\t\t\t\t\t\t{\n"
    "\t\t\t\t\t\t\t\tmemset( frame->weapondata, 0, sizeof( frame->weapondata ));\n"
    "\t\t\t\t\t\t\t\tif( id2 >= 0 && id2 < MAX_LOCAL_WEAPONS )\n"
    "\t\t\t\t\t\t\t\t{\n"
    "\t\t\t\t\t\t\t\t\tframe->weapondata[id2].m_iId = id2;\n"
    "\t\t\t\t\t\t\t\t\tframe->weapondata[id2].m_iClip = clip2;\n"
    "\t\t\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t\t\tframe->clientdata.m_iId = id2;\n"
    "\t\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t/* MAU CANH GIAP: cs16-client KHONG hook ban tin ten \"Health\" —\n"
    "\t\t\t\t\t\t * do bang ten ban tin trong client wasm: co AmmoX/Battery/\n"
    "\t\t\t\t\t\t * CurWeapon/Money/ScoreInfo/SpecHealth, KHONG co Health. Mau cua\n"
    "\t\t\t\t\t\t * nguoi choi that di qua clientdata.health chu khong qua ban tin,\n"
    "\t\t\t\t\t\t * nen moi lenh CL_DispatchUserMessage(\"Health\") deu roi vao hu\n"
    "\t\t\t\t\t\t * khong. Ghi thang vao day.\n"
    "\t\t\t\t\t\t * Ban va cu ghi vao day roi MAT TAY SUNG — nhung loi la o GIA TRI\n"
    "\t\t\t\t\t\t * (lay tu entity_state.health, luon = 0) chu khong o cho ghi:\n"
    "\t\t\t\t\t\t * engine an viewmodel bang `cl.local.health <= 0`. Gio lay mau\n"
    "\t\t\t\t\t\t * that tu bang csga_own va CHI ghi khi > 0. */\n"
    "\t\t\t\t\t\t{\n"
    "\t\t\t\t\t\t\textern int CSGA_OwnHealth( int ent );\n"
    "\t\t\t\t\t\t\tint hp2 = CSGA_OwnHealth( dc_view );\n"
    "\t\t\t\t\t\t\tif( hp2 > 0 )\n"
    "\t\t\t\t\t\t\t{\n"
    "\t\t\t\t\t\t\t\tframe->clientdata.health = hp2;\n"
    "\t\t\t\t\t\t\t\t/* client_data_t KHONG co truong mau (engine/cdll_int.h) nen\n"
    "\t\t\t\t\t\t\t\t * dll khong lay mau tu do. No doc entity cua CHINH MINH.\n"
    "\t\t\t\t\t\t\t\t * Cung khuon mau da sua duoc loi ngoi/dung: ghi vao\n"
    "\t\t\t\t\t\t\t\t * playerstate[cl.playernum] chu khong vao entity dang bam. */\n"
    "\t\t\t\t\t\t\t\tframe->playerstate[cl.playernum].health = hp2;\n"
    "\t\t\t\t\t\t\t\t/* SO MAU canh giap bi chan boi BIT SUIT, khong phai boi gia\n"
    "\t\t\t\t\t\t\t\t * tri mau — cs16-client cl_dll/health.cpp:\n"
    "\t\t\t\t\t\t\t\t *   if( gHUD.m_iWeaponBits & (1<<WEAPON_SUIT) ) <ve so>\n"
    "\t\t\t\t\t\t\t\t * m_iWeaponBits lay tu client_data_t.iWeaponBits, ma\n"
    "\t\t\t\t\t\t\t\t * spectator co weapons = 0 -> cong dong, du m_iHealth dung.\n"
    "\t\t\t\t\t\t\t\t * WEAPON_SUIT = 31 trong SDK. */\n"
    "\t\t\t\t\t\t\t\tframe->clientdata.weapons |= ( 1U << 31 );\n"
    "\t\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t}\n",
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

# --- 9. TRA pfnIsSpectateOnly() VE FALSE khi phat demo ---
# csga-client.patch cho ham nay tra them `cls.demoplayback` de client dll chiu
# xu ly doi nguoi bam CUC BO. Nhung cs16-client cl_dll/health.cpp:
#     if( !(gHUD.m_iHideHUDDisplay & HIDEHUD_HEALTH) && !gEngfuncs.IsSpectateOnly() )
# => co gia tri true la TAT HAN cum mau goc trai duoi. Mat 5 vong di sua du lieu
# phia sau mot cai cong do CHINH MINH dong (8/8).
# Da do: bo `cls.demoplayback` thi cum mau hien dung (icon + va so), va `democam`
# VAN doi nguoi binh thuong — ban va do nay thua vi ta doi cam TRONG ENGINE.
patch(
    "engine/client/cl_game.c",
    "\treturn (cls.spectator != 0) || cls.demoplayback;",
    "\treturn (cls.spectator != 0);\t/* KHONG them demoplayback: xem csga-own.py muc 9 */",
    "own-spectate-only",
)


# --- 10. pfnIsLocal: coi NGUOI DANG BAM la "cuc bo" khi phat demo ---
# cs16-client cl_dll/events/event_*.cpp:
#     if( EV_IsLocal( idx ) ) { ++g_iShotsFired; EV_MuzzleFlash(); ... }
# Luc phat demo, `idx` la nguoi BAN (entity khac) con cl.playernum la may ghi,
# nen dieu kien LUON SAI: `g_iShotsFired` khong bao gio tang, ma ammo.cpp chi
# NO tam ngam khi bien do tang — con lai thi CO. Dung trieu chung "ban ma tam
# ngam khong no ra co vao" (user bao 8/8).
#
# Day la he qua cua mo hinh da chon: ta cho dll TIN rang client cuc bo CHINH LA
# nguoi dang bam (vi CS 1.6 khong co duong nao chuyen dan/tien cua nguoi bi bam
# sang spectator). Da chon mo hinh do thi phai nhat quan ca o day, khong thi
# moi thu khac dung ma rieng hieu ung sung lai chay theo may ghi.
#
# `playernum` la chi so 0-based; `democam_target` la chi so ENTITY (1-based).
patch(
    "engine/client/cl_game.c",
    "static int GAME_EXPORT pfnIsLocal( int playernum )\n"
    "{\n"
    "\tif( playernum == cl.playernum )\n",
    "static int GAME_EXPORT pfnIsLocal( int playernum )\n"
    "{\n"
    "\textern int democam_target;\t/* xem csga-own.py muc 10 */\n"
    "\tif( cls.demoplayback && democam_target > 0 && playernum == democam_target - 1 )\n"
    "\t\treturn true;\n"
    "\tif( playernum == cl.playernum )\n",
    "own-islocal",
)

# --- 11. Cho code vu khi cua dll CHAY khi phat demo spectator ---
# cl_pmove.c:
#     if( cls.state != ca_active || cls.spectator ) return;
#     ...
#     clgame.dllFuncs.pfnPostRunCmd( from, to, &cmd, runfuncs, *time, random_seed );
# `pfnPostRunCmd` -> HUD_PostRunCmd -> HUD_WeaponsPostThink, la NOI DUY NHAT gan
#     g_iPlayerFlags  = from->client.flags;
#     g_flPlayerSpeed = from->client.velocity.Length();
# ma ammo.cpp dung de quyet dinh do rong tam ngam (ngoi *0.5, chay nhanh *1.5,
# tren khong *2). Demo cua may ghi la demo SPECTATOR nen ham thoat ngay dong dau
# => hai bien do KHONG BAO GIO duoc cap nhat. Do la ly do nhoi FL_DUCKING va
# van toc vao clientdata deu vo hieu: dung du lieu, nhung khong ai doc.
#
# Chi mo cho DEMO. Spectator TRUC TIEP van thoat nhu cu (khong dung toi).
# An toan: `CL_IsPredicted()` van false khi phat demo nen khoi pfnPlayerMove
# KHONG chay — chi rieng pfnPostRunCmd duoc goi, dung thu ta can.
patch(
    "engine/client/cl_pmove.c",
    "\tif( cls.state != ca_active || cls.spectator )\n"
    "\t\treturn;\n",
    "\tif( cls.state != ca_active || ( cls.spectator && !cls.demoplayback ))\n"
    "\t\treturn;\t/* xem csga-own.py muc 11 */\n",
    "own-postruncmd",
)

# --- 12. DEBUG: in co FL_DUCKING DUNG CHO dll doc ---
# HUD_WeaponsPostThink lay `from->client.flags`. Ta ghi co o cl_frame.c, nhung
# giua do va day con di qua CL_RunUsercmd (`*to = *from`, CL_FinishPMove...).
# Tu khi mo CL_PredictMovement cho demo (muc 11) duong nay MOI chay, nen rat co
# the no tinh lai co tu tu the cua MAY GHI va de len gia tri ta ghi.
# Do duoc: replay dao dau so voi choi that (dung 9 = hep, ngoi 13 = rong) —
# khop voi kha nang "dung thi dll nhan FL_DUCKING, ngoi thi khong".
patch(
    "engine/client/cl_pmove.c",
    "\tclgame.dllFuncs.pfnPostRunCmd( from, to, &cmd, runfuncs, *time, random_seed );\n",
    "\tif( cls.demoplayback )\n"
    "\t{\n"
    "\t\tstatic double csga_dbg_t;\n"
    "\t\tif( cl.time - csga_dbg_t > 1.0 )\n"
    "\t\t{\n"
    "\t\t\tcsga_dbg_t = cl.time;\n"
    "\t\t\tCon_Printf( \"[PRC] from_duck=%d to_duck=%d from_ground=%d vel=%d\\n\",\n"
    "\t\t\t\t( from->client.flags & FL_DUCKING ) ? 1 : 0,\n"
    "\t\t\t\t( to->client.flags & FL_DUCKING ) ? 1 : 0,\n"
    "\t\t\t\t( from->client.flags & FL_ONGROUND ) ? 1 : 0,\n"
    "\t\t\t\t(int)VectorLength( from->client.velocity ));\n"
    "\t\t}\n"
    "\t}\n"
    "\tclgame.dllFuncs.pfnPostRunCmd( from, to, &cmd, runfuncs, *time, random_seed );\n",
    "own-prc-debug",
)

# --- 13. Bom WEAPONDATA cua nguoi dang bam vao prediction ---
# Mat xich cuoi cua vu tam ngam nguoc (do 8/8):
#   cs_weapons.cpp: g_iWeaponFlags = pWeapon->m_iWeaponState;   // tu from->weapondata[]
#   ammo.cpp/Glock: (xhairWeaponFlags & 2) ? BAN LOAT (x1.4) : thuong (ngoi x0.5)
# `weapondata` la du lieu prediction cua NGUOI CHOI CUC BO — may ghi la spectator
# nen vung nay rong/rac. Do duoc 13/9 ≈ 1.44 ≈ x1.4: dang an nham bo co ban loat
# tu rac do. Ta da bom clientdata (mau/co/van toc) nhung CHUA tung dong toi
# weapondata — day la khe cuoi.
# a) accessor doc bang csga_own (dinh nghia canh CSGA_OwnHealth)
patch(
    "engine/client/cl_parse.c",
    "int CSGA_OwnHas( int ent )",
    "int CSGA_OwnCurWeapon( int ent, int *st, int *id, int *clip )\n"
    "{\n"
    "\tcsga_own_t *o;\n"
    "\n"
    "\tif( ent < 1 || ent > 64 )\n"
    "\t\treturn 0;\n"
    "\to = &csga_own[ent];\n"
    "\tif( o->len[1] < 3 )\n"
    "\t\treturn 0;\n"
    "\t*st = o->raw[1][0]; *id = o->raw[1][1]; *clip = o->raw[1][2];\n"
    "\treturn 1;\n"
    "}\n"
    "\n"
    "int CSGA_OwnHas( int ent )",
    "own-curweapon-accessor",
)
# b) tiem vao prediction ngay sau khi engine chep frame cua may ghi
patch(
    "engine/client/cl_pmove.c",
    "\tmemcpy( from->weapondata, frame->weapondata, sizeof( from->weapondata ));\n"
    "\tfrom->playerstate = frame->playerstate[cl.playernum];\n"
    "\tfrom->client = frame->clientdata;\n",
    "\tmemcpy( from->weapondata, frame->weapondata, sizeof( from->weapondata ));\n"
    "\tfrom->playerstate = frame->playerstate[cl.playernum];\n"
    "\tfrom->client = frame->clientdata;\n"
    "\n"
    "\t/* CSGA: prediction phai nhin thay khau sung cua NGUOI DANG BAM, khong\n"
    "\t * phai vung rong/rac cua may ghi (xem csga-own.py muc 13). */\n"
    "\tif( cls.demoplayback )\n"
    "\t{\n"
    "\t\textern int democam_target;\n"
    "\t\textern int CSGA_OwnCurWeapon( int ent, int *st, int *id, int *clip );\n"
    "\t\tint st, id, clip;\n"
    "\t\tint tgt = democam_target > 0 ? democam_target : frame->clientdata.iuser2;\n"
    "\t\tif( tgt > 0 && CSGA_OwnCurWeapon( tgt, &st, &id, &clip ))\n"
    "\t\t{\n"
    "\t\t\tmemset( from->weapondata, 0, sizeof( from->weapondata ));\n"
    "\t\t\tif( id >= 0 && id < MAX_LOCAL_WEAPONS )\n"
    "\t\t\t{\n"
    "\t\t\t\tfrom->weapondata[id].m_iId = id;\n"
    "\t\t\t\tfrom->weapondata[id].m_iClip = clip;\n"
    "\t\t\t\tfrom->weapondata[id].m_iWeaponState = 0;\t/* trang thai SACH */\n"
    "\t\t\t}\n"
    "\t\t\tfrom->client.m_iId = id;\n"
    "\t\t}\n"
    "\t}\n",
    "own-weapondata",
)

# --- 14. DEBUG: in TOA DO THAT cua tam ngam tu lenh ve ---
# Do pixel qua anh chup + loc mau da lua ta nhieu lan (0 mau, nguong, nen khac
# nhau). Chan thang CL_FillRGBA: khi phat demo va mau XANH LA troi (tam ngam CS
# ve bang cac vach chu nhat qua ham nay), in x/y/w/h — con so CHINH XAC ma dll
# tinh ra, khong qua anh. Doi chieu voi [PRC] (co dll nhan) se thay tang nao lech.
patch(
    "engine/client/cl_game.c",
    "static void GAME_EXPORT CL_FillRGBA( int x, int y, int w, int h, int r, int g, int b, int a )\n{",
    "static void GAME_EXPORT CL_FillRGBA( int x, int y, int w, int h, int r, int g, int b, int a )\n{\n"
    "\t/* CSGA debug (xem csga-own.py muc 14). Ban dau throttle 0.5s bat LENH VE\n"
    "\t * XANH DAU TIEN moi nhip — vo phai phan tu khac (y=256 trong khi tam man\n"
    "\t * 226). Gio loc theo HINH DANG vach tam ngam: manh (1px mot chieu) va SAT\n"
    "\t * TAM man hinh, in DU ca 4 vach cua cung mot khung, 1 khung moi giay. */\n"
    "\tif( cls.demoplayback && g > r + 30 && g > b + 30 && ( w == 1 || h == 1 ))\n"
    "\t{\n"
    "\t\tint cx = refState.width / 2, cy = refState.height / 2;\n"
    "\t\tif( abs( x + w / 2 - cx ) < 60 && abs( y + h / 2 - cy ) < 60 )\n"
    "\t\t{\n"
    "\t\t\tstatic double csga_xh_t; static int csga_xh_n;\n"
    "\t\t\tif( cl.time - csga_xh_t > 1.0 ) { csga_xh_t = cl.time; csga_xh_n = 0; }\n"
    "\t\t\tif( csga_xh_n < 4 )\n"
    "\t\t\t{\n"
    "\t\t\t\tcsga_xh_n++;\n"
    "\t\t\t\tCon_Printf( \"[XH] x=%d y=%d w=%d h=%d cx=%d cy=%d\\n\", x, y, w, h, cx, cy );\n"
    "\t\t\t}\n"
    "\t\t}\n"
    "\t}",
    "own-xhair-debug",
)

# --- 15. DEBUG: in MOI lenh CurWeapon bom vao dll, kem nguon ---
# [XH] cho thay: dung ve khe 3 (= hang 8 bang Distances, AUG?!), ngoi ve khe 7
# (= hang co base 7, vd knife 29) — dll dang tinh cho KHAU KHAC voi khau ta
# tuong. Nghi: mot trong ba nguon CurWeapon bom sai id, va no doi theo tu the.
patch(
    "engine/client/cl_parse.c",
    "\tif( owner == csga_own_view && cls.demoplayback )\n"
    "\t\tCL_DispatchUserMessage( csga_nm[which], len, (void *)p );",
    "\tif( owner == csga_own_view && cls.demoplayback )\n"
    "\t{\n"
    "\t\tif( which == 1 )\n"
    "\t\t\tCon_Printf( \"[CW] mirror st=%d id=%d clip=%d\\n\", p[0], len >= 2 ? p[1] : -1, len >= 3 ? p[2] : -1 );\n"
    "\t\tCL_DispatchUserMessage( csga_nm[which], len, (void *)p );\n"
    "\t}",
    "own-cw-dbg-mirror",
)
patch(
    "engine/client/cl_parse.c",
    "\tif( o->len[1] )\n"
    "\t\tCL_DispatchUserMessage( csga_nm[1], o->len[1], (void *)o->raw[1] );",
    "\tif( o->len[1] )\n"
    "\t{\n"
    "\t\tCon_Printf( \"[CW] replay st=%d id=%d clip=%d\\n\", o->raw[1][0], o->raw[1][1], o->raw[1][2] );\n"
    "\t\tCL_DispatchUserMessage( csga_nm[1], o->len[1], (void *)o->raw[1] );\n"
    "\t}",
    "own-cw-dbg-replay",
)
patch(
    "engine/client/cl_frame.c",
    "\t\t\t\t\t\t\tif( !CSGA_OwnHas( dc_view ))\n"
    "\t\t\t\t\t\t\t\tCL_DispatchUserMessage( \"CurWeapon\", 3, wbuf );",
    "\t\t\t\t\t\t\tif( !CSGA_OwnHas( dc_view ))\n"
    "\t\t\t\t\t\t\t{\n"
    "\t\t\t\t\t\t\t\tCon_Printf( \"[CW] synth st=%d id=%d\\n\", wbuf[0], wbuf[1] );\n"
    "\t\t\t\t\t\t\t\tCL_DispatchUserMessage( \"CurWeapon\", 3, wbuf );\n"
    "\t\t\t\t\t\t\t}",
    "own-cw-dbg-synth",
)

# --- 16. SUA GOC tam ngam nguoc: ep lai co SAU pmove, TRUOC khi dll doc ---
# Chuoi nhan qua (do tan tay 8/8, [PRC] fg/tg):
#   ta ghi FL_DUCKING+FL_ONGROUND vao clientdata (dung) → prediction mo phong
#   chuyen dong bang THAN THE MAY GHI (spectator lo lung) → voi hull ngoi, trace
#   cham dat hong → pmove XOA FL_ONGROUND khoi `to` → khung sau dll doc from=to
#   cu → "tren khong" → ammo.cpp ×2 (khe 17.5) thay vi ×0.5 (khe 4).
# Dung: 8×1.5=12→13px (nhanh toc-do, iWeaponSpeed=0 va 0>=0 luon dung — hanh vi
# nay GIONG CS that, anh choi that cua user cung rong khi dung). Ngoi: 4 ✓.
# Ep o day chu khong o cl_frame.c: day la DIEM CUOI truoc khi dll doc, moi thu
# pmove pha o giua deu bi ghi de lai.
patch(
    "engine/client/cl_pmove.c",
    "\tif( cls.demoplayback )\n"
    "\t{\n"
    "\t\tstatic double csga_dbg_t;",
    "\t/* CSGA: ep lai co theo NGUOI DANG BAM — xem csga-own.py muc 16 */\n"
    "\tif( cls.demoplayback )\n"
    "\t{\n"
    "\t\textern int democam_target;\n"
    "\t\tif( democam_target > 0 )\n"
    "\t\t{\n"
    "\t\t\tcl_entity_t *dce = CL_GetEntityByIndex( democam_target );\n"
    "\t\t\tif( dce && dce->model )\n"
    "\t\t\t{\n"
    "\t\t\t\tint dfl = FL_ONGROUND | (( dce->curstate.usehull == 1 ) ? FL_DUCKING : 0 );\n"
    "\t\t\t\tfrom->client.flags = ( from->client.flags & ~FL_DUCKING ) | dfl;\n"
    "\t\t\t\tto->client.flags   = ( to->client.flags   & ~FL_DUCKING ) | dfl;\n"
    "\t\t\t}\n"
    "\t\t}\n"
    "\t}\n"
    "\tif( cls.demoplayback )\n"
    "\t{\n"
    "\t\tstatic double csga_dbg_t;",
    "own-flags-after-pmove",
)
