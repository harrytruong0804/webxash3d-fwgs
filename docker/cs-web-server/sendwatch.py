#!/usr/bin/env python3
"""Bay chan doan cho cu KET DUONG GUI: engine ngung gui cho MOI nguoi cung luc.

SU CO 2026-08-14 17:02:28 (pub Italy VN). Do duoc tu bo dem cua SFU:
    sendrate = 0 cho ca 7 peer   (sendStats dem "engine YEU CAU gui")
    recvrate ~ 450/peer          (bridge van giao goi VAO engine)
    engine van in duoc lenh console `stuffto` luc 17:02:34
=> vong lap chinh con song, chi duong gui chet. Khach dung hinh 59 giay roi
selfheal moi restart. Lan truoc: 11/8 09:10. Hiem, nhung dat.

TRONG MA NGUON chi co DUNG MOT cho tao ra duoc bo ba do — Host_ServerFrame:

    SV_ReadPackets ();                  <- recvrate van chay
    ...
    if( !SV_RunGameFrame ()) return;    <- thoat o day
    SV_SendClientMessages ();           <- khong bao gio toi

`SV_RunGameFrame` tra false khi `sv.time_residual` chua du mot tick. Binh thuong
no false vai nhip lien tiep la cung (host chay ~1000fps, sv_fps 100 => nhieu
nhat ~9 nhip). Neu bien tich luy do hong (NaN, hoac am sau) thi no false VINH
VIEN — khop ca ba chung cu tren.

NHUNG DO LA GIA THUYET, CHUA CHUNG MINH. Va co mot cho tu mau thuan: host.frametime
bi kep `bound(MIN_FRAMETIME, ...)` nen ve ly khong the bang 0, tuc residual van
phai lon dan. Bay nay de KET LUAN thay vi doan tiep:
  - Neu lan ket sau in ra dong [CSGA-WEDGE] => dung cho nay, va con so
    residual/frametime noi ro bien nao hong.
  - Neu KET ma KHONG co dong nao => loai han nhanh nay, di tim cho khac.
Ca hai ket qua deu co gia tri; im lang moi la thu khong dung duoc.

AN TOAN: khong doi hanh vi gi. Chi dem va in. Nguong 600 nhip lien tiep + toi da
mot dong moi 10 giay nen luc chay binh thuong no khong bao gio in, khong the lam
phinh log.
"""
import sys

P = "/xash/engine/server/sv_main.c"
s = open(P).read()

FUNC = r"""
/* ==== CSGA: dem so nhip LIEN TIEP khong chay duoc game frame ====
 * ran = true  -> vua chay duoc mot frame, reset bo dem.
 * ran = false -> nhip nay khong gui gi cho ai ca (xem chu thich sendwatch.py).
 */
static void SV_CsgaSendWatch( qboolean ran )
{
	static int	misses = 0;
	static double	lastprint = 0.0;
	int		i, spawned = 0;

	if( ran )
	{
		misses = 0;
		return;
	}

	// Vai nhip truot lien tiep la BINH THUONG (host chay nhanh hon sv_fps).
	// 600 nhip lien tiep thi khong con binh thuong nua.
	if( ++misses < 600 )
		return;

	if( host.realtime - lastprint < 10.0 )
		return;
	lastprint = host.realtime;

	for( i = 0; i < svs.maxclients; i++ )
	{
		if( svs.clients[i].state == cs_spawned )
			spawned++;
	}

	Con_Printf( "[CSGA-WEDGE] khong gui duoc %d nhip lien tiep: residual=%.6f frametime=%.6f realtime=%.3f sim=%d state=%d sv_fps=%.2f nguoi=%d\n",
		misses, sv.time_residual, host.frametime, host.realtime,
		(int)sv.simulating, (int)sv.state, sv_fps.value, spawned );
}

"""

anchor_fn = "void Host_ServerFrame( void )\n{"
if "SV_CsgaSendWatch" in s:
    print("  ham da co, bo qua")
elif anchor_fn not in s:
    sys.exit("KHONG TIM THAY Host_ServerFrame")
else:
    s = s.replace(anchor_fn, FUNC + anchor_fn, 1)
    print("  chen ham xong")

# Goi o CA HAI nhanh: truot thi dem, chay duoc thi reset. Thieu ve reset la bo
# dem chi tang, som muon gi cung in ra bao dong gia.
anchor_call = "\tif( !SV_RunGameFrame ()) return;"
new_call = (
    "\tif( !SV_RunGameFrame ())\n"
    "\t{\n"
    "\t\tSV_CsgaSendWatch( false );\n"
    "\t\treturn;\n"
    "\t}\n"
    "\tSV_CsgaSendWatch( true );"
)
if "SV_CsgaSendWatch( false )" in s:
    print("  cho goi da vá, bo qua")
elif anchor_call not in s:
    sys.exit("KHONG TIM THAY cho goi SV_RunGameFrame trong Host_ServerFrame")
else:
    s = s.replace(anchor_call, new_call, 1)
    print("  vá cho goi xong")

open(P, "w").write(s)
print("sendwatch.py: xong")
