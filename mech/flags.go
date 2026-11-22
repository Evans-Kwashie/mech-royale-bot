package mech

import "strings"

// Flags gate each experimental behaviour on top of the 5.83 controller.
// Every flag defaults to off, so a zero Flags value plays exactly like 15b8438.
type Flags struct {
	LaserHold   bool // keep a charging laser on a target that just broke LOS instead of firing into cover
	CoverCache  bool // cache failed cover searches for 0.4 s (latency)
	CubeCap     bool // stop cube detours past stat_cap unless near an upgrade threshold; nanites-first upgrades
	FrontArmor  bool // idle aim faces attackers/sounds; prefer targets facing away from us
	PrePeek     bool // practice: pre-charge laser on a hidden foe in cover, then peek to release
	ModeDetect  bool // FFA detection needs 2 foreign deaths, or 1 before t=100
	StayInFight bool // looser swamped/crowd-hide thresholds (port of 1148655)
	RegenHold   bool // below 55% HP in zone: break LOS, hold fire until 85% (45 HP/s regen)
	DropPrep    bool // no drop-avoidance at home, opportunistic drops in FFA too
	LightTarget bool // lightning prefers charging lasers and chain clusters; laser prefers mortar holders
	DualPower   bool // swap the gun out for a second power weapon (laser + lightning)
}

// Active is applied to every new Brain. Set it before NewBrain.
var Active Flags

var flagNames = map[string]func(*Flags) *bool{
	"laserhold":   func(f *Flags) *bool { return &f.LaserHold },
	"covercache":  func(f *Flags) *bool { return &f.CoverCache },
	"cubecap":     func(f *Flags) *bool { return &f.CubeCap },
	"frontarmor":  func(f *Flags) *bool { return &f.FrontArmor },
	"prepeek":     func(f *Flags) *bool { return &f.PrePeek },
	"modedetect":  func(f *Flags) *bool { return &f.ModeDetect },
	"stayinfight": func(f *Flags) *bool { return &f.StayInFight },
	"regenhold":   func(f *Flags) *bool { return &f.RegenHold },
	"dropprep":    func(f *Flags) *bool { return &f.DropPrep },
	"lighttarget": func(f *Flags) *bool { return &f.LightTarget },
	"dualpower":   func(f *Flags) *bool { return &f.DualPower },
}

// ParseFlags reads a comma-separated list such as "laserhold,cubecap".
// "all" enables everything; unknown names are returned for logging.
func ParseFlags(s string) (Flags, []string) {
	var f Flags
	var unknown []string
	for _, k := range strings.FieldsFunc(s, func(r rune) bool { return r == ',' || r == ' ' }) {
		k = strings.ToLower(k)
		if k == "all" {
			for _, get := range flagNames {
				*get(&f) = true
			}
			continue
		}
		if get, ok := flagNames[k]; ok {
			*get(&f) = true
		} else {
			unknown = append(unknown, k)
		}
	}
	return f, unknown
}
