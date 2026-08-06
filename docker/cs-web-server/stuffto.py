#!/usr/bin/env python3
"""Them lenh server `stuffto <ten|#id> <lenh>` — bao MOT client chay mot lenh.

VI SAO CAN: `follow`/`specmode` la lenh CLIENT gui len server (ClientCommand xu
ly per-player). Kenh /control chay Cbuf_AddText o console SERVER, noi khong co
`follow` -> "Unknown command". Nen de doi muc tieu bam cua may ghi giua tran,
phai bao CHINH may ghi (client) chay lenh do.

Engine da co san co che: svc_stufftext gui mot chuoi lenh toi mot client de no
tu chay (giong stuffcmd cua HL). `stuffto` goi dung co che do, chon client bang
SV_ClientByName nhu lenh `kick`.

Dung: qua /control gui `stuffto REC follow "chicken (1)"` -> may ghi ten REC
chay `follow "chicken (1)"` -> chuyen sang bam nguoi vua giet.

An toan: chi them mot lenh console server moi, khong doi hanh vi cu. Muon goi
duoc van phai qua /control (co token).
"""
import sys

P = "/xash/engine/server/sv_cmds.c"
s = open(P).read()

FUNC = r"""
/* ==== CSGA stuffto: bao mot client chay mot lenh (svc_stufftext) ==== */
static void SV_StuffTo_f( void )
{
	sv_client_t	*cl;
	const char	*param, *p;

	if( Cmd_Argc() < 3 )
	{
		Con_Printf( "stuffto <#id|name> <command>\n" );
		return;
	}

	param = Cmd_Argv( 1 );
	if( *param == '#' && Q_isdigit( param + 1 ))
		cl = SV_ClientById( Q_atoi( param + 1 ));
	else
		cl = SV_ClientByName( param );

	if( !cl || cl->state != cs_spawned )
	{
		Con_Printf( "stuffto: client khong san sang\n" );
		return;
	}

	/* Cmd_Args() = "<target> <command...>" — bo token target dau tien, giu
	 * nguyen phan con lai (co ca dau nhay kep cho ten co khoang trang). */
	p = Cmd_Args();
	if( !COM_CheckString( p ))
		return;
	while( *p && *p != ' ' ) p++;
	while( *p == ' ' ) p++;
	if( !*p )
		return;

	MSG_WriteByte( &cl->netchan.message, svc_stufftext );
	MSG_WriteStringf( &cl->netchan.message, "%s\n", p );
	Con_Printf( "stuffto %s: %s\n", cl->name, p );
}
/* ==== het stuffto ==== */

"""

# Chen ham ngay truoc SV_InitOperatorCommands.
anchor_fn = "void SV_InitOperatorCommands( void )\n{"
if "SV_StuffTo_f" in s:
    print("  ham da co, bo qua")
elif anchor_fn not in s:
    sys.exit("KHONG TIM THAY SV_InitOperatorCommands")
else:
    s = s.replace(anchor_fn, FUNC + anchor_fn, 1)
    print("  chen ham xong")

# Dang lenh ngay sau dong dang `kick`.
anchor_reg = 'Cmd_AddCommand( "kick", SV_Kick_f, "kick a player off the server by number or name" );'
reg = anchor_reg + '\n\tCmd_AddCommand( "stuffto", SV_StuffTo_f, "CSGA: bao mot client chay mot lenh" );'
if "SV_StuffTo_f, " in s:
    print("  lenh da dang, bo qua")
elif anchor_reg not in s:
    sys.exit("KHONG TIM THAY dong dang kick")
else:
    s = s.replace(anchor_reg, reg, 1)
    print("  dang lenh xong")

open(P, "w").write(s)
print("stuffto.py: xong")
