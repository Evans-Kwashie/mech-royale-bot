package mech

import (
	"bufio"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"math"
	"math/rand"
	"os"
	"path/filepath"
	"sort"
	"testing"
	"time"
)

// TestLatency replays the official check stream, then 600 synthetic worst-case
// ticks (15 visible mechs, 30 projectiles, loot, sounds, a wounded self so the
// cover search runs), timing JSON decode + Act + encode per tick.
// Kit location: $MECHFIGHT_KIT (default ~/mechfight-kit).
func TestLatency(t *testing.T) {
	kit := os.Getenv("MECHFIGHT_KIT")
	if kit == "" {
		kit = filepath.Join(os.Getenv("HOME"), "mechfight-kit")
	}
	f, err := os.Open(filepath.Join(kit, "check", "stream.jsonl.gz"))
	if err != nil {
		t.Skip("no kit:", err)
	}
	defer f.Close()
	gz, err := gzip.NewReader(f)
	if err != nil {
		t.Fatal(err)
	}
	var hello Hello
	var lines [][]byte
	sc := bufio.NewScanner(gz)
	sc.Buffer(make([]byte, 1<<20), 1<<22)
	for sc.Scan() {
		l := append([]byte(nil), sc.Bytes()...)
		var p struct{ Type string }
		json.Unmarshal(l, &p)
		switch p.Type {
		case "hello":
			if err := json.Unmarshal(l, &hello); err != nil {
				t.Fatal(err)
			}
		case "obs":
			lines = append(lines, l)
		}
	}
	w, err := LoadWorld(filepath.Join(kit, "arena"))
	if err != nil {
		t.Fatal(err)
	}
	for _, cfg := range []struct {
		name string
		f    Flags
	}{{"flags=none", Flags{}}, {"flags=all", allFlags()}} {
		Active = cfg.f
		b := NewBrain(&hello, w)
		var replay []float64
		var last Obs
		for _, l := range lines {
			d, o := timeAct(b, l)
			replay = append(replay, d)
			last = o
		}
		syn := synthetic(b, last, 600)
		report(t, cfg.name+" replay", replay)
		report(t, cfg.name+" worst-case", syn)
	}
	Active = Flags{}
}

func allFlags() Flags {
	f, _ := ParseFlags("all")
	return f
}

func timeAct(b *Brain, line []byte) (float64, Obs) {
	start := time.Now()
	var o Obs
	json.Unmarshal(line, &o)
	a := b.Act(&o)
	json.Marshal(a)
	return float64(time.Since(start).Microseconds()) / 1000, o
}

func synthetic(b *Brain, base Obs, n int) []float64 {
	rng := rand.New(rand.NewSource(7))
	me := base.Self.Pos
	type mover struct{ x, y, vx, vy float64 }
	ms := make([]mover, 15)
	for i := range ms {
		a := rng.Float64() * 2 * math.Pi
		r := 20 + rng.Float64()*180
		ms[i] = mover{me[0] + math.Cos(a)*r, me[1] + math.Sin(a)*r, rng.NormFloat64() * 6, rng.NormFloat64() * 6}
	}
	var out []float64
	for k := 0; k < n; k++ {
		o := base
		o.Tick = base.Tick + 2*(k+1)
		o.T = base.T + 0.1*float64(k+1)
		o.Self.HP = o.Self.MaxHP * (0.3 + 0.4*float64(k%50)/50) // wounded: retreat/regen/cover paths
		o.Mechs = nil
		for i := range ms {
			m := &ms[i]
			m.x += m.vx * 0.1
			m.y += m.vy * 0.1
			ws := []string{"gun", "laser"}
			if i%3 == 1 {
				ws = []string{"gun", "lightning"}
			} else if i%3 == 2 {
				ws = []string{"gun", "mortar"}
			}
			z := b.W.GroundAt(m.x, m.y)
			o.Mechs = append(o.Mechs, MechSeen{ID: i + 1, Kind: "mech", Pos: Vec3{m.x, m.y, z}, Vel: Vec3{m.vx, m.vy, 0},
				Aim: [2]float64{math.Atan2(me[1]-m.y, me[0]-m.x) + rng.NormFloat64()*0.5, 0}, HP: 400 + float64(i)*60,
				MaxHP: 1400, Cubes: i % 12, Weapons: ws, Charging: (k+i)%7 == 0})
		}
		o.Projectiles = nil
		for i := 0; i < 30; i++ {
			kind := "gun"
			vz := 0.0
			if i%5 == 0 {
				kind, vz = "mortar", 20
			}
			a := rng.Float64() * 2 * math.Pi
			o.Projectiles = append(o.Projectiles, Proj{ID: 100000 + k*30 + i, Kind: kind,
				Pos: Vec3{me[0] + math.Cos(a)*40, me[1] + math.Sin(a)*40, me[2] + 6},
				Vel: Vec3{-math.Cos(a) * 200, -math.Sin(a) * 200, vz}})
		}
		o.Cubes, o.Crates, o.Pickups = nil, nil, nil
		for i := 0; i < 8; i++ { // loot that jumps around forces new path goals
			a := rng.Float64() * 2 * math.Pi
			p := Vec3{me[0] + math.Cos(a)*80, me[1] + math.Sin(a)*80, 0}
			p[2] = b.W.GroundAt(p[0], p[1])
			o.Cubes = append(o.Cubes, Item{ID: 5000 + k*8 + i, Pos: p})
			o.Crates = append(o.Crates, Item{ID: 1000 + i, Pos: p, HP: 300})
			o.Pickups = append(o.Pickups, Item{ID: 8000 + i, Kind: []string{"laser", "lightning", "mortar"}[i%3], Pos: p})
		}
		o.Sounds = []Sound{{Kind: "gun", Bearing: rng.Float64() * 6, Dist: "mid", Age: 0.05}, {Kind: "laser_charge", Bearing: 1, Dist: "near", Age: 0.1}}
		by := 1 + k%15
		bear := rng.Float64() * 6
		o.Events = []Event{{Type: "damaged", Amount: 45, Weapon: "gun", Bearing: &bear, By: &by}, {Type: "hit", Target: by, Amount: 45}}
		line, _ := json.Marshal(o)
		d, _ := timeAct(b, line)
		out = append(out, d)
	}
	return out
}

func report(t *testing.T, name string, ms []float64) {
	s := append([]float64(nil), ms...)
	sort.Float64s(s)
	q := func(p float64) float64 { return s[int(math.Min(float64(len(s)-1), p*float64(len(s))))] }
	msg := fmt.Sprintf("%-24s n=%d p50=%.2fms p95=%.2fms p99=%.2fms max=%.2fms", name, len(s), q(0.5), q(0.95), q(0.99), s[len(s)-1])
	t.Log(msg)
	fmt.Println(msg)
	if q(0.99) > 10 {
		t.Errorf("%s p99 %.2f ms exceeds 10 ms", name, q(0.99))
	}
}
