# title: 8bit BGM generator
# author: frenchbread
# desc: A Pyxel music auto-generation tool
# site: https://github.com/shiromofufactory/8bit-bgm-generator
# license: MIT
# version: 1.21
import pyxel as px
import json
import sounds
import os
from bdf import BDFRenderer

SUBMELODY_DIFF = 0
SUB_RHYTHM = [0, None, 0, None, 0, None, 0, None, 0, None, 0, None, 0, None, 0, None]

LOCAL = False
try:
    from js import Blob, URL, document, window
except:
    LOCAL = True

# カラー定義
COL_BACK_PRIMARY = 7
COL_BACK_SECONDARY = 12
COL_BTN_BASIC = 5
COL_BTN_SELECTED = 6
COL_BTN_DISABLED = 13
COL_TEXT_BASIC = 1
COL_TEXT_MUTED = 5
COL_SHADOW = 0

# 生成する曲の小節数（8固定）
BARS_NUMBERS = 8

# パラメータ指定用
list_instrumentation = [
    (0, "Melo(with reverb) & Bass"),
    (1, "Melo & Bass & Drums"),
    (2, "Melo & Bass & Sub"),
    (3, "Full (Melo & Bass & Sub & Drums)"),
]
list_tones = [
    (11, "Pulse solid"),
    (8, "Pulse thin"),
    (2, "Pulse soft"),
    (10, "Square solid"),
    (6, "Square thin (Harp)"),
    (4, "Square soft (Flute)"),
]
list_melo_lowest_note = [
    (28, "E2"),
    (29, "F2"),
    (30, "F#2"),
    (31, "G2"),
    (32, "G#2"),
    (33, "A2"),
]
list_melo_use16 = [(True, "Yes"), (False, "No")]
list_melo_density = [(0, "less"), (2, "normal"), (4, "more")]


# 部品
class Element:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def mouse_in(self):
        mx = px.mouse_x
        my = px.mouse_y
        return (
            mx >= self.x
            and mx < self.x + self.w
            and my >= self.y
            and my < self.y + self.h
        )


# タブ
class Tab(Element):
    def __init__(self, idx, x, y, text):
        super().__init__(x, y, 64, 12)
        self.idx = idx
        self.text = text

    def draw(self, app):
        active = self.idx == app.tab
        rect_c = COL_BACK_PRIMARY if active else COL_BACK_SECONDARY
        text_c = COL_TEXT_BASIC if active else COL_TEXT_MUTED
        px.rect(self.x, self.y, self.w, self.h, rect_c)
        text_info = app.get_text(self.text)
        x = int(self.x + self.w / 2 - text_info[1])
        y = int(self.y + self.h / 2 - 4)
        app.text(x, y, self.text, text_c)


# アイコン
class Icon(Element):
    def __init__(self, id, x, y):
        super().__init__(x, y, 16, 12)
        self.id = id
        self.state = 0

    def draw(self, app):
        state = 0
        if self.id == 0:
            state = 1 if px.play_pos(0) else 0
        elif self.id == 1:
            state = 1 if not px.play_pos(0) else 0
        elif self.id == 2:
            state = 1 if app.loop else 0
        elif self.id == 3:
            state = 1 if app.show_export else 0
        px.blt(self.x, self.y, 0, self.id * 16, state * 16, self.w, self.h, 0)
        self.state = state


# ボタン
class Button(Element):
    def __init__(self, tab, type, key, x, y, w, text, disable_cond=0):
        super().__init__(x, y, w, 10)
        self.tab = tab
        self.type = type
        self.key = key
        self.x = x
        self.y = y
        self.w = w
        self.text = text
        self.disable_cond = disable_cond
        self.selected = False

    def draw(self, app):
        if not self.visible(app):
            return
        text_s = str(self.text)
        if self.disabled(app):
            rect_c = COL_BTN_DISABLED
        elif app.parm[self.type] == self.key:
            rect_c = COL_BTN_SELECTED
        else:
            rect_c = COL_BTN_BASIC
        text_c = COL_TEXT_BASIC
        px.rect(self.x, self.y, self.w - 1, self.h - 1, rect_c)
        px.text(
            self.x + self.w / 2 - len(text_s) * 2,
            self.y + self.h / 2 - 3,
            text_s,
            text_c,
        )

    def visible(self, app):
        return self.tab is None or app.tab == self.tab

    def disabled(self, app):
        org = app.parm["instrumentation"]
        return (self.disable_cond == 1 and org in (0, 2)) or (
            self.disable_cond == 2 and org in (0, 1)
        )


# アプリ
class App:
    def __init__(self):
        output_path = os.path.abspath(".")
        if output_path.endswith("src"):
            self.output_path = output_path + "/../export"
        else:
            self.output_path = output_path + "/export"
        self.output_json = "music.json"
        self.output_midi = "music.mid"
        self.failed_export_midi = False
        px.init(256, 256, title="8bit BGM generator", quit_key=px.KEY_NONE)
        px.load("assets.pyxres")
        self.bdf = BDFRenderer("misaki_gothic.bdf")
        self.parm = {
            "preset": 0,
            "transpose": 0,
            "language": 1,
            "base_highest_note": 26,  # ベース（ルート）最高音
            "melo_density": 4,  # メロディ濃度(0-4)
        }
        self.loop = True
        with open("tones.json", "rt", encoding="utf-8") as fin:
            self.tones = json.loads(fin.read())
        with open("patterns.json", "rt", encoding="utf-8") as fin:
            self.patterns = json.loads(fin.read())
        with open("generator.json", "rt", encoding="utf-8") as fin:
            self.generator = json.loads(fin.read())
        with open("rhythm.json", "rt", encoding="utf-8") as fin:
            self.melo_rhythm = json.loads(fin.read())
        # タブ、共通ボタン、アイコン
        self.tabs = []
        self.buttons = []
        self.icons = []
        list_tab = (0, 1, 2)
        list_language = ("Japanese", "English")
        for i, elm in enumerate(list_tab):
            self.set_tab(i, i * 64 + 4, 20, elm)
        for i in range(4 if LOCAL else 5):
            self.set_icon(i, 4 + i * 20, 4)
        for i, elm in enumerate(list_language):
            self.set_btn(None, "language", i, 116 + 48 * i, 6, 48, elm)
        # 基本タブ
        for i, elm in enumerate(self.generator["preset"]):
            self.set_btn(0, "preset", i, 8 + 24 * i, 50, 24, i + 1)
        for i in range(12):
            key = (i + 6) % 12 - 11
            self.set_btn(0, "transpose", key, 8 + 20 * i, 114, 20, i - 5)
        for i, elm in enumerate(list_instrumentation):
            self.set_btn(0, "instrumentation", elm[0], 8, 144 + i * 10, 144, elm[1])
        # コードとリズムタブ
        list_speed = [360, 312, 276, 240, 216, 192, 168, 156]
        list_base_quantize = [12, 13, 14, 15]
        for i, elm in enumerate(list_speed):
            self.set_btn(1, "speed", elm, 8 + 24 * i, 50, 24, int(28800 / elm))
        for i, elm in enumerate(self.generator["chords"]):
            self.set_btn(1, "chord", i, 8 + 24 * i, 80, 24, i + 1)
        for i, elm in enumerate(self.generator["base"]):
            self.set_btn(1, "base", i, 8 + 24 * i, 110, 24, i + 1)
        for i, elm in enumerate(list_base_quantize):
            quantize = str(int(elm * 100 / 16)) + "%"
            self.set_btn(1, "base_quantize", elm, 8 + 24 * i, 140, 24, quantize)
        for i, elm in enumerate(self.generator["drums"]):
            self.set_btn(1, "drums", i, 8 + 24 * i, 170, 24, i + 1, 1)
        # メロディータブ
        for i, elm in enumerate(list_tones):
            self.set_btn(2, "melo_tone", i, 8 + 24 * i, 50, 24, i + 1)
        for i, elm in enumerate(list_tones):
            self.set_btn(2, "sub_tone", i, 8 + 24 * i, 80, 24, i + 1, 2)
        for i, elm in enumerate(list_melo_lowest_note):
            self.set_btn(2, "melo_lowest_note", elm[0], 8 + 24 * i, 110, 24, elm[1])
        for i, elm in enumerate(list_melo_density):
            self.set_btn(2, "melo_density", elm[0], 8 + 48 * i, 140, 48, elm[1])
        for i, elm in enumerate(list_melo_use16):
            self.set_btn(2, "melo_use16", elm[0], 8 + 24 * i, 170, 24, elm[1])
        self.items = []
        self.set_preset(self.parm["preset"])
        self.play()
        self.saved_playkey = [-1, -1, -1]
        self.show_export = None
        self.tab = 0
        px.mouse(True)
        px.run(self.update, self.draw)

    @property
    def total_len(self):
        return BARS_NUMBERS * 16

    @property
    def with_submelody(self):
        return self.parm["instrumentation"] in (2, 3)

    @property
    def with_drum(self):
        return self.parm["instrumentation"] in (1, 3)

    def set_tab(self, *args):
        self.tabs.append(Tab(*args))

    def set_icon(self, *args):
        self.icons.append(Icon(*args))

    def set_btn(self, *args):
        self.buttons.append(Button(*args))

    def update(self):
        if not px.btnp(px.MOUSE_BUTTON_LEFT):
            return
        if self.show_export:
            self.show_export = None
            return
        for tab in self.tabs:
            if tab.mouse_in():
                self.tab = tab.idx
        for icon in self.icons:
            if icon.mouse_in():
                if icon.id == 0 and icon.state == 0:
                    self.play()
                elif icon.id == 1 and icon.state == 0:
                    px.stop()
                elif icon.id == 2:
                    self.loop = not self.loop
                    if px.play_pos(0):
                        self.play()
                elif icon.id == 3:
                    if LOCAL:
                        with open(
                            f"{self.output_path}/{self.output_json}", "wt"
                        ) as fout:
                            fout.write(json.dumps(self.music))
                        try:
                            sounds.make_midi(
                                self.items, f"{self.output_path}/{self.output_midi}"
                            )
                        except:
                            self.failed_export_midi = True
                            print(
                                "MIDIファイルを出力できませんでした。midoをインストールしてください。"
                            )
                    else:
                        blob = Blob.new(self.music, {"type": "text/plain"})
                        blob_url = URL.createObjectURL(blob)
                        a = document.createElement("a")
                        a.href = blob_url
                        a.download = self.output_json
                        document.body.appendChild(a)
                        a.click()
                        document.body.removeChild(a)
                        URL.revokeObjectURL(blob_url)
                    self.show_export = True
                elif icon.id == 4:
                    window.open(
                        "https://github.com/shiromofufactory/8bit-bgm-generator#readme"
                    )
        for button in self.buttons:
            if button.visible(self) and button.mouse_in():
                prev_value = self.parm[button.type]
                self.parm[button.type] = button.key
                if button.type == "language":
                    return
                if button.type == "preset":
                    self.set_preset(button.key)
                else:
                    make_melody = button.type in [
                        "transpose",
                        "instrumentation",
                        "chord",
                        "base",
                        "melo_lowest_note",
                        "melo_density",
                        "melo_use16",
                    ]
                    # サブ音色変更時、Beforeがサブなしだったらメロディ再生成する
                    if button.type == "sub_tone":
                        if (prev_value < 0 and button.key >= 0) or (
                            prev_value >= 0 and button.key < 0
                        ):
                            make_melody = True
                    self.generate_music(make_melody)
                self.play()

    def draw(self):
        px.cls(COL_BACK_SECONDARY)
        px.rect(4, 32, 248, 184, COL_BACK_PRIMARY)
        px.text(220, 8, "ver 1.21", COL_TEXT_MUTED)
        if self.tab == 0:
            self.text(8, 40, 3, COL_TEXT_BASIC)
            px.rectb(8, 64, 240, 32, COL_TEXT_MUTED)
            self.text(16, 68, 4, COL_TEXT_MUTED)
            self.text(16, 76, 5, COL_TEXT_MUTED)
            self.text(16, 84, 6, COL_TEXT_MUTED)
            self.text(8, 104, 7, COL_TEXT_BASIC)
            self.text(8, 134, 8, COL_TEXT_BASIC)
            px.rectb(8, 188, 240, 24, COL_TEXT_MUTED)
            self.text(16, 192, 29, COL_TEXT_MUTED)
            self.text(16, 200, 30, COL_TEXT_MUTED)
        elif self.tab == 1:
            self.text(8, 40, 9, COL_TEXT_BASIC)
            self.text(8, 70, 10, COL_TEXT_BASIC)
            chord_name = self.generator["chords"][self.parm["chord"]]["description"]
            self.text(80, 70, chord_name, COL_TEXT_MUTED)
            self.text(8, 100, 11, COL_TEXT_BASIC)
            self.text(8, 130, 12, COL_TEXT_BASIC)
            self.text(8, 160, 13, COL_TEXT_BASIC)
        elif self.tab == 2:
            self.text(8, 40, 16, COL_TEXT_BASIC)
            melo_tone_name = list_tones[self.parm["melo_tone"]][1]
            self.text(88, 40, melo_tone_name, COL_TEXT_MUTED)
            self.text(8, 70, 17, COL_TEXT_BASIC)
            if self.with_submelody:
                sub_tone_name = list_tones[self.parm["sub_tone"]][1]
            else:
                sub_tone_name = "-"
            self.text(88, 70, sub_tone_name, COL_TEXT_MUTED)
            self.text(8, 100, 18, COL_TEXT_BASIC)
            self.text(8, 130, 19, COL_TEXT_BASIC)
            self.text(8, 160, 20, COL_TEXT_BASIC)
        # タブ、ボタン、モーダル
        for tab in self.tabs:
            tab.draw(self)
        for button in self.buttons:
            button.draw(self)
        for icon in self.icons:
            icon.draw(self)
        if self.show_export:
            h = 12 * 5 + 18
            y = 72
            px.rect(20, y + 4, 224, h, COL_SHADOW)
            px.rect(16, y, 224, h, COL_BTN_SELECTED)
            px.rectb(16, y, 224, h, COL_BTN_BASIC)
            if self.failed_export_midi:
                list_mes = (22, 25, 26, 27, 28)
            else:
                list_mes = (22, 23, 24, 27, 28)
            for i in range(5):
                self.text(20, y + 4 + 12 * i, list_mes[i], COL_TEXT_BASIC)
        # 鍵盤
        sx = 8
        sy = 234
        px.rect(sx, sy, 5 * 42 - 1, 16, 7)
        for x in range(5 * 7 - 1):
            px.line(sx + 5 + x * 6, sy, sx + 5 + x * 6, sy + 15, 0)
        for o in range(5):
            px.rect(sx + 3 + o * 42, sy, 5, 9, 0)
            px.rect(sx + 9 + o * 42, sy, 5, 9, 0)
            px.rect(sx + 21 + o * 42, sy, 5, 9, 0)
            px.rect(sx + 27 + o * 42, sy, 5, 9, 0)
            px.rect(sx + 33 + o * 42, sy, 5, 9, 0)
        # 音域バー
        mln = self.parm["melo_lowest_note"]
        bhn = self.parm["base_highest_note"]
        (x1, _) = self.get_piano_xy(mln)
        (x2, _) = self.get_piano_xy(mln + 16)
        px.rect(x1, 231, x2 - x1 + 3, 2, 11)
        if self.with_submelody:
            (x1, _) = self.get_piano_xy(bhn - 20)
            (x2, _) = self.get_piano_xy(mln + 13)
            px.rect(x1, 228, x2 - x1 + 3, 2, 14)
        (x1, _) = self.get_piano_xy(bhn - 23)
        (x2, _) = self.get_piano_xy(bhn)
        px.rect(x1, 231, x2 - x1 + 3, 2, 10)
        # 再生インジケータ
        if px.play_pos(0):
            pos = px.play_pos(0)[1]
            ticks = self.parm["speed"] / 16
            loc = int(pos // ticks)
            bars = loc // 16 + 1
            beats = (loc // 4) % 4 + 1
        else:
            return
        px.text(8, 220, f"bars: {bars}/{BARS_NUMBERS}", COL_TEXT_BASIC)
        px.text(56, 220, f"beats: {beats}/{4}", COL_TEXT_BASIC)
        item = self.items[loc]
        # 演奏情報
        self.draw_playkey(0, item[6], 11)
        self.draw_playkey(1, item[10], 10)
        if self.with_submelody:
            self.draw_playkey(2, item[14], 14)
        for i, elm in enumerate(self.patterns):
            y = i // 3
            x = i % 3
            c = COL_TEXT_BASIC if elm["key"] in (item[14], item[18]) else COL_TEXT_MUTED
            px.text(220 + x * 10, 235 + y * 8, elm["abbr"], c)

    def draw_playkey(self, key, input, c):
        value = input
        if value is None:
            value = self.saved_playkey[key]
        else:
            self.saved_playkey[key] = value
        if value < 0:
            return
        (x, y) = self.get_piano_xy(value)
        px.rect(x, y, 3, 4, c)

    def get_piano_xy(self, value):
        note12 = value % 12
        oct = value // 12
        x = 8 + (1, 4, 7, 10, 13, 19, 22, 25, 28, 31, 34, 37)[note12] + oct * 42
        y = 234 + (2 if note12 in [1, 3, 6, 8, 10] else 10)
        return x, y

    def play(self):
        for ch, sound in enumerate(self.music):
            px.sounds[ch].set(*sound)
            px.play(ch, ch, loop=self.loop)

    def set_preset(self, value):
        preset = self.generator["preset"][value]
        for key in preset:
            self.parm[key] = preset[key]
        self.generate_music()

    def text(self, x, y, value, c):
        if type(value) is int:
            self.bdf.text(x, y, self.get_text(value)[0], c)
        else:
            self.bdf.text(x, y, value, c)

    def get_text(self, value):
        list_text = [
            ("きほん", "Basic"),
            ("コードとリズム", "Chord & Rhythm"),
            ("メロディ", "Melody"),
            ("プリセット", "Preset"),
            (
                "「コードとリズム」「メロディ」の　オススメせっていを",
                "The recommended settings for 'Chord and Rhyth' and",
            ),
            (
                "とうろくしてあります。　はじめてのかたは",
                "'Melody' are registered. If you are a first time user,",
            ),
            (
                "プリセットをもとに　きょくをつくってみましょう。",
                "create a song based on the presets.",
            ),
            ("トランスポーズ", "Transpose"),
            ("へんせい", "Instrumentation"),
            ("テンポ", "Tempo"),
            ("コードしんこう", "Chord Progression"),
            ("ベース　パターン", "Bass Patterns"),
            ("ベース　クオンタイズ", "Base Quantize"),
            ("ドラム　パターン", "Drums Patterns"),
            (
                "「No drums」をせんたくすると　ドラムパートのかわりに",
                "When 'No drums' is selected, ",
            ),
            (
                "メロディにリバーブがかかります。",
                "reverb is applied to the melody instead of the drum part.",
            ),
            ("ねいろ（メイン）", "Tone (1st channel)"),
            ("ねいろ（サブ）", "Tone (2nd channel)"),
            ("おとのたかさ（さいていおん）", "Sound Height (lowest note)"),
            ("おんぷのかず", "Number of notes"),
            ("１６ぶおんぷをつかう？", "Use 16th notes?"),
            ("", ""),
            (
                "【ローカルでうごかしているばあい】",
                "[When running in a local environment]",
            ),
            (
                "　exportフォルダに music.json と music.mid を",
                "  'music.json' and 'music.mid' in the export folder.",
            ),
            ("　ほぞんしました。", ""),
            (
                "　exportフォルダに music.jsonをほぞんしました。",
                "  'music.json' in the export folder.",
            ),
            ("", ""),
            ("【ブラウザでうごかしているばあい】", "[When running in a browser]"),
            (
                "　music.json がダウンロードされます。",
                " 'music.json' will be downloaded.",
            ),
            (
                "フルへんせいのばあいは４チャンネル、",
                "Use 4 channels for full instrumentation,",
            ),
            (
                "それいがいは３チャンネルをつかいます。",
                "3 channels for everything else.",
            ),
        ]
        lang = self.parm["language"]
        text = list_text[value][lang]
        width = 4 if lang == 0 else 2
        return text, len(text) * width

    def generate_music(self, make_melody=True):
        px.stop()
        parm = self.parm
        base = self.generator["base"][parm["base"]]
        drums = self.generator["drums"][parm["drums"]]
        # コードリスト準備
        self.set_chord_lists()
        # バッキング生成
        items = []
        self.base_notes = []
        self.cur_chord_idx = -1
        for loc in range(self.total_len):
            items.append([None for _ in range(19)])
            (chord_idx, _) = self.get_chord(loc)
            if chord_idx > self.cur_chord_idx:
                chord_list = self.chord_lists[chord_idx]
                self.cur_chord_idx = chord_idx
                self.cur_chord_loc = loc
            item = items[loc]
            tick = loc % 16  # 拍(0-15)
            if loc == 0:  # 最初の行（セットアップ）
                item[0] = parm["speed"]  # テンポ
                item[1] = 48  # 4/4拍子
                item[2] = 3  # 16分音符
                item[3] = list_tones[parm["melo_tone"]][0]  # メロディ音色
                item[4] = 6  # メロディ音量
                item[5] = 14  # メロディ音長
                item[7] = 7  # ベース音色
                item[8] = 7  # ベース音量
                item[9] = parm["base_quantize"]  # ベース音長
                if self.with_submelody:
                    item[11] = list_tones[parm["sub_tone"]][0]
                    item[12] = 4
                    item[13] = 15
                    if self.with_drum:
                        item[15] = 15
                        item[16] = 5
                        item[17] = 15
                elif self.with_drum:
                    item[11] = 15
                    item[12] = 5
                    item[13] = 15
                else:  # リバーブ
                    item[11] = item[3]
                    item[12] = 2
                    item[13] = item[5]

            # ベース音設定
            if not chord_list["repeat"] is None:
                repeat_loc = self.chord_lists[chord_list["repeat"]]["loc"]
                target_loc = repeat_loc + loc - self.cur_chord_loc
                item[10] = items[target_loc][10]
            else:
                pattern = "basic" if loc // 16 < 7 else "final"
                base_str = base[pattern][tick]
                if base_str == ".":
                    base_note = None
                elif base_str == "0":
                    base_note = -1
                else:
                    highest = parm["base_highest_note"]
                    pattern = "basic" if loc // 16 < 7 else "final"
                    base_root = 12 + parm["transpose"] + chord_list["base"]
                    while base_root + 24 > highest:
                        base_root -= 12
                    notes = chord_list["notes_origin"]
                    adjust_list = [0, -1, 1, -2, 2, -3, 3]
                    adjust_idx = 0
                    base_add = {"1": 7, "2": 12, "3": 19, "4": 24}[base_str]
                    while notes:
                        adjust = adjust_list[adjust_idx]
                        base_note = base_root + base_add + adjust
                        tmp = (base_note + parm["transpose"]) % 12
                        # print(notes, tmp, notes[tmp])
                        if notes[(base_note + parm["transpose"]) % 12] in [1, 2, 3]:
                            break
                        adjust_idx += 1
                item[10] = base_note
            self.base_notes.append(base_note)
            # ドラム音設定
            if self.with_drum:
                pattern = "basic" if (loc // 16) % 4 < 3 else "final"
                idx = 18 if self.with_submelody else 14
                drum_str = drums[pattern][tick]
                if drum_str == "0":
                    item[idx] = None
                else:
                    item[idx] = ":" + drum_str
        # メロディー生成
        failure_cnt = 0
        while make_melody:
            self.generate_melody()
            if self.check_melody():
                break
            failure_cnt += 1
            self.set_chord_lists()
            # print("--------失敗---------")
        # print("失敗回数", failure_cnt)
        # メロディ・サブとリバーブの音符を設定
        for loc in range(self.total_len):
            item = items[loc]
            item[6] = self.melody_notes[loc]
            if self.with_submelody:
                item[14] = self.submelody_notes[loc]
            elif not self.with_drum:  # リバーブ
                item[14] = self.melody_notes[
                    (loc + self.total_len - 1) % self.total_len
                ]
        # 完了処理
        self.music = sounds.compile(items, self.tones, self.patterns)
        self.items = items

    # self.chord_listsを生成
    def set_chord_lists(self):
        chord = self.generator["chords"][self.parm["chord"]]
        self.chord_lists = []
        for progression in chord["progression"]:
            chord_list = {
                "loc": progression["loc"],
                "base": 0,
                "no_root": False,
                "notes": [],
                "notes_origin": [],
                "repeat": progression["repeat"] if "repeat" in progression else None,
            }
            if "repeat" in progression:
                chord_list["base"] = self.chord_lists[progression["repeat"]]["base"]
            if "notes" in progression:
                notes = [int(s) for s in progression["notes"]]
                chord_list["notes_origin"] = notes
                note_chord_cnt = 0
                # ベース音設定
                for idx in range(12):
                    if notes[idx] == 2:
                        chord_list["base"] = idx
                    if notes[idx] in [1, 2, 3]:
                        note_chord_cnt += 1
                chord_list["no_root"] = note_chord_cnt > 3
                # レンジを決める
                if self.with_submelody:
                    chord_list["notes"] = self.make_chord_notes(notes, SUBMELODY_DIFF)
                else:
                    chord_list["notes"] = self.make_chord_notes(notes)
            self.chord_lists.append(chord_list)

    # コードリストの音域設定
    def make_chord_notes(self, notes, tone_up=0):
        parm = self.parm
        note_highest = None
        idx = 0
        results = []
        while True:
            note_type = int(notes[idx % 12])
            note = 12 + idx + parm["transpose"]
            if note >= parm["melo_lowest_note"] + tone_up:
                if note_type in [1, 2, 3, 9]:
                    results.append((note, note_type))
                    if note_highest is None:
                        note_highest = note + 15
            if note_highest and note >= note_highest:
                break
            idx += 1
        return results

    # メロディ生成
    def generate_melody(self):
        self.melody_notes = [-2 for _ in range(self.total_len)]
        self.submelody_notes = [-2 for _ in range(self.total_len)]
        # メインメロディ
        # print("=== MAIN START ===")
        rhythm_main_list = []
        for _ in range(5):
            rhythm_main_list.append(self.get_rhythm_set())
        rhythm_main_list.sort(key=len)
        rhythm_main = rhythm_main_list[self.parm["melo_density"]]
        for loc in range(self.total_len):
            # すでに埋まっていたらスキップ
            if self.melody_notes[loc] != -2:
                continue
            # 1セットの音を追加
            notesets = self.get_next_notes(rhythm_main, loc)
            if notesets is None:  # repeat
                repeat_loc = self.chord_lists[self.chord_list["repeat"]]["loc"]
                target_loc = repeat_loc + loc - self.cur_chord_loc
                repeat_note = self.melody_notes[target_loc]
                self.put_melody(loc, repeat_note, 1)
                repeat_subnote = self.submelody_notes[target_loc]
                self.submelody_notes[loc] = repeat_subnote
            else:
                notesets_len = 0
                for noteset in notesets:
                    self.put_melody(noteset[0], noteset[1], noteset[2])
                    notesets_len += noteset[2]
                self.put_submelody(loc, -2, notesets_len)
        # サブメロディ
        # print("=== SUB START ===")
        rhythm_sub = self.get_rhythm_set(True)
        prev_note_loc = -1
        for loc in range(self.total_len):
            note = self.submelody_notes[loc]
            if not note is None and note >= 0:
                prev_note_loc = loc
                self.prev_note = note
            elif loc - prev_note_loc >= 4 and loc % 4 == 0:
                notesets = self.get_next_notes(rhythm_sub, loc, True)
                if not notesets is None:
                    for noteset in notesets:
                        self.put_submelody(noteset[0], noteset[1], noteset[2])
                    prev_note_loc = loc

    # メロディのリズムを取得
    def get_rhythm_set(self, is_sub=False):
        self.cur_chord_idx = -1  # 現在のコード（self.chord_listsのインデックス）
        self.cur_chord_loc = -1  # 現在のコードの開始位置
        self.is_repeat = False  # リピートモード
        self.chord_list = []
        self.prev_note = -1  # 直前のメロディー音
        self.first_in_chord = True  # コード切り替え後の最初のノート
        results = []
        used16 = False
        while True:
            for bar in range(BARS_NUMBERS):
                if is_sub:
                    pat_line = SUB_RHYTHM
                else:
                    while True:
                        pat_line = self.melo_rhythm[
                            px.rndi(0, len(self.melo_rhythm) - 1)
                        ]
                        # 16分音符回避設定
                        if self.has_16th_note(pat_line):
                            if not self.parm["melo_use16"]:
                                continue
                            used16 = True
                        # 先頭が持続音のものは避ける（暫定）
                        if not pat_line[0] is None:
                            break
                for idx, pat_one in enumerate(pat_line):
                    loc = bar * 16 + idx
                    if not pat_one is None:
                        results.append((loc, pat_one))
            if is_sub or not self.parm["melo_use16"] or used16:
                break
        for _ in range(2):
            results.append((self.total_len, -1))
        return results

    # 16分音符が含まれるか
    def has_16th_note(self, line):
        prev_str = None
        for i in line:
            if i == 0 and prev_str == 0:
                return True
            prev_str = i
        return False

    def get_next_notes(self, rhythm_set, loc, is_sub=False):
        pat = None
        for pat_idx, rhythm in enumerate(rhythm_set):
            if loc == rhythm[0]:
                pat = rhythm[1]
                break
            elif loc < rhythm[0]:
                break
        note_len = rhythm_set[pat_idx + 1][0] - loc
        # コード切替判定
        change_code = False
        premonitory = False
        (next_chord_idx, next_chord_loc) = self.get_chord(loc)
        if next_chord_idx > self.cur_chord_idx:
            change_code = True
        elif not self.is_repeat and loc + note_len > next_chord_loc:
            (next_chord_idx, next_chord_loc) = self.get_chord(loc + note_len)
            change_code = True
            premonitory = True
            # print(loc, note_len, "先取音発生")
        if change_code:
            self.chord_list = self.chord_lists[next_chord_idx]
            self.cur_chord_idx = next_chord_idx
            self.cur_chord_loc = loc
            self.first_in_chord = True
            self.is_repeat = not self.chord_list["repeat"] is None
        # 小節単位の繰り返し
        if self.is_repeat:
            # print(loc, "repeat")
            return [] if premonitory else None
        if pat == -1:  # 休符
            # print(loc, "休符")
            return [(loc, -1, note_len)]
        # 初期処理
        self.chord_notes = self.chord_list["notes"]
        next_idx = self.get_target_note(is_sub, loc)
        # 連続音を何個置けるか（コード維持＆４分音符以下）
        following = []
        prev_loc = loc
        while True:
            pat_loc = rhythm_set[pat_idx + 1 + len(following)][0]
            no_next = pat_loc >= next_chord_loc or pat_loc - prev_loc > 4
            if not following or not no_next:
                following.append((prev_loc, pat_loc - prev_loc))
            if no_next:
                break
            prev_loc = pat_loc
        loc, note_len = following[0]
        # 直前のメロディーのインデックスを今のコードリストと照合(構成音から外れていたらNone)
        cur_idx = None
        if not premonitory:
            for idx, note in enumerate(self.chord_notes):
                if self.prev_note == note[0]:
                    cur_idx = idx
                    break
        # 初音（直前が休符 or コード構成音から外れた場合は、コード構成音を取得）
        if self.prev_note < 0 or cur_idx is None:
            # print(loc, "初音")
            note = self.chord_notes[next_idx][0]
            return [(loc, note, note_len)]
        # 各種変数準備
        results = []
        diff = abs(next_idx - cur_idx)
        direction = 1 if next_idx > cur_idx else -1
        # 刺繍音/同音
        if diff == 0:
            cnt = len(following) // 2
            if cnt and px.rndi(0, 1) and not is_sub:
                # print(loc, "刺繍音", cnt * 2)
                for i in range(cnt):
                    while next_idx == cur_idx:
                        next_idx = self.get_target_note()
                    direction = 1 if next_idx > cur_idx else -1
                    # print(cur_idx, next_idx, self.chord_notes)
                    note = self.chord_notes[cur_idx + direction][0]
                    prev_note = self.prev_note
                    note_follow = following[i * 2]
                    results.append((note_follow[0], note, note_follow[1]))
                    note_follow = following[i * 2 + 1]
                    results.append((note_follow[0], prev_note, note_follow[1]))
                return results
            else:
                # print(loc, "同音")
                return [(loc, self.prev_note, note_len)]
        # ステップに必要な長さが足りない/跳躍量が大きい/割合で跳躍音採用
        if abs(next_idx - cur_idx) > len(following):
            note = self.chord_notes[next_idx][0]
            # print(loc, "跳躍")
            return [(loc, note, note_len)]
        # ステップ
        # print(loc, "ステップ", abs(next_idx - cur_idx))
        i = 0
        while next_idx != cur_idx:
            cur_idx += direction
            note = self.chord_notes[cur_idx][0]
            note_follow = following[i]
            results.append((note_follow[0], note, note_follow[1]))
            i += 1
        return results

    # メロディ検査（コード中の重要構成音が入っているか）
    def check_melody(self):
        cur_chord_idx = -1
        need_notes_list = []
        for loc in range(self.total_len):
            (next_chord_idx, _) = self.get_chord(loc)
            if next_chord_idx > cur_chord_idx:
                # need_notes_listが残っている＝重要構成音が満たされていない
                if len(need_notes_list) > 0:
                    return False
                cur_chord_idx = next_chord_idx
                notes_list = self.chord_lists[cur_chord_idx]["notes"]
                need_notes_list = []
                for chord in notes_list:
                    note = chord[0] % 12
                    if chord[1] == 1 and not note in need_notes_list:
                        need_notes_list.append(note)
            note = self.melody_notes[loc]
            if not note is None and note >= 0 and note % 12 in need_notes_list:
                need_notes_list.remove(note % 12)
            if self.with_submelody:
                note = self.submelody_notes[loc]
                if not note is None and note >= 0 and note % 12 in need_notes_list:
                    need_notes_list.remove(note % 12)
        return True

    # コードリスト取得（locがchords_listsの何番目のコードか、次のコードの開始位置を返す）
    def get_chord(self, loc):
        chord_lists_cnt = len(self.chord_lists)
        next_chord_loc = 16 * BARS_NUMBERS
        for rev_idx in range(chord_lists_cnt):
            idx = chord_lists_cnt - rev_idx - 1
            if loc >= self.chord_lists[idx]["loc"]:
                break
            else:
                next_chord_loc = self.chord_lists[idx]["loc"]
        return idx, next_chord_loc

    # 跳躍音の跳躍先を決定
    def get_target_note(self, is_sub=False, loc=None):
        no_root = self.first_in_chord or self.chord_list["no_root"]
        allowed_types = [1, 3] if no_root else [1, 2, 3]
        notes = self.get_subnotes(loc) if is_sub else self.chord_list["notes"]
        # 跳躍先候補が1オクターブ超のみの場合、最低音を選択
        hightest_note = 0
        hightest_idx = 0
        for idx, noteset in enumerate(notes):
            if noteset[0] > hightest_note and noteset[1] in allowed_types:
                hightest_note = noteset[0]
                hightest_idx = idx
        if self.prev_note - hightest_note > 12:
            return hightest_idx
        while True:
            idx = px.rndi(0, len(notes) - 1)
            if not notes[idx][1] in allowed_types:
                continue
            note = notes[idx][0]
            if self.prev_note >= 0:
                diff = abs(self.prev_note - note)
                if diff > 12:
                    continue
                factor = diff if diff != 12 else diff - 6
                # 近い音ほど出やすい（オクターブ差は補正、サブはそうではない）
                if px.rndi(0, 15) < factor and not is_sub:
                    continue
            return idx

    # メロディのトーンを配置
    def put_melody(self, loc, note, note_len=1):
        for idx in range(note_len):
            self.melody_notes[loc + idx] = note if idx == 0 else None
        if note is not None:
            self.prev_note = note
            self.first_in_chord = False

    # サブメロディのトーンを配置
    def put_submelody(self, loc, note, note_len=1):
        master_note = None
        subnote = note
        master_loc = loc
        while master_loc >= 0:
            master_note = self.melody_notes[master_loc]
            if not master_note is None and master_note >= 0:
                prev_note = master_note if note == -2 else note
                subnote = self.search_downer_note(prev_note, master_note, master_loc)
                break
            master_loc -= 1
        prev_subnote = None
        for idx in range(note_len):
            if (
                not self.melody_notes[loc + idx] is None
                and self.melody_notes[loc + idx] >= 0
            ):
                master_note = self.melody_notes[loc + idx]
            duplicate = (
                not master_note is None
                and not subnote is None
                and (abs(subnote > master_note) < 3)
            )
            if duplicate:
                subnote = self.search_downer_note(subnote, master_note, loc + idx)
            self.submelody_notes[loc + idx] = (
                subnote if subnote != prev_subnote else None
            )
            prev_subnote = subnote

    # メロの下ハモを探す
    def search_downer_note(self, prev_note, master_note, loc):
        if self.with_submelody and master_note >= 0:
            notes = self.get_subnotes(loc)
            if not prev_note is None and abs(prev_note - master_note) >= 3:
                return prev_note
            cur_note = master_note - 3
            while cur_note >= self.parm["melo_lowest_note"]:
                for n in notes:
                    if n[0] == cur_note and n[1] in [1, 2, 3]:
                        return cur_note
                cur_note -= 1
        return -1

    # サブパートの許容音域を取得
    def get_subnotes(self, start_loc):
        master_note = None
        base_note = None
        loc = start_loc
        while master_note is None or base_note is None:
            if master_note is None and self.melody_notes[loc] != -1:
                master_note = self.melody_notes[loc]
            if base_note is None and self.base_notes[loc] != -1:
                base_note = self.base_notes[loc]
            loc = (loc + self.total_len - 1) % self.total_len
        notes = self.chord_list["notes_origin"].copy()
        results = []
        has_important_tone = False
        idx = 0
        while notes:
            note_type = notes[idx % 12]
            if note_type in [1, 2, 3, 9]:
                note = 12 + idx + self.parm["transpose"]
                # ベース+3〜メイン-3までを許可する
                if note > master_note - 3 and has_important_tone:
                    break
                if note >= base_note + 3:
                    results.append((note, note_type))
                    if note_type in [1, 3]:
                        has_important_tone = True
            idx += 1
        self.chord_notes = results
        return results


App()
