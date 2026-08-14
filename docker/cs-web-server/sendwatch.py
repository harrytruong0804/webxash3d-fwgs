#!/usr/bin/env python3
"""Bay chan doan cho cu KET DUONG GUI: dem xem NHANH NAO chan, roi in ra.

SU CO 2026-08-14 17:02:28 (pub Italy VN):
    sendrate = 0 cho ca 7 peer   (sendStats dem "engine YEU CAU gui")
    recvrate ~ 450/peer          (bridge van DAY goi vao hang doi)
    engine van in duoc lenh console `stuffto` luc 17:02:34
Khach dung hinh 59 giay roi selfheal moi restart. Lan truoc 11/8 09:10.

⚠️ BAN DAU TAO DAT BAY NHAM CHO. Nghi `if( !SV_RunGameFrame ()) return;` trong
Host_ServerFrame, vi no nam dung giua ReadPackets va SendClientMessages. Doc ky
hon thi thay `Cvar_RegisterVariable( &sv_fps )` bi boc trong `#if !XASH_DEDICATED`,
ma Dockerfile build bang `./waf configure -T release -d` (-d = --dedicated).
Kiem tren server DANG CHAY: `sv_fps` -> `Unknown command`. Tuc sv_fps.value = 0,
ma nhanh sv_fps==0 cua SV_RunGameFrame luon `return true`. NHANH DO KHONG BAO GIO
CHAY. Mot bay dat o do se im lang mai mai, va cai im lang ay khong chung minh gi
ca — dung kieu "cong luon-luon-mo" da ghi trong CLAUDE.md.

CHO DUNG la ben trong SV_SendClientMessages. No VAN duoc goi (RunGameFrame luon
true), nen viec khong ai nhan duoc gi chi con ba kha nang, va ca ba deu dem duoc:

  1. chua-den-luot : client khong co co FCL_SEND_NET_MESSAGE.
  2. qua-han-nhan  : `sv_failuretime` (do duoc tren prod = 0.5s) — engine NGUNG
                     gui cho ai qua 0.5 giay khong nhan duoc goi tu ho. Neu
                     engine ngung TIEU THU hang doi thi ca phong dinh cai nay
                     cung luc. Luu y recvrate cua SFU dem luc BRIDGE DAY VAO
                     (PushPacket), khong phai luc engine lay ra — nen
                     "recv>0" KHONG chung minh engine con nghe.
  3. nghen-bang-thong : `Netchan_CanPacket` false (cleartime o tuong lai).

In khi: co nguoi da spawn, khong gui duoc cho AI trong hon 2 giay. Toi da mot
lan moi 10 giay. Kem theo tung client: cach day bao lau moi nhan duoc goi cua
ho, cleartime con bao lau, choke bao nhieu — du de goi ten thu pham ngay lan
ket sau thay vi lai ngoi doan.

AN TOAN: chi dem va in, khong doi hanh vi. Luc chay binh thuong `sent > 0` moi
nhip nen khong bao gio in.
"""
import sys

P = "/xash/engine/server/sv_frame.c"
s = open(P).read()

FUNC = r"""
/* ==== CSGA: khong ai duoc gui trong >2 giay thi noi ro VI SAO ==== */
static void SV_CsgaSendAudit( int spawned, int sent, int noflag, int failtime, int choke )
{
	static double	lastsent = 0.0;
	static double	lastprint = 0.0;
	sv_client_t	*c;
	int		i;

	if( sent > 0 || spawned == 0 )
	{
		lastsent = host.realtime;
		return;
	}

	if( host.realtime - lastsent < 2.0 )
		return;
	if( host.realtime - lastprint < 10.0 )
		return;
	lastprint = host.realtime;

	Con_Printf( "[CSGA-WEDGE] %.1fs khong gui cho ai: nguoi=%d chua-den-luot=%d qua-han-nhan=%d nghen-bang-thong=%d sv.state=%d realtime=%.3f frametime=%.6f\n",
		host.realtime - lastsent, spawned, noflag, failtime, choke,
		(int)sv.state, host.realtime, host.frametime );

	for( i = 0; i < svs.maxclients; i++ )
	{
		c = &svs.clients[i];
		if( c->state <= cs_zombie || FBitSet( c->flags, FCL_FAKECLIENT ))
			continue;
		Con_Printf( "[CSGA-WEDGE]   p%d \"%s\" state=%d nhan-cach-day=%.3fs cleartime-con=%.3fs choke=%d\n",
			i, c->name, (int)c->state,
			host.realtime - c->netchan.last_received,
			c->netchan.cleartime - host.realtime,
			c->chokecount );
	}
}

"""

anchor_fn = "void SV_SendClientMessages( void )\n{"
if "SV_CsgaSendAudit" in s:
    print("  ham da co, bo qua")
elif anchor_fn not in s:
    sys.exit("KHONG TIM THAY SV_SendClientMessages")
else:
    s = s.replace(anchor_fn, FUNC + anchor_fn, 1)
    print("  chen ham xong")

# Bien dem: phai khai o DAU KHOI (C89) chu khong chen giua than ham.
anchor_decl = "\tdouble       time_until_next_message;\n"
decl = anchor_decl + "\tint          csga_spawned = 0, csga_sent = 0, csga_noflag = 0, csga_fail = 0, csga_choke = 0;\n"
if "csga_spawned" in s:
    print("  bien dem da co, bo qua")
elif anchor_decl not in s:
    sys.exit("KHONG TIM THAY khoi khai bao cua SV_SendClientMessages")
else:
    s = s.replace(anchor_decl, decl, 1)
    print("  them bien dem xong")

STEPS = [
    # dem nguoi da spawn (bo qua fakeclient va client chet)
    (
        "\t\tif( FBitSet( cl->flags, FCL_SKIP_NET_MESSAGE ))",
        "\t\tif( cl->state == cs_spawned )\n\t\t\tcsga_spawned++;\n\n"
        "\t\tif( FBitSet( cl->flags, FCL_SKIP_NET_MESSAGE ))",
        "csga_spawned++",
    ),
    # nhanh 2: qua han nhan (sv_failuretime)
    (
        "\t\t\tif( sv_failuretime.value < ( host.realtime - cl->netchan.last_received ))\n"
        "\t\t\t\tClearBits( cl->flags, FCL_SEND_NET_MESSAGE );",
        "\t\t\tif( sv_failuretime.value < ( host.realtime - cl->netchan.last_received ))\n"
        "\t\t\t{\n"
        "\t\t\t\tClearBits( cl->flags, FCL_SEND_NET_MESSAGE );\n"
        "\t\t\t\tcsga_fail++;\n"
        "\t\t\t}",
        "csga_fail++",
    ),
    # nhanh 1: chua den luot
    (
        "\t\t// only send messages if the client has sent one\n"
        "\t\t// and the bandwidth is not choked\n"
        "\t\tif( FBitSet( cl->flags, FCL_SEND_NET_MESSAGE ))",
        "\t\t// only send messages if the client has sent one\n"
        "\t\t// and the bandwidth is not choked\n"
        "\t\tif( !FBitSet( cl->flags, FCL_SEND_NET_MESSAGE ))\n"
        "\t\t\tcsga_noflag++;\n\n"
        "\t\tif( FBitSet( cl->flags, FCL_SEND_NET_MESSAGE ))",
        "csga_noflag++",
    ),
    # nhanh 3: nghen bang thong
    (
        "\t\t\t\tcl->chokecount++;",
        "\t\t\t\tcl->chokecount++;\n\t\t\t\tcsga_choke++;",
        "csga_choke++",
    ),
    # gui duoc that
    (
        "\t\t\telse Netchan_TransmitBits( &cl->netchan, 0, NULL ); // just update reliable",
        "\t\t\telse Netchan_TransmitBits( &cl->netchan, 0, NULL ); // just update reliable\n\n"
        "\t\t\tcsga_sent++;",
        "csga_sent++",
    ),
    # goi ham kiem o cuoi
    (
        "\t// reset current client\n\tsv.current_client = NULL;",
        "\tSV_CsgaSendAudit( csga_spawned, csga_sent, csga_noflag, csga_fail, csga_choke );\n\n"
        "\t// reset current client\n\tsv.current_client = NULL;",
        "SV_CsgaSendAudit( csga_spawned",
    ),
]

for anchor, repl, marker in STEPS:
    if marker in s:
        print(f"  {marker}: da co, bo qua")
    elif anchor not in s:
        sys.exit(f"KHONG TIM THAY mo neo cho {marker}")
    else:
        s = s.replace(anchor, repl, 1)
        print(f"  {marker}: xong")

open(P, "w").write(s)
print("sendwatch.py: xong")
