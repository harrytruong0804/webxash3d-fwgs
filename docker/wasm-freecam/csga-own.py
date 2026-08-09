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
    "\t\t\t\t\t\tstatic int vm_last_wm = -1, vm_last_idx;\n"
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
    "\t\t\t\tcl_entity_t *dte = dc_view > 0 ? CL_GetEntityByIndex( dc_view ) : NULL;\n",
    "\t\t\t\tcl_entity_t *dte = dc_view > 0 ? CL_GetEntityByIndex( dc_view ) : NULL;\n"
    "\t\t\t\tif( dte )\n"
    "\t\t\t\t{\n"
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
    "\tclgame.dllFuncs.pfnPostRunCmd( from, to, &cmd, runfuncs, *time, random_seed );\n",
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
    "\tclgame.dllFuncs.pfnPostRunCmd( from, to, &cmd, runfuncs, *time, random_seed );\n",
    "own-flags-after-pmove",
)

# --- 17. CAMERA REPLAY: tu quyet dinh vi tri, dung chieu cao mat CUA CS ---
# (a) VI TRI: da chung minh co khung dll re sang nhanh nguoi-choi-thuong va tra
#     ve vi tri THAN THE MAY GHI — do trung khit: cam nhay ve (416 2080 35),
#     may ghi o (416 2080 36), nguoi dang bam o (-608 -1920 -204). Va iuser o
#     ca 3 tang (clientdata / curstate / `src` cua HUD_ProcessPlayerState) deu
#     KHONG chan het duoc (van 50 cu nhay/100s) => thoi thuyet phuc dll, TU DAT.
#     Sau va: 50 -> 2 cu, ca 2 deu hop le (luc chua bam + luc doi nguoi).
# (b) CHIEU CAO MAT 17, khong phai 28: dll dung 28 = DEFAULT_VIEWHEIGHT cua
#     HALF-LIFE (cl_dll/view.cpp:1490), con CS 1.6 dat mat o 17
#     (dlls/util.h VEC_VIEW = (0,0,17); pm_shared.h PM_VEC_VIEW 17).
#     Camera cao hon mat that 11 don vi => ngam NGANG ma dan cam THAP HON tam.
#     Ngoi thi dll dung 12 = dung VEC_DUCK_VIEW nen khong loi — khop viec chi
#     thay lech luc DUNG.
# (b2) DUNG dung 17 (VEC_VIEW cua CS), KHONG dung 28.
#     28 la DEFAULT_VIEWHEIGHT cua Half-Life goc; cs16-client bê nguyên sang CS
#     (cl_dll/view.cpp:1459 V_GetInEyePos) nen dll sai san. Chep theo dll thi
#     CAMERA o 28 trong khi VIEN DAN roi khoi 17 (muc 18) -> dung thi vet dan
#     thap hon tam DUNG 11 don vi, ngoi thi trung khit vi ca hai deu dung 12.
#     Do la trieu chung user bao: "ngoi thi chinh xac, dung thi bi lech".
# (c) TAY SUNG phai dich cung mot luong: dll dat viewmodel theo vieworg CU cua
#     no; khong dich theo thi "mat tay, chi con dau nong tho ra".
patch(
    "engine/client/cl_view.c",
    "\t\tclgame.dllFuncs.pfnCalcRefdef( &rp );\n"
    "\t\tCL_DemoCamApply( &rp );",
    "\t\tclgame.dllFuncs.pfnCalcRefdef( &rp );\n"
    "\t\tif( cls.demoplayback && !democam_chase && democam_target > 0 )\n"
    "\t\t{\n"
    "\t\t\tcl_entity_t *ce = CL_GetEntityByIndex( democam_target );\n"
    "\t\t\tif( ce && ce->model )\n"
    "\t\t\t{\n"
    "\t\t\t\tvec3_t neworg, delta;\n"
    "\t\t\t\tVectorCopy( ce->origin, neworg );\n"
    "\t\t\t\tif( ce->curstate.solid == SOLID_NOT )\n"
    "\t\t\t\t\tneworg[2] += -8.0f;\t\t/* PM_DEAD_VIEWHEIGHT */\n"
    "\t\t\t\telse if( ce->curstate.usehull == 1 )\n"
    "\t\t\t\t\tneworg[2] += 12.0f;\t\t/* VEC_DUCK_VIEW */\n"
    "\t\t\t\telse\n"
    "\t\t\t\t\tneworg[2] += 17.0f;\t\t/* VEC_VIEW cua CS */\n"
    "\t\t\t\tVectorSubtract( neworg, rp.vieworg, delta );\n"
    "\t\t\t\tVectorCopy( neworg, rp.vieworg );\n"
    "\t\t\t\tif( clgame.viewent.model )\n"
    "\t\t\t\t{\n"
    "\t\t\t\t\tVectorAdd( clgame.viewent.origin, delta, clgame.viewent.origin );\n"
    "\t\t\t\t\tVectorAdd( clgame.viewent.curstate.origin, delta, clgame.viewent.curstate.origin );\n"
    "\t\t\t\t\tVectorAdd( clgame.viewent.latched.prevorigin, delta, clgame.viewent.latched.prevorigin );\n"
    "\t\t\t\t}\n"
    "\t\t\t}\n"
    "\t\t}\n"
    "\t\tCL_DemoCamApply( &rp );",
    "own-camera-authoritative",
)


# --- 18. SUA DUONG DAN: cong chieu cao mat vao diem xuat phat cua vien dan ---
# LOI THAT CUA cs16-client (cl_dll/ev_common.cpp:104 EV_GetGunPosition):
#     if( EV_IsLocal(idx) && !IS_FIRSTPERSON_SPEC ) <lay view height that: 17>
#     else if( args->ducking == 1 )                 <lay VEC_DUCK_VIEW: 12>
#     // DUNG ma khong phai minh -> KHONG NHANH NAO CHAY -> view_ofs = (0,0,0)
#     pos = args->origin + view_ofs;
# => xem nguoi khac DUNG thi dan xuat phat tu duoi CHAN, cam vao tuong THAP HON
# tam ngam dung bang chieu cao mat.
#
# User chot bang phep so HAI MAN HINH SONG SONG (nguoi choi that vs inspector,
# cung canh): TAM NGAM hai ben TRUNG nhau, chi VET DAN lech => camera von dung,
# sai nam o duong dan. Nho vay loai duoc camera khoi dien nghi va tim ra day.
# Cung giai thich: nguoi choi that khong dinh (nhanh dau chay), NGOI khong dinh
# (co nhanh 12) — chi DUNG moi lech, khop y het quan sat.
#
# Vá o engine vi dll la wasm dong san: dll tinh pos = args->origin + view_ofs,
# nen cong san chieu cao mat vao args->origin la du. CHI khi phat demo.
patch(
    "engine/client/cl_events.c",
    "\t\t\t\t\tCL_CalcPlayerVelocity( state->number, args.velocity );\n"
    "\t\t\t\t\targs.ducking = ( state->usehull == 1 );\n",
    "\t\t\t\t\tCL_CalcPlayerVelocity( state->number, args.velocity );\n"
    "\t\t\t\t\targs.ducking = ( state->usehull == 1 );\n"
    "\n"
    "\t\t\t\t\t/* xem csga-own.py muc 18 */\n"
    "\t\t\t\t\tif( cls.demoplayback && !args.ducking )\n"
    "\t\t\t\t\t\targs.origin[2] += 17.0f;\t/* VEC_VIEW cua CS */\n",
    "own-bullet-origin",
)

# --- GHI CHU: KHONG bat pfnPostRunCmd khi phat demo ---
# Da thu HAI LAN va ca hai lan deu SAI:
#   `if( cls.state != ca_active || ( cls.spectator && !cls.demoplayback )) return;`
# Ly do them: pfnPostRunCmd -> HUD_WeaponsPostThink la noi gan g_iPlayerFlags,
# tuong rang thieu no thi co FL_DUCKING (muc 16) khong ai doc.
# THUC TE DO DUOC (user kiem tay 2026-08-08): bat len thi NGOI lai GIAN RA,
# tat di thi ngoi thu nho / dung gian ra — DUNG.
# => dll con mot duong KHAC de biet tu the nguoi dang bam ma tao chua tim ra;
# ep thu cong qua clientdata lam nhieu duong do. Truoc khi dong vao day lan
# nua, PHAI tim duoc duong that su nuoi crosshair (dat diem dung trong
# cs16-client GetCrosshairGap/DrawCrosshair roi lan nguoc), dung suy tu
# "noi duy nhat gan g_iPlayerFlags" — suy luan do da sai hai lan.

# --- 20. Cho code vu khi chay khi phat demo (CAN, dung go nua) ---
# `cs16-client` gan g_iPlayerFlags / g_flPlayerSpeed o DUNG MOT cho:
# cl_dll/cs_wpn/cs_weapons.cpp:1232, ben trong HUD_WeaponsPostThink, ma no chi
# toi duoc qua HUD_PostRunCmd (dong 1472). Tat pfnPostRunCmd khi phat demo =>
# hai bien vinh vien 0 => GetCrosshairGap luon roi vao nhanh dau
# (`!(0 & FL_ONGROUND) && ACCURACY_AIR` -> minGap *= 2) => TAM NGAM DUNG HINH.
# Da do 2026-08-08: 12 khung cach nhau 3s tren demo ngoi/dung moi 6s cho tam
# ngam Y HET NHAU. "Khong doi" rat de bi doc nham thanh "dung".
# `cls.spectator` bi dat lai true o cl_parse.c:2060 (HLTV_ACTIVE) sau khi
# cl_demo.c:731 da dat false, nen phai loai tru bang cls.demoplayback.
patch(
    "engine/client/cl_pmove.c",
    "\tif( cls.state != ca_active || cls.spectator )\n\t\treturn;",
    "\tif( cls.state != ca_active || ( cls.spectator && !cls.demoplayback ))\n\t\treturn;",
    "own-postruncmd",
)

# Ghi chu do luong 2026-08-08 (bang chung, dung do lai tu dau):
#   demo #25 (ngoi/dung luan phien 6s), do khe tam ngam theo tung khung kem
#   `usehull` doc cung khung:  DUNG = 10px,  NGOI = 4-5px  -> ty le 0.5 dung
#   bang `minGap *= 0.5f` trong cs16-client GetCrosshairGap. Tam ngam DUNG.

# Kiem CUC cua usehull (do 2026-08-08, dung origin[2] lam chi so DOC LAP):
#   hull=0 -> z=36   |   hull=1 -> z=18   (thap hon dung 18 don vi, khop PM_Duck)
# => usehull==1 THAT SU la ngoi. Ca ba ban va (camera muc 17, duong dan muc 18,
#    co tu the muc 16) doc dung cuc, khong can dao.
#
# BAY VE PHUONG PHAP: "vet dan trung tam" KHONG kiem duoc cuc nay. Camera va
# nong sung deu doc usehull, nen sai cuc thi ca hai lech CUNG CHIEU va tren man
# hinh van trung khit. Muon kiem mot gia tri thi phai doi chieu voi thu MINH
# KHONG SINH RA.
#
# Do tam ngam sau khi sua (demo #25, cua so 1500px, doc hull cung khung):
#   DUNG khe 23px / canh 9px      NGOI khe 8px / canh 5px
# Canh chuyen dung->ngoi di qua mot khung 22/14: `m_flCrosshairDistance` bi kep
# `max(dist, iDistance)` nen len TUC THI, con xuong thi phai co dan
# (`-= dist*0.013 + 0.1` moi khung), trong luc do `iLength` phinh ra. Do la
# hanh vi goc cua CS, khong phai loi — nhung truoc khi sua thi tam ngam DUNG
# HINH, nen cu no nay la thu moi xuat hien.

# --- 21. TU CHON NGUOI BAM ngay khi mo demo ---
#
# VAN DE (user phat hien 2026-08-09): mo trang xem lai ma CHUA click vao khung
# hinh thi `democam_target` van la 0 (cl_view.c:371 khoi tao 0 = tat), nen KHONG
# MOT ban va nao cua CSGA chay — dang xem goc nhin tho cua may ghi, la mot
# spectator dang BAY. Spectator bay thi `from->client.flags` khong co
# FL_ONGROUND, nen GetCrosshairGap cua cs16-client roi vao nhanh ACCURACY_AIR
# (`minGap *= 2`) co dinh: tam ngam to va khong phan ung ngoi/dung.
# Click chuot trai goi `democam_next` -> target > 0 -> moi thu dung tro lai.
#
# Moi phep do truoc day deu "dung" vi script tu dong luon go `democam 1` ngay
# sau khi phat — vo tinh bat che do cua minh, trong khi nguoi dung thi khong.
#
# Sua: dang phat demo ma target con 0 thi tu tim nguoi dau tien hop le.
# - Chi tu chon MOT LAN moi demo (`democam_auto`), de nguoi xem van bam duoc
#   "cam goc" (`democam 0`) quay ve goc nhin may ghi ma khong bi keo lai.
# - Phai kiem lai ket qua: CL_DemoCamStep KHONG tra ve 0 khi that bai — no
#   tang dan roi thoat vong lap voi target = maxclients. Luc dau tran thuc the
#   chua co model, nen khong kiem thi se bam vao mot chi so rong.
patch(
    "engine/client/cl_view.c",
    "void CL_DemoCamNext_f( void ) { CL_DemoCamStep( +1 ); }",
    "int democam_auto = 0;\t/* da tu chon nguoi bam cho demo nay chua */\n"
    "void CSGA_DemoCamAutoPick( void )\n"
    "{\n"
    "\tcl_entity_t *e;\n"
    "\tif( !cls.demoplayback || democam_auto || democam_target != 0 )\n"
    "\t\treturn;\n"
    "\tCL_DemoCamStep( +1 );\n"
    "\te = CL_GetEntityByIndex( democam_target );\n"
    "\tif( democam_target > 0 && e && e->model && democam_target != cl.playernum + 1 )\n"
    "\t\tdemocam_auto = 1;\n"
    "\telse\n"
    "\t\tdemocam_target = 0;\t/* chua san sang — thu lai khung sau */\n"
    "}\n"
    "void CL_DemoCamNext_f( void ) { CL_DemoCamStep( +1 ); }",
    "own-autopick",
)

# Goi moi khung, ngay TRUOC khoi camera (muc 17) de khung dau tien da co nguoi bam.
patch(
    "engine/client/cl_view.c",
    "\t\tclgame.dllFuncs.pfnCalcRefdef( &rp );\n"
    "\t\tif( cls.demoplayback && !democam_chase && democam_target > 0 )",
    "\t\tCSGA_DemoCamAutoPick();\n"
    "\t\tclgame.dllFuncs.pfnCalcRefdef( &rp );\n"
    "\t\tif( cls.demoplayback && !democam_chase && democam_target > 0 )",
    "own-autopick-call",
)

# Mo demo moi thi quen lua chon cu — khong thi demo thu hai trong cung mot tab
# se giu nguyen chi so cua demo truoc (khac tran, khac nguoi).
patch(
    "engine/client/cl_demo.c",
    "\tcls.demoplayback = mode;\n"
    "\tcls.state = ca_connected;",
    "\tcls.demoplayback = mode;\n"
    "\t{\n"
    "\t\textern int democam_target, democam_auto;\n"
    "\t\tdemocam_target = 0;\n"
    "\t\tdemocam_auto = 0;\n"
    "\t}\n"
    "\tcls.state = ca_connected;",
    "own-autopick-reset",
)



# --- 22+23. GUI spectator khi xem lai: an hai dai den, keo dong ten len tren ---
#
# `cs16-client` la wasm DUNG SAN (khong build tu nguon) nen khong sua thang
# duoc. Nhung ca hai thu deu ve qua HAM CUA ENGINE, nen chan o day duoc:
#   - hai dai den : spectator_gui.cpp:141-142 goi FillRGBABlend, mau (0,0,0,153)
#                   (chu thich goc cua ho: "at first, draw these silly black bars")
#   - dong ten    : spectator_gui.cpp:223 goi DrawHudString -> tung ky tu qua
#                   gEngfuncs.pfnDrawCharacter, tai y = INT_YPOS(9) ~ 0.9*H
#                   (INT_YPOS(y) = y/10 * ScreenHeight, luoi 16x10)
#
# Nhan dang an toan:
#   - dai den: den tuyet doi + alpha DUNG 153 + rong hon nua man + cham mep tren
#     hoac duoi. Da grep toan bo cl_dll: to hop mau nay khong dung o dau khac.
#   - dong ten: y nam trong dai hep quanh 0.9*H. HUD duoi (mau/giap/tien/dan) ve
#     bang SPRITE (SPR_DrawAdditive), khong qua pfnDrawCharacter nen khong bi keo
#     theo; chu notify da tat bang `con_notifytime 0` truoc khi phat.
#
# MAC DINH GIU NGUYEN BAN GOC. Hai cai nay chi dung cho VIDEO HIGHLIGHT —
# noi khung hinh phai sach de dang len FB/Discord. Trang /replay va inspect luc
# dang choi thi de y nguyen: nguoi xem o do can dung thu nguoi choi da thay,
# va hai dai den + dong ten o day la mot phan cua giao dien CS that.
#   csga_specbars   1 = giu hai dai (MAC DINH) | 0 = an
#   csga_specname_y 0 = ten o cho cu (MAC DINH)| 0.035 = keo len sat mep tren
# Bat len o `autoclip4.mjs` / `autoclip5.mjs`, ngay truoc khi bat dau quay.
# Bo FCVAR_ARCHIVE de moi phien luon khoi dong tu mac dinh, khong bi mot lan
# nghich tay dinh lai vao config.

# Khai bao o DAU cl_game.c: pfnDrawCharacter (~dong 2000) dung truoc
# CL_FillRGBABlend (~dong 3172), dat canh FillRGBABlend thi ham tren bao
# "use of undeclared identifier".
patch(
    "engine/client/cl_game.c",
    "static char cl_textbuffer[MAX_TEXTCHANNELS][2048];",
    "CVAR_DEFINE_AUTO( csga_specbars, \"1\", 0, \"CSGA: 0 = an hai dai den cua GUI spectator (chi dung khi dung clip)\" );\n"
    "CVAR_DEFINE_AUTO( csga_specname_y, \"0\", 0, \"CSGA: >0 = keo dong ten len vi tri nay (ti le chieu cao); 0 = giu cho cu\" );\n"
    "static char cl_textbuffer[MAX_TEXTCHANNELS][2048];",
    "own-specgui-cvars",
)

patch(
    "engine/client/cl_game.c",
    "static void GAME_EXPORT CL_FillRGBABlend( int x, int y, int w, int h, int r, int g, int b, int a )\n"
    "{\n"
    "\tfloat x_ = x, y_ = y, w_ = w, h_ = h;\n",
    "static void GAME_EXPORT CL_FillRGBABlend( int x, int y, int w, int h, int r, int g, int b, int a )\n"
    "{\n"
    "\tfloat x_ = x, y_ = y, w_ = w, h_ = h;\n"
    "\n"
    "\t/* CSGA: nuot hai dai den cua GUI spectator khi dang xem lai. */\n"
    "\tif( cls.demoplayback && csga_specbars.value == 0.0f\n"
    "\t && r == 0 && g == 0 && b == 0 && a == 153\n"
    "\t && w >= clgame.scrInfo.iWidth / 2\n"
    "\t && ( y <= 0 || y + h >= clgame.scrInfo.iHeight - 1 ))\n"
    "\t\treturn;\n",
    "own-specbars",
)

patch(
    "engine/client/cl_game.c",
    "static int GAME_EXPORT pfnDrawCharacter( int x, int y, int number, int r, int g, int b )\n"
    "{\n"
    "\trgba_t color = { r, g, b, 255 };\n",
    "static int GAME_EXPORT pfnDrawCharacter( int x, int y, int number, int r, int g, int b )\n"
    "{\n"
    "\trgba_t color = { r, g, b, 255 };\n"
    "\n"
    "\t/* CSGA: keo dong ten nguoi dang bam tu day man hinh len tren. */\n"
    "\tif( cls.demoplayback && csga_specname_y.value > 0.0f )\n"
    "\t{\n"
    "\t\tint H = clgame.scrInfo.iHeight;\n"
    "\t\tif( H > 0 && y >= (int)( H * 0.86f ) && y <= (int)( H * 0.94f ))\n"
    "\t\t\ty = (int)( H * csga_specname_y.value );\n"
    "\t}\n",
    "own-specname",
)

# Neo vao dong UPSTREAM, khong neo vao ma do chinh minh sinh ra.
patch(
    "engine/client/cl_main.c",
    "\tCmd_AddCommand (\"democam\", CL_DemoCam_f, \"CSGA: bam nguoi choi khi phat demo\" );",
    "\t{\n"
    "\t\textern convar_t csga_specbars, csga_specname_y;\n"
    "\t\tCvar_RegisterVariable( &csga_specbars );\n"
    "\t\tCvar_RegisterVariable( &csga_specname_y );\n"
    "\t}\n"
    "\tCmd_AddCommand (\"democam\", CL_DemoCam_f, \"CSGA: bam nguoi choi khi phat demo\" );",
    "own-specgui-reg",
)
