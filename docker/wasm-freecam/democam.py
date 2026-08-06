#!/usr/bin/env python3
"""Va engine THEM camera tu do khi phat demo — LAM O ENGINE, khong dung client dll.

Vi sao khong dung spec_mode cua client dll: da do 2026-08-06, ke ca khi va
IsSpectateOnly, lenh spec_mode/spec_mode 5 KHONG doi duoc view luc phat demo cua
mot game-spectator. Bo may khan gia trong cs16-client khong gianh duoc quyen —
g_iUser1 khong len, hoac bi reset moi khung. Do khong sua noi tu ngoai vi client
dll la wasm rieng (npm), khong build lai.

Cach nay ngan gon hon va do CHINH engine kiem soat: sau khi client dll tinh xong
ref_params (pfnCalcRefdef), engine GHI DE thang vieworg/viewangles bang vi tri
cua nguoi choi minh chon. Bo qua hoan toan bo may khan gia.

  democam <n>     : bam nguoi choi entity n (0 = tat, ve view goc cua demo)
  democam_next    : nhay sang nguoi choi ke tiep
  democam_prev    : nguoi choi truoc
  democam_chase   : bat/tat che do bam sau lung (mac dinh goc nhin thu nhat)

Han che biet truoc: chi bam duoc nguoi choi CO trong du lieu demo. Neu demo ghi
o che do in-eye bam mot nguoi va server cat bot theo tam nhin (PVS) thi nguoi o
xa co the khong co du lieu. Ghi o che do thay het (roaming/full) thi doi duoc
moi nguoi.
"""
import re
import sys

ROOT = "/xash3d-fwgs/engine/client"


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


# --- 1. Khoi code democam, chen vao cuoi cl_view.c (truoc dong include cuoi hay
#        cuoi file cung duoc — de an toan, chen ngay truoc V_RenderView). ---
DEMOCAM_CODE = r"""
/* ==== CSGA democam: camera tu do khi phat demo (xem democam.py) ==== */
/* KHONG static: cl_frame.c extern sang de de banner spectator hien dung target
 * (de iuser1/iuser2 vao clientdata truoc pfnTxferLocalOverrides). */
int democam_target = 0;   /* entity index nguoi dang bam; 0 = tat */
int democam_chase  = 0;   /* 1 = bam sau lung, 0 = goc nhin thu nhat */

static void CL_DemoCam_f( void )
{
	if( Cmd_Argc() < 2 )
	{
		Con_Printf( "democam <entity#>  (0 = tat). Dang bam: %i\n", democam_target );
		return;
	}
	democam_target = Q_atoi( Cmd_Argv( 1 ));
	Con_Printf( "democam -> %i\n", democam_target );
}

static void CL_DemoCamStep( int dir )
{
	int i, n = cl.maxclients;
	for( i = 0; i < n; i++ )
	{
		democam_target += dir;
		if( democam_target < 1 ) democam_target = n;
		if( democam_target > n ) democam_target = 1;
		cl_entity_t *e = CL_GetEntityByIndex( democam_target );
		if( e && e->model ) { Con_Printf( "democam -> %i\n", democam_target ); return; }
	}
}
static void CL_DemoCamNext_f( void ) { CL_DemoCamStep( +1 ); }
static void CL_DemoCamPrev_f( void ) { CL_DemoCamStep( -1 ); }

/* Bam nguoi choi theo TEN (tu log kill). cl.players[i] la slot i, entity i+1. */
static void CL_DemoCamName_f( void )
{
	int i, n = cl.maxclients, wlen;
	const char *want;

	if( Cmd_Argc() < 2 )
	{
		Con_Printf( "democam_name <ten nguoi choi>\n" );
		return;
	}
	want = Cmd_Args();   /* ca ten, ke ca co khoang trang: "chicken (2)" */
	wlen = Q_strlen( want );

	/* khop chinh xac truoc */
	for( i = 0; i < n; i++ )
	{
		if( !cl.players[i].name[0] ) continue;
		if( !Q_stricmp( cl.players[i].name, want ))
		{
			democam_target = i + 1;
			Con_Printf( "democam -> %s (entity %i)\n", cl.players[i].name, democam_target );
			return;
		}
	}
	/* khop tien to */
	for( i = 0; i < n; i++ )
	{
		if( !cl.players[i].name[0] ) continue;
		if( wlen > 0 && !Q_strnicmp( cl.players[i].name, want, wlen ))
		{
			democam_target = i + 1;
			Con_Printf( "democam -> %s (entity %i, khop tien to)\n", cl.players[i].name, democam_target );
			return;
		}
	}
	Con_Printf( "democam_name: khong thay '%s'\n", want );
}
static void CL_DemoCamChase_f( void )
{
	democam_chase = !democam_chase;
	Con_Printf( "democam che do: %s\n", democam_chase ? "bam sau lung" : "goc nhin thu nhat" );
}

/* Ghi de vieworg/viewangles bang vi tri nguoi choi da chon. Goi NGAY sau
 * pfnCalcRefdef trong V_RenderView. */
static void CL_DemoCamApply( ref_params_t *rp )
{
	cl_entity_t	*ent;
	vec3_t		org, ang, fwd;

	if( !cls.demoplayback || democam_target <= 0 )
		return;
	ent = CL_GetEntityByIndex( democam_target );
	if( !ent || !ent->model )
		return;

	VectorCopy( ent->origin, org );
	VectorCopy( ent->angles, ang );
	/* Goc pitch cua nguoi choi luu dang nen: view_pitch = -3 * body_pitch
	 * (xem V_CalcSpectatorRefdef trong cs16-client). */
	ang[0] = ent->angles[0] * -3.0f;

	if( democam_chase )
	{
		AngleVectors( ang, fwd, NULL, NULL );
		VectorMA( org, -112.0f, fwd, org );   /* lui sau 112 don vi */
		org[2] += 24.0f;
	}
	else
	{
		org[2] += 28.0f;   /* chieu cao mat khi dung */
	}

	VectorCopy( org, rp->vieworg );
	VectorCopy( ang, rp->viewangles );
}
/* ==== het democam ==== */

"""

patch(
    "cl_view.c",
    "void V_RenderView( void )\n{",
    DEMOCAM_CODE + "void V_RenderView( void )\n{",
    "code",
)

# --- 2. Goi CL_DemoCamApply ngay sau pfnCalcRefdef ---
patch(
    "cl_view.c",
    "\t\tclgame.dllFuncs.pfnCalcRefdef( &rp );\n",
    "\t\tclgame.dllFuncs.pfnCalcRefdef( &rp );\n\t\tCL_DemoCamApply( &rp );\n",
    "goi-apply",
)

# --- 3. Dang lenh trong CL_InitLocal (cl_main.c) ---
patch(
    "cl_main.c",
    '\tCmd_AddCommand ("fullupdate", NULL, "re-init HUD on start demo recording" );',
    '\tCmd_AddCommand ("fullupdate", NULL, "re-init HUD on start demo recording" );\n'
    '\tCmd_AddCommand ("democam", CL_DemoCam_f, "CSGA: bam nguoi choi khi phat demo" );\n'
    '\tCmd_AddCommand ("democam_next", CL_DemoCamNext_f, "CSGA: nguoi choi ke" );\n'
    '\tCmd_AddCommand ("democam_name", CL_DemoCamName_f, "CSGA: bam nguoi choi theo ten" );\n'
    '\tCmd_AddCommand ("democam_prev", CL_DemoCamPrev_f, "CSGA: nguoi choi truoc" );\n'
    '\tCmd_AddCommand ("democam_chase", CL_DemoCamChase_f, "CSGA: bat/tat bam sau lung" );',
    "dang-lenh",
)

# Ham dinh nghia o cl_view.c nhung dung o cl_main.c -> khai bao extern.
patch(
    "cl_main.c",
    "static void CL_InitLocal( void )\n{",
    "extern void CL_DemoCam_f( void );\n"
    "extern void CL_DemoCamNext_f( void );\n"
    "extern void CL_DemoCamName_f( void );\n"
    "extern void CL_DemoCamPrev_f( void );\n"
    "extern void CL_DemoCamChase_f( void );\n\n"
    "static void CL_InitLocal( void )\n{",
    "extern-decl",
)

# Bo `static` khoi 4 ham lenh de cl_main.c linh duoc (van giu static cho bien).
v = open(f"{ROOT}/cl_view.c").read()
for fn in ("CL_DemoCam_f", "CL_DemoCamNext_f", "CL_DemoCamPrev_f", "CL_DemoCamChase_f", "CL_DemoCamName_f"):
    v = v.replace(f"static void {fn}( void )", f"void {fn}( void )")
open(f"{ROOT}/cl_view.c", "w").write(v)
print("  [bo-static] xong")

# --- 4. Hook DeathMsg: in CHI SO ENTITY killer/victim khi phat demo ---
# Map kill->entity phai theo chi so entity, KHONG theo ten (khach trung ten
# duoc, server them "(1)"). DeathMsg trong demo bit-packed khong grep duoc, nhung
# tai CL_DispatchUserMessage engine da giao payload BYTE-ALIGNED cho client dll.
# In pbuf[0]=killer, pbuf[1]=victim (chi so client = chi so entity nguoi choi).
# Worker doc dong [HLKILL] tu log luc phat -> map kill->entity mien nhiem trung ten.
patch(
    "cl_parse.c",
    "qboolean CL_DispatchUserMessage( const char *pszName, int iSize, void *pbuf )\n{\n\tint\ti;\n\n\tif( !COM_CheckString( pszName ))\n\t\treturn false;\n",
    "qboolean CL_DispatchUserMessage( const char *pszName, int iSize, void *pbuf )\n{\n\tint\ti;\n\n\tif( !COM_CheckString( pszName ))\n\t\treturn false;\n\n"
    "\tif( !Q_strcmp( pszName, \"DeathMsg\" ) && iSize >= 2 )\n"
    "\t\tCon_Printf( \"[HLKILL] killer=%d victim=%d\\n\", ((byte *)pbuf)[0], ((byte *)pbuf)[1] );\n",
    "hook-deathmsg-dispatch",
)

# Duong phat demo protocol 49 di qua CL_ParseUserMessage (CL_ParseServerMessage
# -> svc_usermessage), KHONG qua CL_DispatchUserMessage. pbuf o day la byte[]
# da byte-align (MSG_ReadBytes). Hook them o day moi bat duoc kill luc phat demo.
patch(
    "cl_parse.c",
    "\tif( clgame.msg[i].func )\n\t{\n\t\tclgame.msg[i].func( clgame.msg[i].name, iSize, pbuf );\n",
    "\tif( !Q_strcmp( clgame.msg[i].name, \"DeathMsg\" ) && iSize >= 2 )\n"
    "\t\tCon_Printf( \"[HLKILL] killer=%d victim=%d\\n\", pbuf[0], pbuf[1] );\n\n"
    "\tif( clgame.msg[i].func )\n\t{\n\t\tclgame.msg[i].func( clgame.msg[i].name, iSize, pbuf );\n",
    "hook-deathmsg-parse",
)

# --- 5. Banner spectator hien DUNG target cua democam ---
# Client dll (HL SDK) set g_iUser1/2 tu clientdata trong HUD_TxferLocalOverrides;
# democam chi de camera nen banner van hien target CU ma recorder bam luc ghi
# ("chicken (100)" trong khi cam da sang nguoi khac — bug user bao 2026-08-06).
# De iuser1 (2=chase/4=in-eye) + iuser2 (target) vao clientdata TRUOC cu goi do.
patch(
    "cl_frame.c",
    "\t\tif( state->number == ( cl.playernum + 1 ))\n"
    "\t\t\tclgame.dllFuncs.pfnTxferLocalOverrides( state, &frame->clientdata );\n",
    "\t\tif( state->number == ( cl.playernum + 1 ))\n"
    "\t\t{\n"
    "\t\t\textern int democam_target, democam_chase;\n"
    "\t\t\tif( cls.demoplayback && democam_target > 0 )\n"
    "\t\t\t{\n"
    "\t\t\t\tframe->clientdata.iuser1 = democam_chase ? 2 : 4;\n"
    "\t\t\t\tframe->clientdata.iuser2 = democam_target;\n"
    "\t\t\t\t{\n"
    "\t\t\t\t\t/* mau cua target neu demo co (entity_state.health); 0 = khong biet */\n"
    "\t\t\t\t\tcl_entity_t *dte = CL_GetEntityByIndex( democam_target );\n"
    "\t\t\t\t\tif( dte && dte->curstate.health > 0 )\n"
    "\t\t\t\t\t\tframe->clientdata.health = dte->curstate.health;\n"
    "\n"
    "\t\t\t\t\t/* Crosshair: client dll chi ve khi m_pWeapon duoc set boi usermessage\n"
    "\t\t\t\t\t * CurWeapon — demo CHI chua CurWeapon cua nguoi recorder bam luc ghi\n"
    "\t\t\t\t\t * (xem chicken co crosshair, xem nguoi khac thi khong — bug user bao).\n"
    "\t\t\t\t\t * Tong hop CurWeapon tu p_ weaponmodel cua target (luon co trong demo). */\n"
    "\t\t\t\t\tif( dte )\n"
    "\t\t\t\t\t{\n"
    "\t\t\t\t\t\tstatic int dc_last_ent, dc_last_wm = -1;\n"
    "\t\t\t\t\t\tint wm = dte->curstate.weaponmodel;\n"
    "\t\t\t\t\t\tif( wm != dc_last_wm || democam_target != dc_last_ent )\n"
    "\t\t\t\t\t\t{\n"
    "\t\t\t\t\t\t\tstatic const struct { const char *p; byte id; } dc_wtbl[] = {\n"
    "\t\t\t\t\t\t\t\t{\"p_p228\",1},{\"p_scout\",3},{\"p_hegrenade\",4},{\"p_xm1014\",5},\n"
    "\t\t\t\t\t\t\t\t{\"p_c4\",6},{\"p_mac10\",7},{\"p_aug\",8},{\"p_smokegrenade\",9},\n"
    "\t\t\t\t\t\t\t\t{\"p_elite\",10},{\"p_fiveseven\",11},{\"p_ump45\",12},{\"p_sg550\",13},\n"
    "\t\t\t\t\t\t\t\t{\"p_galil\",14},{\"p_famas\",15},{\"p_usp\",16},{\"p_glock18\",17},\n"
    "\t\t\t\t\t\t\t\t{\"p_awp\",18},{\"p_mp5\",19},{\"p_m249\",20},{\"p_m3\",21},\n"
    "\t\t\t\t\t\t\t\t{\"p_m4a1\",22},{\"p_tmp\",23},{\"p_g3sg1\",24},{\"p_flashbang\",25},\n"
    "\t\t\t\t\t\t\t\t{\"p_deagle\",26},{\"p_sg552\",27},{\"p_ak47\",28},{\"p_knife\",29},\n"
    "\t\t\t\t\t\t\t\t{\"p_p90\",30},\n"
    "\t\t\t\t\t\t\t};\n"
    "\t\t\t\t\t\t\tbyte wbuf[3] = { 0, 0, 0 };\n"
    "\t\t\t\t\t\t\tmodel_t *pm = wm ? CL_ModelHandle( wm ) : NULL;\n"
    "\t\t\t\t\t\t\tif( pm && pm->name[0] )\n"
    "\t\t\t\t\t\t\t{\n"
    "\t\t\t\t\t\t\t\tsize_t di;\n"
    "\t\t\t\t\t\t\t\tfor( di = 0; di < sizeof( dc_wtbl ) / sizeof( dc_wtbl[0] ); di++ )\n"
    "\t\t\t\t\t\t\t\t\tif( Q_strstr( pm->name, dc_wtbl[di].p )) { wbuf[0] = 1; wbuf[1] = dc_wtbl[di].id; wbuf[2] = 1; break; }\n"
    "\t\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t\t/* wm=0 (chet/khong sung) -> state 0: an crosshair, dung nhu that */\n"
    "\t\t\t\t\t\t\tCL_DispatchUserMessage( \"CurWeapon\", 3, wbuf );\n"
    "\t\t\t\t\t\t\tdc_last_ent = democam_target; dc_last_wm = wm;\n"
    "\t\t\t\t\t\t}\n"
    "\t\t\t\t\t}\n"
    "\t\t\t\t}\n"
    "\t\t\t}\n"
    "\t\t\tclgame.dllFuncs.pfnTxferLocalOverrides( state, &frame->clientdata );\n"
    "\t\t}\n",
    "banner-target",
)

# --- 6. In-eye NHUONG han cho client dll ---
# Nho patch 5, g_iUser1=4/g_iUser2=target duoc bom moi khung -> bo may spectator
# cua cs16-client TU dung in-eye chuan: goc noi suy muot + VE SUNG (viewmodel tu
# weaponmodel trong entity state — demo luon co). Engine chi con de camera o che
# do chase. (Truoc day in-eye engine-override: khong sung, goc soc — cung goc
# loi voi banner: client dll khong biet dang spectate ai.)
patch(
    "cl_view.c",
    "	if( !cls.demoplayback || democam_target <= 0 )\n\t\treturn;\n\tent = CL_GetEntityByIndex( democam_target );",
    "	if( !cls.demoplayback || democam_target <= 0 )\n\t\treturn;\n"
    "\tif( !democam_chase )\n\t\treturn;   /* in-eye: client dll lo (xem patch 5) */\n"
    "\tent = CL_GetEntityByIndex( democam_target );",
    "ineye-client-dll",
)

print("democam.py: tat ca patch da ap")
