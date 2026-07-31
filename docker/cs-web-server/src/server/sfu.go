package main

import (
	"encoding/json"
	"fmt"
	"github.com/gorilla/websocket"
	"github.com/jinzhu/configor"
	"github.com/pion/ice/v4"
	"github.com/pion/interceptor"
	"github.com/pion/logging"
	"github.com/pion/rtcp"
	"github.com/pion/rtp"
	"github.com/pion/webrtc/v4"
	"github.com/yohimik/goxash3d-fwgs/pkg"
	"io"
	"math/rand"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

var net = NewSFUNet()

type SFUNet struct {
	*goxash3d_fwgs.BaseNet
}

func NewSFUNet() *SFUNet {
	return &SFUNet{
		BaseNet: goxash3d_fwgs.NewBaseNet(goxash3d_fwgs.BaseNetOptions{
			HostName: "webxash",
			HostID:   3000,
		}),
	}
}

// sendStats counts what the engine actually asks us to deliver, per peer.
//
// Needed because logging only FAILURES cannot distinguish the two remaining
// explanations for a player who silently stops receiving game data: either the
// engine stopped addressing packets to them, or it kept sending and every write
// reported success while nothing arrived. One says the fault is above the SFU,
// the other says it is inside it.
var sendStats [256]struct {
	calls int64
	bytes int64
}

// recvStats counts packets handed TO the engine (PushPacket in ReadLoop).
//
// Added after the 2026-07-31 05:52 incident: sendrate proved the engine stopped
// ADDRESSING packets to all five players at once, but that left two suspects it
// cannot tell apart — the bridge stopped delivering incoming packets (engine
// starved, then timed everyone out), or delivery continued and the engine went
// deaf on its own. recvrate is the other half: recv>0 while send=0 pins the
// wedge inside the engine; recv=0 pins it in the bridge.
var recvStats [256]struct {
	calls int64
	bytes int64
}

func init() {
	go func() {
		for {
			time.Sleep(10 * time.Second)
			line := ""
			for i := 0; i < 256; i++ {
				c := atomic.SwapInt64(&sendStats[i].calls, 0)
				b := atomic.SwapInt64(&sendStats[i].bytes, 0)
				if c == 0 && connections[i] == nil {
					continue
				}
				line += fmt.Sprintf(" p%d=%d/%dB", i, c, b)
			}
			if line != "" {
				log.Errorf("sendrate:%s", line)
			}
			line = ""
			for i := 0; i < 256; i++ {
				c := atomic.SwapInt64(&recvStats[i].calls, 0)
				b := atomic.SwapInt64(&recvStats[i].bytes, 0)
				// Same rule as sendrate: a LIVE peer at zero must be printed —
				// the zeros are the whole point during a wedge.
				if c == 0 && connections[i] == nil {
					continue
				}
				line += fmt.Sprintf(" p%d=%d/%dB", i, c, b)
			}
			if line != "" {
				log.Errorf("recvrate:%s", line)
			}
		}
	}()
}

// sendComplain rate-limits the diagnostics below: SendTo runs per packet
// (tens per second per player), so logging every failure would bury the box.
var sendComplain [256]time.Time

func complain(index byte, format string, args ...any) {
	now := time.Now()
	if now.Sub(sendComplain[index]) < 5*time.Second {
		return
	}
	sendComplain[index] = now
	log.Errorf(format, args...)
}

func (n *SFUNet) SendTo(fd int, packet goxash3d_fwgs.Packet, flags int) int {
	index := packet.Addr.IP[0]
	conn := connections[index]
	// Both failures below used to be entirely silent, which made the worst
	// production symptom impossible to diagnose: a player stops receiving game
	// data while ICE, SCTP and the WebSocket all stay healthy, so every log and
	// every server-side counter looks normal.
	//
	// Measured 2026-07-28: a peer that had been playing for 27 minutes went to
	// exactly zero game bytes (only 30s SCTP heartbeats left, RTT 3ms) about 35
	// seconds after ANOTHER peer opened its data channels, and never recovered.
	// These two lines separate the two possible causes — if neither fires, the
	// engine simply stopped addressing packets to that player and the fault is
	// above the SFU.
	/* KHÔNG trả -1 khi peer đã biến mất.
	 *
	 * Hàm này giả lập `sendto()` cho engine, và -1 nghĩa là SOCKET HỎNG. Nhưng
	 * với UDP thật, gửi tới một peer đã rời đi không bao giờ lỗi — gói chỉ rơi
	 * vào hư không. Trả -1 là nói dối engine rằng tầng mạng của nó chết, trong
	 * khi thực tế chỉ là một người thoát.
	 *
	 * Đo 2026-07-29: hai người đang chơi, một người lag rồi văng, ngay sau đó
	 * người còn lại ngừng nhận dữ liệu dù WebRTC của họ vẫn nguyên vẹn. Server
	 * kẹt cho tới khi restart. Đây là nhánh cuối của họ lỗi "một người rời đi
	 * làm hỏng người còn lại" — ba bản vá trước chặn ở tầng SFU, nhưng cái -1
	 * này vẫn lọt xuống tận engine.
	 *
	 * Engine vẫn biết peer đã đi, qua `sv_timeout` — đúng cơ chế được thiết kế
	 * cho việc đó, thay vì suy ra từ một lỗi socket giả.
	 */
	if conn == nil {
		complain(index, "SendTo: no connection for peer %d (da roi di, bo goi)", index)

		return len(packet.Data)
	}
	nn, err := conn.Write(packet.Data)
	if err != nil {
		complain(index, "SendTo: write failed for peer %d: %v", index, err)

		return len(packet.Data)
	}
	atomic.AddInt64(&sendStats[index].calls, 1)
	atomic.AddInt64(&sendStats[index].bytes, int64(nn))
	return nn
}

// SendToBatch delivers each packet independently.
//
// It used to `return -1` on the first failing peer, which DISCARDED every
// remaining packet in the batch — packets addressed to perfectly healthy
// players. One player closing their browser tab was therefore enough to starve
// everyone else in the room: the game server keeps that player's slot for its
// disconnect timeout (~60s), and during that whole window every outgoing batch
// aborted at the dead peer. With several players leaving at once the room never
// recovered and no one could join until the container was restarted.
//
// A failing peer now only loses its own packet.
func (n *SFUNet) SendToBatch(fd int, packets []goxash3d_fwgs.Packet, flags int) int {
	sum := 0
	for _, packet := range packets {
		nn := n.SendTo(fd, packet, flags)
		if nn == -1 {
			continue
		}
		sum += nn
	}
	return sum
}

var pool = goxash3d_fwgs.NewBytesPool(256)
var connections = make([]io.Writer, 256)

var (
	addr     = ":27016"
	upgrader = websocket.Upgrader{
		CheckOrigin: func(r *http.Request) bool { return true },
	}

	api *webrtc.API

	// lock for peerConnections and trackLocals
	listLock        sync.RWMutex
	peerConnections []*peerConnectionState
	trackLocals     map[string]*webrtc.TrackLocalStaticRTP

	log = logging.NewDefaultLoggerFactory().NewLogger("sfu-ws")
)

type websocketMessage struct {
	Event string          `json:"event"`
	Data  json.RawMessage `json:"data"`
}

type peerConnectionState struct {
	peerConnection *webrtc.PeerConnection
	websocket      *threadSafeWriter
	signalsCount   int
}

const DefaultSignalsCount = 5

const (
	// Well under the ~60s idle window most NAT/firewall boxes use for TCP.
	pingInterval = 20 * time.Second
	// Deliberately six missed pings, not one or two.
	//
	// This deadline is the only change here that can kill a session the old
	// code would have kept alive, so it is tuned to catch genuinely dead peers
	// and nothing else. A tight value would turn any unforeseen problem with
	// pong delivery into every player dropping on a timer — worse than the bug
	// being fixed. When it does fire, the existing "Failed to read message"
	// log line reports an i/o timeout, which is enough to diagnose from
	// `docker logs`.
	pongWait = 120 * time.Second
)

// Add to list of tracks and fire renegotation for all PeerConnections.
func addTrack(t *webrtc.TrackRemote) *webrtc.TrackLocalStaticRTP { // nolint
	listLock.Lock()
	defer func() {
		listLock.Unlock()
		signalPeerConnections()
	}()

	// Create a new TrackLocal with the same codec as our incoming
	trackLocal, err := webrtc.NewTrackLocalStaticRTP(t.Codec().RTPCodecCapability, t.ID(), t.StreamID())
	if err != nil {
		panic(err)
	}

	trackLocals[t.ID()] = trackLocal

	for _, con := range peerConnections {
		con.signalsCount = DefaultSignalsCount
	}

	return trackLocal
}

// Remove from list of tracks and fire renegotation for all PeerConnections.
func removeTrack(t *webrtc.TrackLocalStaticRTP) {
	listLock.Lock()
	defer func() {
		listLock.Unlock()
		signalPeerConnections()
	}()

	for _, con := range peerConnections {
		con.signalsCount = DefaultSignalsCount
	}

	delete(trackLocals, t.ID())
}

// signalPeerConnections updates each PeerConnection so that it is getting all the expected media tracks.
func signalPeerConnections() { // nolint
	listLock.Lock()
	defer func() {
		listLock.Unlock()
		dispatchKeyFrame()
	}()

	attemptSync := func() (tryAgain bool) {
		for i := range peerConnections {
			// Prune closed peers FIRST. This check used to sit *after* the
			// `signalsCount <= 0` guard below, so any peer that finished
			// signalling — i.e. every successfully connected player — was
			// skipped by `continue` and never removed from the global slice,
			// even long after it closed.
			if peerConnections[i].peerConnection.ConnectionState() == webrtc.PeerConnectionStateClosed {
				peerConnections = append(peerConnections[:i], peerConnections[i+1:]...)

				return true // We modified the slice, start from the beginning
			}

			if peerConnections[i].signalsCount <= 0 {
				continue
			}

			// map of sender we already are seanding, so we don't double send
			existingSenders := map[string]bool{}

			for _, sender := range peerConnections[i].peerConnection.GetSenders() {
				if sender.Track() == nil {
					continue
				}

				existingSenders[sender.Track().ID()] = true

				// If we have a RTPSender that doesn't map to a existing track remove and signal
				if _, ok := trackLocals[sender.Track().ID()]; !ok {
					if err := peerConnections[i].peerConnection.RemoveTrack(sender); err != nil {
						return true
					}
				}
			}

			// Don't receive videos we are sending, make sure we don't have loopback
			for _, receiver := range peerConnections[i].peerConnection.GetReceivers() {
				if receiver.Track() == nil {
					continue
				}

				existingSenders[receiver.Track().ID()] = true
			}

			// Add all track we aren't sending yet to the PeerConnection
			for trackID := range trackLocals {
				if _, ok := existingSenders[trackID]; !ok {
					if _, err := peerConnections[i].peerConnection.AddTrack(trackLocals[trackID]); err != nil {
						return true
					}
				}
			}

			// Offering is PER PEER: a failure here must not abandon the peers
			// after this one in the slice.
			//
			// These three used to `return true`, which aborted the whole scan.
			// One peer stuck mid-signalling — it got an offer and never answered,
			// so it sits in `have-local-offer` and every later CreateOffer /
			// SetLocalDescription on it fails — therefore blocked EVERY later
			// joiner from receiving an offer at all. Not transiently: the retry
			// below re-runs the same scan, hits the same peer, and aborts at the
			// same place, forever. The only escape was that peer's WebSocket
			// finally dying.
			//
			// Measured on a test container before this fix: peer A connects and
			// stalls, peer B connects 5s later and receives nothing for its
			// entire 60s life, while a lone peer gets its offer in 0.1s.
			//
			// Still sets tryAgain so a broken peer is retried, but `continue`
			// means everyone else is served in this same pass.
			offer, err := peerConnections[i].peerConnection.CreateOffer(nil)
			if err != nil {
				log.Errorf("CreateOffer failed for peer %d: %v", i, err)
				tryAgain = true

				continue
			}

			if err = peerConnections[i].peerConnection.SetLocalDescription(offer); err != nil {
				log.Errorf("SetLocalDescription failed for peer %d: %v", i, err)
				tryAgain = true

				continue
			}

			if err = peerConnections[i].websocket.WriteJSON("offer", offer); err != nil {
				log.Errorf("Failed to send offer to peer %d: %v", i, err)
				tryAgain = true

				continue
			}
		}

		return tryAgain
	}

	for syncAttempt := 0; ; syncAttempt++ {
		if syncAttempt == 25 {
			// Release the lock and attempt a sync in 3 seconds. We might be blocking a RemoveTrack or AddTrack
			go func() {
				time.Sleep(time.Second * 3)
				signalPeerConnections()
			}()

			return
		}

		if !attemptSync() {
			break
		}
	}
}

// dispatchKeyFrame sends a keyframe to all PeerConnections, used everytime a new user joins the call.
func dispatchKeyFrame() {
	listLock.Lock()
	defer listLock.Unlock()

	for i := range peerConnections {
		for _, receiver := range peerConnections[i].peerConnection.GetReceivers() {
			if receiver.Track() == nil {
				continue
			}

			_ = peerConnections[i].peerConnection.WriteRTCP([]rtcp.Packet{
				&rtcp.PictureLossIndication{
					MediaSSRC: uint32(receiver.Track().SSRC()),
				},
			})
		}
	}
}

const messageSize = 1024 * 8

func ReadLoop(d io.Reader, ip [4]byte) {
	for {
		buffer := make([]byte, messageSize)
		n, err := d.Read(buffer)
		if err != nil {
			fmt.Println("Datachannel closed; Exit the readloop:", err)

			return
		}
		atomic.AddInt64(&recvStats[ip[0]].calls, 1)
		atomic.AddInt64(&recvStats[ip[0]].bytes, int64(n))
		net.PushPacket(goxash3d_fwgs.Packet{
			Addr: goxash3d_fwgs.Addr{
				IP:   ip,
				Port: 1000,
			},
			Data: buffer[:n],
		})
	}
}

// Handle incoming websockets.
func websocketHandler(w http.ResponseWriter, r *http.Request) { // nolint
	// Upgrade HTTP request to Websocket
	unsafeConn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Errorf("Failed to upgrade HTTP to Websocket: ", err)

		return
	}

	c := &threadSafeWriter{unsafeConn, sync.Mutex{}} // nolint

	// When this frame returns close the Websocket
	defer c.Close() //nolint

	// Create new PeerConnection
	peerConnection, err := api.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		log.Errorf("Failed to creates a PeerConnection: %v", err)

		return
	}

	// When this frame returns close the PeerConnection
	defer peerConnection.Close() //nolint

	// Accept one audio track incoming
	for _, typ := range []webrtc.RTPCodecType{webrtc.RTPCodecTypeAudio} {
		if _, err := peerConnection.AddTransceiverFromKind(typ, webrtc.RTPTransceiverInit{
			Direction: webrtc.RTPTransceiverDirectionRecvonly,
		}); err != nil {
			log.Errorf("Failed to add transceiver: %v", err)

			return
		}
	}

	f := false
	var z uint16 = 0
	if err != nil {
		log.Errorf("Failed to creates a data channel: %v", err)

		return
	}
	ip := [4]byte{}
	for i := range ip {
		ip[i] = byte(rand.Intn(256))
	}
	index, _ := pool.TryGet()
	ip[0] = index
	defer pool.TryPut(index)
	// Clear the routing entry when this peer goes away. Without it the dead
	// writer stays in `connections` forever, so every later send to that index
	// fails — and the index is recycled to a future player while still pointing
	// at the old, closed data channel.
	defer func() { connections[index] = nil }()
	// Without these the numeric peer index in the SendTo diagnostics cannot be
	// tied to a person or to the join/leave timeline.
	log.Errorf("peer %d: allocated", index)
	defer log.Errorf("peer %d: released", index)

	writeChannel, err := peerConnection.CreateDataChannel("write", &webrtc.DataChannelInit{
		Ordered:        &f,
		MaxRetransmits: &z,
	})
	if err != nil {
		log.Errorf("Failed to creates a data channel: %v", err)

		return
	}
	var readChannel *webrtc.DataChannel
	defer func() {
		if readChannel != nil {
			readChannel.Close()
		}
	}()
	writeChannel.OnOpen(func() {
		d, err := writeChannel.Detach()
		if err != nil {
			panic(err)
		}
		connections[index] = d
		log.Errorf("peer %d: routing live", index)

		rc, err := peerConnection.CreateDataChannel("read", &webrtc.DataChannelInit{
			Ordered:        &f,
			MaxRetransmits: &z,
		})
		if err != nil {
			log.Errorf("Failed to creates a data channel: %v", err)

			return
		}
		readChannel = rc
		readChannel.OnOpen(func() {
			d, err := readChannel.Detach()
			if err != nil {
				panic(err)
			}
			go ReadLoop(d, ip)
		})
	})
	defer writeChannel.Close()

	// Trickle ICE. Emit server candidate to client
	peerConnection.OnICECandidate(func(i *webrtc.ICECandidate) {
		if i == nil {
			return
		}
		// If you are serializing a candidate make sure to use ToJSON
		// Using Marshal will result in errors around `sdpMid`

		if writeErr := c.WriteJSON("candidate", i.ToJSON()); writeErr != nil {
			log.Errorf("Failed to write JSON: %v", writeErr)
		}
	})

	// If PeerConnection is closed remove it from global list
	peerConnection.OnConnectionStateChange(func(p webrtc.PeerConnectionState) {
		switch p {
		case webrtc.PeerConnectionStateFailed:
			if err := peerConnection.Close(); err != nil {
				log.Errorf("Failed to close PeerConnection: %v", err)
			}
		case webrtc.PeerConnectionStateClosed:
			signalPeerConnections()
		default:
		}
	})

	peerConnection.OnTrack(func(t *webrtc.TrackRemote, _ *webrtc.RTPReceiver) {
		// Create a track to fan out our incoming video to all peers
		trackLocal := addTrack(t)
		defer removeTrack(trackLocal)

		buf := make([]byte, 1500)
		rtpPkt := &rtp.Packet{}

		for {
			i, _, err := t.Read(buf)
			if err != nil {
				return
			}

			if err = rtpPkt.Unmarshal(buf[:i]); err != nil {
				log.Errorf("Failed to unmarshal incoming RTP packet: %v", err)

				return
			}

			rtpPkt.Extension = false
			rtpPkt.Extensions = nil

			if err = trackLocal.WriteRTP(rtpPkt); err != nil {
				return
			}
		}
	})

	// Add our new PeerConnection to global list
	state := peerConnectionState{peerConnection, c, DefaultSignalsCount}
	listLock.Lock()
	peerConnections = append(peerConnections, &state)
	listLock.Unlock()

	// Signal for the new PeerConnection
	signalPeerConnections()

	// Keep the signalling socket alive.
	//
	// The whole game session dies with this WebSocket: when ReadMessage returns
	// an error this handler exits and the deferred peerConnection.Close() tears
	// down the data channels, even though WebRTC itself was perfectly healthy.
	// After the handshake the socket goes completely idle for the rest of the
	// match, so any middlebox that reaps idle TCP — home routers, mobile
	// carriers, corporate firewalls, reverse proxies — silently kills the game.
	// See upstream issue #30 ("Game freezes after few seconds when using nginx
	// reverse proxy").
	//
	// A server-side ping is the right place for this: browsers answer ping
	// frames automatically, so no client change is needed and older clients get
	// the fix for free.
	stopPing := make(chan struct{})
	defer close(stopPing)
	go func() {
		ticker := time.NewTicker(pingInterval)
		defer ticker.Stop()
		for {
			select {
			case <-stopPing:
				return
			case <-ticker.C:
				// WriteControl, not WriteMessage: gorilla allows only one
				// concurrent writer and threadSafeWriter's mutex only guards
				// WriteJSON, so a plain write from this goroutine could race the
				// signalling writes. WriteControl is explicitly safe to call
				// concurrently with every other method.
				if err := c.WriteControl(
					websocket.PingMessage, nil, time.Now().Add(10*time.Second),
				); err != nil {
					return
				}
			}
		}
	}()

	// A peer that stops answering pings is gone; without a deadline the handler
	// would block on ReadMessage forever and leak the peer, its pool index and
	// its slot in the global list.
	_ = c.SetReadDeadline(time.Now().Add(pongWait))
	c.SetPongHandler(func(string) error {
		return c.SetReadDeadline(time.Now().Add(pongWait))
	})

	message := &websocketMessage{}
	for {
		_, raw, err := c.ReadMessage()
		if err != nil {
			log.Errorf("Failed to read message: %v", err)

			return
		}

		if err := json.Unmarshal(raw, &message); err != nil {
			log.Errorf("Failed to unmarshal json to message: %v", err)

			return
		}

		switch message.Event {
		case "candidate":
			candidate := webrtc.ICECandidateInit{}
			if err := json.Unmarshal(message.Data, &candidate); err != nil {
				log.Errorf("Failed to unmarshal json to candidate: %v", err)

				return
			}

			if err := peerConnection.AddICECandidate(candidate); err != nil {
				log.Errorf("Failed to add ICE candidate: %v", err)

				return
			}
		case "answer":
			answer := webrtc.SessionDescription{}
			if err := json.Unmarshal(message.Data, &answer); err != nil {
				log.Errorf("Failed to unmarshal json to answer: %v", err)

				return
			}

			if err := peerConnection.SetRemoteDescription(answer); err != nil {
				log.Errorf("Failed to set remote description: %v", err)

				return
			}
			listLock.Lock()
			state.signalsCount -= 1
			isNeedSignaling := state.signalsCount > 0
			listLock.Unlock()
			if isNeedSignaling {
				signalPeerConnections()
			}
		default:
			log.Errorf("unknown message: %+v", message)
		}
	}
}

// Helper to make Gorilla Websockets threadsafe.
type threadSafeWriter struct {
	*websocket.Conn
	sync.Mutex
}

func (t *threadSafeWriter) WriteJSON(event string, v interface{}) error {
	t.Lock()
	defer t.Unlock()

	return t.Conn.WriteJSON(struct {
		Event string `json:"event"`
		Data  any    `json:"data"`
	}{event, v})
}

const html = ""

func indexHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html")
	fmt.Fprint(w, html)
}

// Config holds the application configuration
type Config struct {
	Engine struct {
		Arguments string `env:"ENGINE_ARGS" required:"false"`
		Console   string `env:"ENGINE_CONSOLE" required:"false"`
		GameDir   string `env:"GAME_DIR" required:"true"`
	}
	Libraries struct {
		Client           string `env:"CLIENT_WASM_PATH" required:"true"`
		Server           string `env:"SERVER_WASM_PATH" required:"true"`
		Menu             string `env:"MENU_WASM_PATH" required:"true"`
		Extras           string `env:"EXTRAS_PATH" required:"true"`
		Filesystem       string `env:"FILESYSTEM_WASM_PATH" required:"true"`
		DynamicLibraries string `env:"DYNAMIC_LIBRARIES" required:"true"`
		FilesMap         string `env:"FILES_MAP" required:"true"`
	}
}

// EngineConfig holds the configuration for the Xash3D engine (JSON response)
type EngineConfig struct {
	Arguments        []string          `json:"arguments"`
	Console          []string          `json:"console"`
	GameDir          string            `json:"game_dir"`
	Libraries        map[string]string `json:"libraries"`
	DynamicLibraries []string          `json:"dynamic_libraries"`
	FilesMap         map[string]string `json:"files_map"`
}

var (
	appConfig        Config
	engineConfigJSON []byte
)

// configHandler returns the pre-serialized engine configuration
func configHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Write(engineConfigJSON)
}

// sliceArgs converts a comma-separated string into a slice of strings
func sliceArgs(value string) []string {
	if value == "" {
		return []string{}
	}
	parts := strings.Split(value, ",")
	result := make([]string, 0, len(parts))
	for _, part := range parts {
		if trimmed := strings.TrimSpace(part); trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
}

// parseFilesMap converts "from:to,from:to" format into map[string]string
func parseFilesMap(value string) map[string]string {
	result := make(map[string]string)
	if value == "" {
		return result
	}
	pairs := strings.Split(value, ",")
	for _, pair := range pairs {
		parts := strings.SplitN(strings.TrimSpace(pair), ":", 2)
		if len(parts) == 2 {
			result[strings.TrimSpace(parts[0])] = strings.TrimSpace(parts[1])
		}
	}
	return result
}

type Server struct {
}

var disabledXPoweredBy = false
var xPoweredByValue = "yohimik"

func init() {
	// Load server configuration
	disable, _ := os.LookupEnv("DISABLE_X_POWERED_BY")
	if disable == "true" {
		disabledXPoweredBy = true
	}
	xPoweredValue, has := os.LookupEnv("X_POWERED_BY_VALUE")
	if has {
		xPoweredByValue = xPoweredValue
	}

	// Load engine configuration using configor
	if err := configor.Load(&appConfig); err != nil {
		log.Errorf("Failed to load configuration: %v", err)
		panic(err)
	}

	// Build and serialize the engine config JSON once
	engineConfig := EngineConfig{
		Arguments: sliceArgs(appConfig.Engine.Arguments),
		Console:   sliceArgs(appConfig.Engine.Console),
		GameDir:   appConfig.Engine.GameDir,
		Libraries: map[string]string{
			"client":     appConfig.Libraries.Client,
			"server":     appConfig.Libraries.Server,
			"extras":     appConfig.Libraries.Extras,
			"menu":       appConfig.Libraries.Menu,
			"filesystem": appConfig.Libraries.Filesystem,
		},
		DynamicLibraries: sliceArgs(appConfig.Libraries.DynamicLibraries),
		FilesMap:         parseFilesMap(appConfig.Libraries.FilesMap),
	}

	var err error
	engineConfigJSON, err = json.Marshal(engineConfig)
	if err != nil {
		log.Errorf("Failed to serialize config: %v", err)
		panic(err)
	}
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if !disabledXPoweredBy {
		w.Header().Set("X-Powered-By", xPoweredByValue)
	}
	switch r.URL.Path {
	case "/websocket":
		websocketHandler(w, r)
	case "/config":
		configHandler(w, r)
	default:
		p := r.URL.Path
		if r.URL.Path == "/" {
			p = "index.html"
		}
		path := filepath.Join("public", p)
		if _, err := os.Stat(path); os.IsNotExist(err) {
			http.NotFound(w, r)
			return
		}
		http.ServeFile(w, r, path)
	}
}

func runSFU() {
	settingEngine := webrtc.SettingEngine{}
	settingEngine.DetachDataChannels()

	port, ok := os.LookupEnv("PORT")
	if ok {
		p, err := strconv.Atoi(port)
		if err == nil {
			udpMux, err := ice.NewMultiUDPMuxFromPort(p)
			if err != nil {
				panic(err)
			}
			settingEngine.SetICEUDPMux(udpMux)
		}
	}

	ip, ok := os.LookupEnv("IP")
	if ok {
		settingEngine.SetNAT1To1IPs([]string{ip}, webrtc.ICECandidateTypeHost)
	}

	m := &webrtc.MediaEngine{}
	err := m.RegisterDefaultCodecs()
	if err != nil {
		panic(err)
	}

	i := &interceptor.Registry{}
	err = webrtc.RegisterDefaultInterceptors(m, i)
	if err != nil {
		panic(err)
	}
	api = webrtc.NewAPI(webrtc.WithSettingEngine(settingEngine), webrtc.WithMediaEngine(m), webrtc.WithInterceptorRegistry(i))

	// Init other state
	trackLocals = map[string]*webrtc.TrackLocalStaticRTP{}

	// request a keyframe every 3 seconds
	go func() {
		for range time.NewTicker(time.Second * 3).C {
			dispatchKeyFrame()
		}
	}()

	// start HTTP server
	if err := http.ListenAndServe(addr, &Server{}); err != nil { //nolint: gosec
		log.Errorf("Failed to start http server: %v", err)
	}
}
