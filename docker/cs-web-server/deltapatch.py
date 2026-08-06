#!/usr/bin/env python3
"""Khai them truong per-player trong delta.lst — nua CONFIG cua serverfill.py.

delta.lst quyet dinh truong nao cua entity_state duoc ma hoa len mang. Bang
field cua engine (net_encode.c) DA co san velocity/fov/health/vuser1/vuser2 —
chi viec khai. Client tu hoc format moi qua svc_deltatable nen khong vo ai.

  velocity[0..2]  van toc (crosshair no khi chay)
  vuser1[0..2]    punchangle (giat sung) — engine do o serverfill.py
  vuser2[0..2]    v_angle (goc nhin THAT) — het suy pitch tu blending
  fov             zoom AWP/Scout
  health          mau (banner spectator)

Chi phi bang thong: ~0 khi dung yen (delta chi gui truong DOI), vai chuc bit/
nguoi/goi khi van dong — khong dang ke voi pub 16 slot.
"""
import sys

PATH = "/opt/xash/xashds/cstrike/delta.lst"

ANCHOR = "DEFINE_DELTA( usehull, DT_INTEGER, 1, 1.0 ),"
ADD = ANCHOR + """
\tDEFINE_DELTA( velocity[0], DT_SIGNED | DT_FLOAT, 16, 8.0 ),
\tDEFINE_DELTA( velocity[1], DT_SIGNED | DT_FLOAT, 16, 8.0 ),
\tDEFINE_DELTA( velocity[2], DT_SIGNED | DT_FLOAT, 16, 8.0 ),
\tDEFINE_DELTA( vuser1[0], DT_SIGNED | DT_FLOAT, 16, 8.0 ),
\tDEFINE_DELTA( vuser1[1], DT_SIGNED | DT_FLOAT, 16, 8.0 ),
\tDEFINE_DELTA( vuser1[2], DT_SIGNED | DT_FLOAT, 16, 8.0 ),
\tDEFINE_DELTA( vuser2[0], DT_ANGLE, 16, 1.0 ),
\tDEFINE_DELTA( vuser2[1], DT_ANGLE, 16, 1.0 ),
\tDEFINE_DELTA( vuser2[2], DT_ANGLE, 16, 1.0 ),
\tDEFINE_DELTA( fov, DT_FLOAT, 8, 1.0 ),
\tDEFINE_DELTA( health, DT_SIGNED | DT_FLOAT, 12, 1.0 ),"""

s = open(PATH).read()
i = s.find("entity_state_player_t")
j = s.find("}", i)
if i < 0 or j <= i:
    sys.exit("khong thay section entity_state_player_t")
seg = s[i:j]
if "vuser2[0]" in seg:
    print("deltapatch: da co, bo qua")
    sys.exit(0)
if ANCHOR not in seg:
    sys.exit("khong thay moc usehull trong section player")
s = s[:i] + seg.replace(ANCHOR, ADD, 1) + s[j:]
open(PATH, "w").write(s)
print("deltapatch: da khai velocity/vuser1/vuser2/fov/health cho player")
