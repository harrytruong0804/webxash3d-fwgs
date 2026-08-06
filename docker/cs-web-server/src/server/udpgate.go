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
		c.seen = time.Now()
		ip := c.ip
		mu.Unlock()

		// Sao chép: buf được dùng lại ngay vòng sau, mà gói đi vào hàng đợi và
		// được engine đọc ở luồng khác, muộn hơn.
		data := make([]byte, n)
		copy(data, buf[:n])

		net.PushPacket(goxash3d_fwgs.Packet{
			Addr: goxash3d_fwgs.Addr{IP: ip, Port: 1000},
			Data: data,
		})
	}
}
