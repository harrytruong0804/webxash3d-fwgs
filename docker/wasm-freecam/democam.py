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
static int democam_target = 0;   /* entity index nguoi dang bam; 0 = tat */
static int democam_chase  = 0;   /* 1 = bam sau lung, 0 = goc nhin thu nhat */

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

print("democam.py: tat ca patch da ap")
