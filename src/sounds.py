import sys
import math

try:
    import mido
    from mido import MidiFile, MidiTrack, Message, MetaMessage
except:
    pass

list_notes = ("c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b")


def putNotes(note_len, state, tones, result):
    if len(result.keys()) == 0:
        result["note"] = ""
        result["tone"] = ""
        result["volume"] = ""
        result["effect"] = ""
    tone = tones[state["tone"]]
    pattern = state["pattern"]
    decay = pattern["decay"] if pattern and "decay" in pattern else tone["decay"]
    sustain = (
        pattern["sustain"] if pattern and "sustain" in pattern else tone["sustain"]
    )
    velocity = pattern["velocity"] / 100 if pattern else 1.0
    loops = int((note_len + state["tick"]) / 48) - int(state["tick"] / 48)
    for _ in range(loops):
        level = 0
        state["duration"] += 1
        duration = state["duration"]
        if (
            not state["is_rest"]
            and duration > note_len / 48 * state["note_cnt"] * state["quantize"]
        ):
            state["is_rest"] = True
            state["duration"] = 0
            duration = 1
        if state["is_rest"]:
            release = tone["release"] if "release" in tone else 0
            if duration < release:
                level = sustain / 100 * (1 - duration / release)
            else:
                level = 0
                state["note"] = -1
        else:
            if duration < tone["attack"]:
                level = duration / tone["attack"]
            elif duration < tone["attack"] + decay:
                level = 1 - (1 - sustain / 100) * ((duration - tone["attack"]) / decay)
            else:
                level = sustain / 100
        if pattern:
            notes = pattern["notes"]
            note = notes[min(duration, len(notes)) - 1]
            state["note"] = note
            note_str = list_notes[note % 12] + str(note // 12)
        elif state["note"] is None or state["note"] < 0:
            note_str = "r"
        else:
            note = state["note"]
            note_str = list_notes[note % 12] + str(note // 12)
        skipVib = tone["wave"] in ["S", "T"] and duration % 2 != 0
        vibrato = tone["vibrato"] if "vibrato" in tone else 0
        effect = "n" if vibrato == 0 or duration < vibrato or skipVib else "v"
        volume = min(math.ceil(level * state["volume"] * velocity), 7)
        result["note"] += note_str
        result["tone"] += pattern["wave"] if pattern else tone["wave"]
        result["volume"] += str(volume)
        result["effect"] += effect


# Pyxel再生データの生成
def compile(src, tones, patterns):
    speed = 240
    note_len = 48
    states = []
    results = []
    for _ in range(4):
        states.append(
            {
                "note_cnt": 0,
                "tone": 0,
                "volume": 7,
                "quantize": 1.0,
                "duration": 0,
                "note": -1,
                "is_rest": True,
                "pattern": None,
                "tick": 0,
            }
        )
        results.append({})
    for row, item in enumerate(src):
        if not item[0] is None:
            old_speed = speed
            speed = item[0]
            note_len = note_len / old_speed * speed
        if not item[2] is None:
            note_len = speed * item[2]
        for ch in range(4):
            state = states[ch]
            item_idx = 3 + ch * 4
            if not item[item_idx] is None:
                state["tone"] = item[item_idx]
            if not item[item_idx + 1] is None:
                state["volume"] = item[item_idx + 1]
            if not item[item_idx + 2] is None:
                state["quantize"] = item[item_idx + 2] / 16
            note = item[item_idx + 3]
            if not note is None:
                state["pattern"] = None
                for pattern in patterns:
                    if pattern["key"] == note:
                        state["pattern"] = pattern
                state["duration"] = 0
                if note == -1:
                    state["is_rest"] = True
                else:
                    state["is_rest"] = False
                    state["note"] = note if state["pattern"] is None else None
                note_cnt = 0
                while True:
                    note_cnt += 1
                    if row + note_cnt >= len(src):
                        break
                    nextItem = src[row + note_cnt]
                    if not nextItem[item_idx + 3] is None:
                        break
                state["note_cnt"] = note_cnt
            putNotes(note_len, state, tones, results[ch])
            state["tick"] += note_len
    sounds = []
    for ch in range(4):
        sound = results[ch]
        if sound["note"]:
            sounds.append(
                [
                    sound["note"],
                    shorten(sound["tone"]),
                    shorten(sound["volume"]),
                    shorten(sound["effect"]),
                    1,
                ]
            )
        else:
            sounds.append(None)
    return sounds


# Pyxel再生データの生成
def make_midi(src, outPath):
    mid = MidiFile()
    tracks = [None, None, None, None]
    has_note = [False, False, False, False]
    tones = [None, None, None, None]
    notes = [-1, -1, -1, -1]
    note_time = [0, 0, 0, 0]
    rest_time = [0, 0, 0, 0]
    volumes = [7, 7, 7, 7]
    quantize = [15, 15, 15, 15]
    bpm = 120
    note_len = 480

    def make_track(ch):
        if tracks[ch] is None:
            tracks[ch] = MidiTrack()
            tracks[ch].append(MetaMessage("set_tempo", tempo=bpm))

    def put_note(ch, new_note):
        make_track(ch)
        note = notes[ch]
        if note_time[ch] and note != -1:
            midi_time = (note_time[ch] * quantize[ch]) // 16
            tracks[ch].append(
                Message(
                    "note_off",
                    note=note,
                    velocity=64,
                    time=midi_time,
                    channel=ch,
                )
            )
            rest_time[ch] = note_time[ch] - midi_time
        if type(new_note) is str and new_note[0] == ":":
            midi_note = {
                ":1": 36,
                ":2": 38,
                ":3": 42,
                ":5": 45,
                ":6": 47,
                ":7": 50,
            }[new_note]
            tracks[ch].append(
                Message(
                    "note_on",
                    note=midi_note,
                    velocity=volumes[ch] * 16,
                    time=rest_time[ch],
                    channel=9,
                )
            )
            tracks[ch].append(
                Message(
                    "note_off",
                    note=midi_note,
                    velocity=64,
                    time=40,
                    channel=9,
                )
            )
            has_note[ch] = True
            rest_time[ch] = -40
            notes[ch] = -1
        elif new_note == -1:
            notes[ch] = -1
        else:
            midi_note = 36 + new_note
            tracks[ch].append(
                Message(
                    "note_on",
                    note=midi_note,
                    velocity=volumes[ch] * 16,
                    time=rest_time[ch],
                    channel=ch,
                )
            )
            has_note[ch] = True
            notes[ch] = midi_note
        note_time[ch] = 0

    for item in src:
        if not item[0] is None:
            # TODO:テンポ変更はいったん考慮しない
            bpm = mido.bpm2tempo(28800 // item[0])
        if not item[2] is None:
            note_len = item[2] * 40
        for ch in range(4):
            idx = (0, 8, 4, 12)[ch]
            if not item[idx + 3] is None:  # 音色
                make_track(ch)
                tone = item[idx + 3]
                tones[ch] = tone
                if tone != 15:
                    tracks[ch].append(Message("program_change", program=6, channel=ch))
            if not item[idx + 4] is None:  # ボリューム
                make_track(ch)
                volumes[ch] = item[idx + 4]
            if not item[idx + 5] is None:  # クオンタイズ
                make_track(ch)
                quantize[ch] = item[idx + 5]
            note = item[idx + 6]  # ノート。-1休符、None継続、0〜実音

            if notes[ch] == -1:
                if not note is None and note != -1:
                    put_note(ch, note)
            else:
                if not note is None:
                    put_note(ch, note)
            if notes[ch] == -1:
                rest_time[ch] += note_len
            else:
                note_time[ch] += note_len
    for ch in range(4):
        put_note(ch, -1)
        if has_note[ch]:
            mid.tracks.append(tracks[ch])
    mid.save(outPath)


def shorten(s):
    head = s[0:1]
    for idx in range(len(s)):
        if s[idx : idx + 1] != head:
            return s
    return head


def raise_error(msg):
    print(msg)
    sys.exit()
