package main

/*
Kênh gửi lệnh console vào server đang chạy.

VÌ SAO CẦN: bản dựng này nhúng engine thành thư viện, thay tầng mạng bằng SFU,
và KHÔNG mở stdin cho container. Đo 2026-08-06: không có socket UDP nào ngoài
cổng media ICE, nên rcon cũng không tới được. Hệ quả là mọi thay đổi — đổi cvar,
đổi map, kick một người — đều phải restart container, tức là đá hết người đang
chơi.

Việc cần ngay: kick máy ghi demo ra để nó đóng file tử tế. Đọc trong
engine/client/cl_main.c thì `CL_Shutdown()` KHÔNG gọi `CL_Disconnect()` cũng
không gọi `CL_Stop_f()` — nên client thoát kiểu gì (SIGTERM, cả lệnh `quit`)
demo cũng mất bảng mục lục và không phát lại được. Đường duy nhất đóng demo
đúng cách là `CL_Stop_f`, mà nó chỉ chạy từ lệnh `stop`, lệnh `disconnect`,
hoặc `CL_Drop()` — cái cuối chính là lúc server gửi `svc_disconnect`, tức là
KICK. Nên `kick` từ server là cách duy nhất không phải vá file bằng tay.

AN TOÀN LUỒNG: engine gọi `RecvFrom()` — hàm Go này — trên CHÍNH luồng của nó,
mỗi khung hình. Nên chỗ đó là điểm duy nhất chắc chắn đang ở trong luồng engine
mà không phải tự dựng cơ chế đồng bộ nào. Gọi `Cbuf_AddText` từ goroutine của
HTTP là chạm vào bộ nhớ engine từ luồng khác — sớm muộn cũng hỏng theo kiểu khó
lần ra. Vì vậy HTTP chỉ NHÉT lệnh vào hàng đợi, còn việc chèn thật nằm ở
`RecvFrom`.

`Cbuf_AddText` chỉ nối chuỗi vào bộ đệm lệnh; engine tự chạy nó ở `Cbuf_Execute`
trong khung hình kế tiếp. Nên hàm này không thực thi gì ngay, và đó là điều tốt:
không có lệnh nào chạy giữa chừng một khung.
*/

// #include <stdlib.h>
// extern void Cbuf_AddText(const char *text);
import "C"

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"sync"
	"unsafe"

	goxash3d_fwgs "github.com/yohimik/goxash3d-fwgs/pkg"
)

// Hàng đợi lệnh chờ được chèn vào engine. Có trần để một client hỏng (hoặc kẻ
// phá) không nhồi được vô hạn vào bộ nhớ.
const controlQueueMax = 64

var (
	controlMu    sync.Mutex
	controlQueue []string
	controlToken = os.Getenv("CONTROL_TOKEN")
)

// enqueueCommand xếp lệnh vào hàng đợi. Trả về false khi hàng đầy.
func enqueueCommand(cmd string) bool {
	controlMu.Lock()
	defer controlMu.Unlock()
	if len(controlQueue) >= controlQueueMax {
		return false
	}
	controlQueue = append(controlQueue, cmd)
	return true
}

// drainCommands lấy hết lệnh đang chờ. CHỈ được gọi từ luồng engine.
func drainCommands() []string {
	controlMu.Lock()
	defer controlMu.Unlock()
	if len(controlQueue) == 0 {
		return nil
	}
	out := controlQueue
	controlQueue = nil
	return out
}

// RecvFrom ghi đè hàm của BaseNet để mượn luồng engine.
//
// Engine gọi hàm này mỗi khung hình để hỏi "có gói nào đến không". Trước khi
// trả lời, ta chèn nốt các lệnh đang chờ — lúc này chắc chắn đang ở luồng
// engine. Phần còn lại giao nguyên cho BaseNet, không đổi hành vi mạng.
func (n *SFUNet) RecvFrom() *goxash3d_fwgs.Packet {
	if cmds := drainCommands(); cmds != nil {
		for _, c := range cmds {
			cs := C.CString(c + "\n")
			C.Cbuf_AddText(cs)
			C.free(unsafe.Pointer(cs))
			log.Errorf("control: da chen lenh %q", c)
		}
	}
	return n.BaseNet.RecvFrom()
}

/*
controlHandler nhận lệnh qua HTTP.

	POST /control   {"cmd": "kick Player"}
	Header: X-Control-Token: <CONTROL_TOKEN>

TẮT MẶC ĐỊNH: không đặt CONTROL_TOKEN thì trả 404 y như đường dẫn không tồn tại
— không hé lộ là có cửa này. Cổng 27016 chỉ publish về 127.0.0.1 nên chỉ tiến
trình trên cùng box gọi được, nhưng token vẫn cần: mọi thứ trong container đều
gọi được tới cổng đó.
*/
func controlHandler(w http.ResponseWriter, r *http.Request) {
	if controlToken == "" {
		http.NotFound(w, r)
		return
	}
	if r.Method != http.MethodPost {
		http.Error(w, "chi nhan POST", http.StatusMethodNotAllowed)
		return
	}
	if r.Header.Get("X-Control-Token") != controlToken {
		http.Error(w, "sai token", http.StatusForbidden)
		return
	}

	var body struct {
		Cmd string `json:"cmd"`
	}
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 4096)).Decode(&body); err != nil {
		http.Error(w, "json hong", http.StatusBadRequest)
		return
	}

	cmd := strings.TrimSpace(body.Cmd)
	// Xuống dòng là ký tự phân tách lệnh của console: lọt vào là một request
	// gửi được nhiều lệnh, kể cả lệnh mình không định cho phép.
	if cmd == "" || strings.ContainsAny(cmd, "\n\r;") || len(cmd) > 256 {
		http.Error(w, "lenh khong hop le", http.StatusBadRequest)
		return
	}

	if !enqueueCommand(cmd) {
		http.Error(w, "hang doi day", http.StatusServiceUnavailable)
		return
	}
	w.Header().Set("content-type", "application/json")
	_, _ = w.Write([]byte(`{"ok":true}`))
}
