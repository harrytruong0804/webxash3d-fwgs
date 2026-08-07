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
typedef struct { byte has, wstate, wid, clip; byte ammo[64]; int battery, money; } csga_own_t;
static csga_own_t csga_own[65];
static int csga_own_view;

void CSGA_OwnStore( const byte *b, int len )
{
	static const char *nm[] = { "", "CurWeapon", "AmmoX", "Battery", "Money" };
	int which = b[0], owner = b[1];
	const byte *p = b + 2;
	csga_own_t *o;

	len -= 2;
	if( owner < 1 || owner > 64 || which < 1 || which > 4 )
		return;
	o = &csga_own[owner];
	o->has = 1;
	/* DEBUG tam (go sau khi chot khong gian chi so): doi chieu owner voi
	 * [HLKILL] de bat lech chi so — bug trao du lieu A<->B user bat 8/8. */
	if( cls.demoplayback )
		Con_Printf( "[CSGAOWN] w=%d own=%d view=%d p0=%d p1=%d\\n", which, owner, csga_own_view, p[0], len >= 2 ? p[1] : -1 );
	switch( which )
	{
	case 1: if( len >= 3 ) { o->wstate = p[0]; o->wid = p[1]; o->clip = p[2]; } break;
	case 2: if( len >= 2 && p[0] < 64 ) o->ammo[p[0]] = p[1]; break;
	case 3: if( len >= 1 ) o->battery = p[0] | ( len >= 2 ? p[1] << 8 : 0 ); break;
	case 4: if( len >= 4 ) o->money = p[0] | ( p[1] << 8 ) | ( p[2] << 16 ) | ( p[3] << 24 ); break;
	}
	/* dang xem dung nguoi nay -> phat ban tin goc ngay, HUD cap nhat tuc thi */
	if( owner == csga_own_view && cls.demoplayback )
		CL_DispatchUserMessage( nm[which], len, (void *)p );
}

void CSGA_OwnReplay( int ent )
{
	csga_own_t *o;
	byte b[8];
	int i;

	csga_own_view = ent;
	if( ent < 1 || ent > 64 )
		return;
	o = &csga_own[ent];
	if( !o->has )
		return;
	b[0] = o->wstate; b[1] = o->wid; b[2] = o->clip;
	CL_DispatchUserMessage( "CurWeapon", 3, b );
	for( i = 0; i < 64; i++ )
	{
		if( !csga_own[ent].ammo[i] )
			continue;
		b[0] = (byte)i; b[1] = o->ammo[i];
		CL_DispatchUserMessage( "AmmoX", 2, b );
	}
	b[0] = o->battery & 0xff; b[1] = ( o->battery >> 8 ) & 0xff;
	CL_DispatchUserMessage( "Battery", 2, b );
	b[0] = o->money & 0xff; b[1] = ( o->money >> 8 ) & 0xff;
	b[2] = ( o->money >> 16 ) & 0xff; b[3] = ( o->money >> 24 ) & 0xff; b[4] = 1;
	CL_DispatchUserMessage( "Money", 5, b );
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
    '\t\t|| !Q_strcmp( clgame.msg[i].name, "Money" ) || !Q_strcmp( clgame.msg[i].name, "ArmorType" )))\n'
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

print("csga-own.py: tat ca patch da ap")
