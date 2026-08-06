package main

import goxash3d_fwgs "github.com/yohimik/goxash3d-fwgs/pkg"

func main() {
	goxash3d_fwgs.DefaultXash3D.Net = net

	go runSFU()

	// Cua vao bang UDP thuong, cho client khong phai trinh duyet (may ghi demo).
	// Tu thoat neu khong dat UDP_GATE_PORT — mac dinh khong doi gi.
	go runUDPGate()

	goxash3d_fwgs.DefaultXash3D.SysStart()
}
