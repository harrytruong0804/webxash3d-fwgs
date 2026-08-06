package main

/*
Cầu UDP — cho một client THẬT nối vào engine qua mạng thường.

Vì sao cần: bản dựng này thay hẳn tầng mạng của engine bằng SFU, gói tin đi
thẳng từ WebRTC vào engine trong cùng tiến trình. Đo 2026-08-06 trên box VN:
container chỉ có ĐÚNG một socket UDP (27018 — cổng media ICE), còn 27015 mà
engine in ra lúc khởi động thì không hề tồn tại. Hệ quả là mọi công cụ của thế
giới GoldSrc đều mất đường vào: rcon, logaddress, HLTV, và bất kỳ client nào
không phải trình duyệt.

Cầu này mở lại đúng một cửa đó. Nó KHÔNG đụng vào đường đi của người chơi thật:
peer WebRTC vẫn nguyên như cũ, cầu chỉ cấp thêm peer từ hướng UDP.

Mục đích trước mắt: chạy một máy ghi demo ngay trên box game — máy ghi bắt buộc
là một client (ghi demo là code phía client, bản dedicated không có), mà client
thì cần một cửa để vào.

TẮT MẶC ĐỊNH. Không đặt UDP_GATE_PORT thì hàm này thoát ngay, hành vi của
container không đổi một chút nào.

⚠️ ĐỪNG publish cổng này ra Internet. Nó là đường vào engine KHÔNG qua xác thực
nào — đúng bằng mức bảo vệ của một server CS 1.6 trần. Để nguyên trong mạng
bridge của docker thì chỉ host và container cùng box với tới được, đó là điều
mình muốn.
*/

import (
	gonet "net" // "net" bi che boi bien package-level `net` (chinh la SFUNet)
	"os"
	"strconv"
	"sync"
	"sync/atomic"
	"time"

	goxash3d_fwgs "github.com/yohimik/goxash3d-fwgs/pkg"
)

// Sau ngần này không nhận được gói nào từ một địa chỉ UDP thì coi như nó đã đi,
// trả lại số hiệu peer cho bể dùng chung.
//
// Chọn 90 giây vì nó phải DÀI HƠN `sv_timeout` của engine (mặc định 60): engine
// mới là bên có quyền tuyên bố client chết. Thu hồi số hiệu sớm hơn engine thì
// số đó bị cấp lại cho người khác trong khi engine vẫn tưởng slot cũ còn sống —
// đúng loại lỗi mà bản vá `connections[index] = nil` hồi 29/7 đã phải đi dọn.
const udpGateIdle = 90 * time.Second

// Tran toc do MOI PEER. Khong co no thi mot client UDP du don gian la chay
// nhanh cung lam nghen ca server.
//
// Do that 2026-08-06: client xash chay khong man hinh (renderer rong, khong
// vsync) ban 26.000-30.000 goi/giay thay vi ~30. Cau noi Go<->engine rut goi
// tung cai mot co Delay() nen thong luong co han; hang doi 128 khe day ngay,
// engine ngung tra loi TAT CA — ke ca goi info tu mot dia chi khac — va khong
// tu hoi phuc sau khi client do bien mat. Ghim CPU container xuong 5% van con
// 1.100 goi/giay va van du lam nghen.
//
// 150/giay la ~5 lan nhip binh thuong cua mot nguoi choi (cl_cmdrate 30), du
// rong cho client tu do lag ma van chan duoc bao goi. Netchan tu chiu duoc mat
// goi — day chinh la thu no duoc thiet ke de xu ly.
const (
	udpGateRate  = 150.0 // goi/giay moi peer
	udpGateBurst = 60.0  // cho phep don cuc ngan luc bat tay
)

// udpPeer đóng vai io.Writer để cắm vừa vào bảng `connections` mà SendTo dùng.
// Nhờ vậy engine gửi cho client UDP y hệt cách nó gửi cho peer WebRTC, không có
// nhánh rẽ nào trong đường truyền nóng.
type udpPeer struct {
	conn *gonet.UDPConn
	addr *gonet.UDPAddr
}

func (p *udpPeer) Write(b []byte) (int, error) {
	return p.conn.WriteToUDP(b, p.addr)
}

type udpClient struct {
	index byte
	// ip giữ NGUYÊN suốt đời phiên: engine định danh client bằng cả địa chỉ, đổi
	// giữa chừng là nó coi như một người hoàn toàn khác và bắt kết nối lại.
	ip   [4]byte
	seen time.Time
	got  int

	// Gao token cho tran toc do.
	tokens   float64
	refilled time.Time
	dropped  int64
}

// min: Go cua image nay chua chac co ban dung sang generic built-in.
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func runUDPGate() {
	raw := os.Getenv("UDP_GATE_PORT")
	if raw == "" {
		return
	}
	port, err := strconv.Atoi(raw)
	if err != nil || port <= 0 || port > 65535 {
		log.Errorf("udpgate: UDP_GATE_PORT khong hop le: %q", raw)
		return
	}

	conn, err := gonet.ListenUDP("udp4", &gonet.UDPAddr{IP: gonet.IPv4zero, Port: port})
	if err != nil {
		log.Errorf("udpgate: khong mo duoc %d/udp: %v", port, err)
		return
	}
	log.Errorf("udpgate: dang nghe tren 0.0.0.0:%d/udp", port)

	var mu sync.Mutex
	clients := map[string]*udpClient{}

	// Dọn client im lặng. Chạy riêng để vòng đọc dưới không phải kiểm tra gì
	// ngoài việc chuyển gói — đó là đường đi nóng nhất của cả tiến trình.
	go func() {
		for range time.NewTicker(15 * time.Second).C {
			now := time.Now()
			mu.Lock()
			for key, c := range clients {
				if now.Sub(c.seen) < udpGateIdle {
					continue
				}
				connections[c.index] = nil
				_ = pool.TryPut(c.index)
				delete(clients, key)
				log.Errorf("udpgate: peer %d (%s) im lang qua lau, tra lai so hieu", c.index, key)
			}
			mu.Unlock()
		}
	}()

	buf := make([]byte, messageSize)
	for {
		n, raddr, err := conn.ReadFromUDP(buf)
		if err != nil {
			log.Errorf("udpgate: loi doc: %v", err)
			continue
		}
		key := raddr.String()

		mu.Lock()
		c, ok := clients[key]
		if !ok {
			index, err := pool.TryGet()
			if err != nil {
				mu.Unlock()
				// Hết số hiệu nghĩa là 256 peer đang sống — bỏ gói còn hơn cấp
				// trùng số với một người đang chơi.
				continue
			}
			c = &udpClient{index: index}
			// Octet đầu LÀ số hiệu peer (xem SendTo: `index := packet.Addr.IP[0]`).
			// Ba octet sau chỉ để phân biệt trong log, engine không dùng tới.
			c.ip = [4]byte{index, 127, 0, 1}
			clients[key] = c
			connections[index] = &udpPeer{conn: conn, addr: raddr}
			log.Errorf("udpgate: peer %d = %s", index, key)
		}
		now := time.Now()
		if c.refilled.IsZero() {
			c.refilled = now
			c.tokens = udpGateBurst
		}
		c.tokens += now.Sub(c.refilled).Seconds() * udpGateRate
		if c.tokens > udpGateBurst {
			c.tokens = udpGateBurst
		}
		c.refilled = now
		if c.tokens < 1 {
			c.dropped++
			// In thua thot: luc bao goi thi moi giay co hang chuc nghin lan
			// vao day, log day du se chon box nhanh hon chinh cai bao goi.
			if c.dropped%20000 == 1 {
				log.Errorf("udpgate: peer %d vuot toc do, da bo %d goi", c.index, c.dropped)
			}
			c.seen = now
			mu.Unlock()
			continue
		}
		c.tokens--
		c.seen = now
		c.got++
		ip := c.ip
		nth := c.got
		mu.Unlock()

		// Đếm gói VÀO cho peer UDP, đối xứng với sendrate — không có nó thì khi
		// engine ngừng trả lời (đo 2026-08-06: client xash nối vào là engine câm
		// vĩnh viễn) không tách được "gói không tới engine" với "tới rồi mà
		// engine không xử lý". Đúng bài học của recvrate hồi 31/7.
		atomic.AddInt64(&recvStats[ip[0]].calls, 1)
		atomic.AddInt64(&recvStats[ip[0]].bytes, int64(n))

		// Vài gói đầu của mỗi peer in ra nguyên văn. Client xash bắt tay khác
		// hẳn trình duyệt, mà chính lúc bắt tay là lúc engine tắc — cần biết
		// gói cuối cùng nó nhận được là gói nào.
		if nth <= 3 {
			log.Errorf("udpgate: peer %d goi #%d (%dB): %q", ip[0], nth, n, string(buf[:min(n, 48)]))
		}

		// Sao chép: buf được dùng lại ngay vòng sau, mà gói đi vào hàng đợi và
		// được engine đọc ở luồng khác, muộn hơn.
		data := make([]byte, n)
		copy(data, buf[:n])

		// Hàng đợi giữa Go và engine chỉ có 128 khe. Nếu Enqueue kẹt ở đây thì
		// thủ phạm là hàng đợi đầy (engine ngừng rút), còn nếu nó trả về ngay
		// mà engine vẫn câm thì thủ phạm nằm trong engine — hai kết luận trái
		// ngược, không đo thì chỉ có đoán.
		t0 := time.Now()
		net.PushPacket(goxash3d_fwgs.Packet{
			Addr: goxash3d_fwgs.Addr{IP: ip, Port: 1000},
			Data: data,
		})
		if d := time.Since(t0); d > 50*time.Millisecond {
			log.Errorf("udpgate: PushPacket ket %v (peer %d, goi #%d) — hang doi day", d, ip[0], nth)
		}
	}
}
