"""Money Studio - desktop app (Tkinter) for the Broke Ben channel.

Tab 1  Xuất video              : chọn kịch bản, xem trước từng cảnh (kèm lời Anh + Việt), chọn phụ đề Anh/Việt, xuất video
Tab 2  Viết kịch bản AI        : copy prompt để dán vào Claude chat (miễn phí) hoặc viết / dịch bằng Claude API
Tab 3  Giọng đọc & cài đặt     : kết nối Kokoro có sẵn trên máy, nghe thử giọng, âm lượng, bộ mã hóa
"""
import glob
import json
import multiprocessing
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import tkinter as tk                              # noqa: E402
from tkinter import ttk, filedialog, messagebox   # noqa: E402

CFG_PATH = os.path.join(ROOT, 'config.json')
SCRIPTS = os.path.join(ROOT, 'scripts')
OUTPUT = os.path.join(ROOT, 'output')
LOGS = os.path.join(ROOT, 'logs')

BG, PANEL, FIELD = '#F4EFE4', '#FFFDF7', '#FFFFFF'
TEXT, MUTED = '#1D212D', '#6E6A62'
GREEN, GREEN_D, RED, GOLD = '#2E8B57', '#23714A', '#D64545', '#FFC43D'

PILLARS = ["Why You're Broke (thói quen làm cạn tiền)", 'The Money Traps (chiêu trò thẻ tín dụng, BNPL, đại lý xe)',
           'Money Explained (giải thích khái niệm)', 'The Math Nobody Shows You (so sánh A vs B)',
           "Ben's Stories (truyện có nhân vật)", 'Economy made simple (kinh tế dễ hiểu)']
SUBS = [('en', 'Tiếng Anh (bản đăng YouTube)'), ('vi', 'Tiếng Việt (để bạn xem duyệt)'), ('none', 'Không phụ đề')]


def load_cfg():
    try:
        with open(CFG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_cfg(cfg):
    with open(CFG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def open_path(p):
    try:
        if sys.platform == 'win32':
            os.startfile(p)  # noqa
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', p])
        else:
            subprocess.Popen(['xdg-open', p])
    except Exception as e:  # noqa
        messagebox.showerror('Không mở được', str(e))


def play(path):
    if sys.platform == 'win32':
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    else:
        open_path(path)


def write_log(text):
    os.makedirs(LOGS, exist_ok=True)
    with open(os.path.join(LOGS, 'app.log'), 'a', encoding='utf-8') as f:
        f.write(text + '\n')


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = load_cfg()
        self.q = queue.Queue()
        self.job = None
        self.preview_img = None
        self.ai_cancel = False
        self.last_out = None
        for d in (SCRIPTS, OUTPUT, LOGS):
            os.makedirs(d, exist_ok=True)
        root.title('Money Studio - Broke Ben')
        root.geometry('1440x900')
        root.minsize(1180, 720)
        if sys.platform == 'win32':
            try:
                root.state('zoomed')
            except Exception:
                pass
        root.configure(bg=BG)
        ico = os.path.join(ROOT, 'assets', 'icon.ico')
        if sys.platform == 'win32' and os.path.exists(ico):
            try:
                root.iconbitmap(ico)
            except Exception:
                pass
        self._style()
        self._build()
        self.refresh_scripts()
        self.root.after(120, self._poll)

    # ------------------------------------------------------------ look
    def _style(self):
        st = ttk.Style()
        try:
            st.theme_use('clam')
        except Exception:
            pass
        base = ('Segoe UI', 10)
        st.configure('.', font=base, background=BG, foreground=TEXT, fieldbackground=FIELD, bordercolor='#D8CFBD',
                     lightcolor=PANEL, darkcolor=PANEL, troughcolor='#E9E1D0', selectbackground=GREEN,
                     selectforeground='white')
        st.configure('TFrame', background=BG)
        st.configure('Panel.TFrame', background=PANEL)
        st.configure('TLabel', background=BG, foreground=TEXT)
        st.configure('Panel.TLabel', background=PANEL)
        st.configure('Muted.TLabel', background=PANEL, foreground=MUTED)
        st.configure('H.TLabel', font=('Segoe UI Semibold', 12), background=PANEL)
        st.configure('TLabelframe', background=PANEL, bordercolor='#D8CFBD')
        st.configure('TLabelframe.Label', background=PANEL, foreground=TEXT, font=('Segoe UI Semibold', 10))
        st.configure('TRadiobutton', background=PANEL)
        st.configure('TCheckbutton', background=PANEL)
        st.configure('TNotebook', background=BG, borderwidth=0)
        st.configure('TNotebook.Tab', padding=(16, 7), font=('Segoe UI Semibold', 10))
        st.map('TNotebook.Tab', background=[('selected', PANEL)], foreground=[('selected', GREEN_D)])
        st.configure('TButton', padding=(10, 5))
        st.configure('Go.TButton', font=('Segoe UI Semibold', 12), padding=(14, 9), background=GREEN,
                     foreground='white')
        st.map('Go.TButton', background=[('active', GREEN_D), ('disabled', '#A9C9B6')])
        st.configure('green.Horizontal.TProgressbar', background=GREEN)

    def _text(self, parent, h=8, mono=False):
        t = tk.Text(parent, height=h, wrap='word', bg=FIELD, fg=TEXT, insertbackground=TEXT, relief='flat',
                    highlightthickness=1, highlightbackground='#D8CFBD',
                    font=('Consolas', 10) if mono else ('Segoe UI', 10))
        return t

    def _build(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill='both', expand=True, padx=8, pady=8)
        t1, t2, t3 = ttk.Frame(nb), ttk.Frame(nb), ttk.Frame(nb)
        nb.add(t1, text='1. Xuất video')
        nb.add(t2, text='2. Viết kịch bản AI')
        nb.add(t3, text='3. Giọng đọc & cài đặt')
        self._tab_export(t1)
        self._tab_ai(t2)
        self._tab_settings(t3)

    # ------------------------------------------------------------ tab 1
    def _tab_export(self, tab):
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)
        left = ttk.Frame(tab, style='Panel.TFrame', padding=10)
        left.grid(row=0, column=0, sticky='ns', padx=(0, 8))
        ttk.Label(left, text='Kịch bản', style='H.TLabel').pack(anchor='w')
        self.lst = tk.Listbox(left, width=34, height=24, bg=FIELD, fg=TEXT, relief='flat', highlightthickness=1,
                              highlightbackground='#D8CFBD', selectbackground=GREEN, exportselection=False,
                              font=('Segoe UI', 10))
        self.lst.pack(fill='y', expand=True, pady=6)
        self.lst.bind('<<ListboxSelect>>', lambda e: self.on_select())
        ttk.Button(left, text='Thêm file kịch bản...', command=self.add_script).pack(fill='x', pady=2)
        ttk.Button(left, text='Mở thư mục scripts', command=lambda: open_path(SCRIPTS)).pack(fill='x', pady=2)
        ttk.Button(left, text='Làm mới danh sách', command=self.refresh_scripts).pack(fill='x', pady=2)

        mid = ttk.Frame(tab, style='Panel.TFrame', padding=10)
        mid.grid(row=0, column=1, sticky='nsew')
        self.mid = mid
        mid.columnconfigure(0, weight=1)
        mid.rowconfigure(3, weight=1)
        self.preview = tk.Label(mid, bg='#E9E1D0')
        self.preview.grid(row=0, column=0, sticky='n')
        sl = ttk.Frame(mid, style='Panel.TFrame')
        sl.grid(row=1, column=0, sticky='ew', pady=(8, 2))
        sl.columnconfigure(1, weight=1)
        ttk.Label(sl, text='Cảnh:', style='Panel.TLabel').grid(row=0, column=0)
        self.scene_var = tk.IntVar(value=1)
        self.scene_scale = ttk.Scale(sl, from_=1, to=1, orient='horizontal',
                                     command=lambda v: self._scene_moved())
        self.scene_scale.grid(row=0, column=1, sticky='ew', padx=8)
        self.scene_lbl = ttk.Label(sl, text='', style='Muted.TLabel', width=46)
        self.scene_lbl.grid(row=0, column=2)
        ttk.Label(mid, text='Lời đọc của cảnh (Anh / Việt)', style='H.TLabel').grid(row=2, column=0, sticky='w',
                                                                                 pady=(8, 2))
        self.scene_txt = self._text(mid, 7)
        self.scene_txt.grid(row=3, column=0, sticky='nsew')

        right = ttk.Frame(tab, style='Panel.TFrame', padding=10)
        right.grid(row=0, column=2, sticky='ns', padx=(8, 0))
        box = ttk.Labelframe(right, text='Phụ đề trên video', padding=8)
        box.pack(fill='x')
        self.subs_var = tk.StringVar(value=self.cfg.get('subtitles', 'en'))
        for val, lab in SUBS:
            ttk.Radiobutton(box, text=lab, value=val, variable=self.subs_var,
                            command=self._subs_changed).pack(anchor='w', pady=1)
        ttk.Label(box, text='Luôn xuất kèm 2 file subtitles_en.srt và\nsubtitles_vi.srt để tải lên YouTube.',
                  style='Muted.TLabel').pack(anchor='w', pady=(4, 0))
        opt = ttk.Labelframe(right, text='Tùy chọn xuất', padding=8)
        opt.pack(fill='x', pady=8)
        self.shorts_var = tk.BooleanVar(value=bool(self.cfg.get('make_shorts', True)))
        self.test_var = tk.BooleanVar(value=False)
        self.prev_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text='Xuất thêm Shorts dọc (dưới 60 giây)', variable=self.shorts_var).pack(anchor='w')
        ttk.Checkbutton(opt, text='Thử nhanh không giọng (không cần Kokoro)', variable=self.test_var).pack(anchor='w')
        ttk.Checkbutton(opt, text='Chỉ xuất 40 giây đầu (xem thử)', variable=self.prev_var).pack(anchor='w')
        ttk.Button(right, text='Kiểm tra kịch bản', command=self.check_script).pack(fill='x', pady=2)
        self.go_btn = ttk.Button(right, text='XUẤT VIDEO', style='Go.TButton', command=self.start)
        self.go_btn.pack(fill='x', pady=(10, 4))
        ttk.Button(right, text='Hủy', command=self.cancel).pack(fill='x', pady=2)
        ttk.Button(right, text='Mở thư mục kết quả', command=self.open_output).pack(fill='x', pady=2)
        self.prog = ttk.Progressbar(right, mode='determinate', maximum=1000, length=260,
                                    style='green.Horizontal.TProgressbar')
        self.prog.pack(fill='x', pady=(14, 4))
        self.status = ttk.Label(right, text='Sẵn sàng', style='Muted.TLabel', wraplength=260)
        self.status.pack(anchor='w')
        ttk.Label(right, text='Nhật ký', style='H.TLabel').pack(anchor='w', pady=(12, 2))
        self.logbox = self._text(right, 14)
        self.logbox.configure(width=36)
        self.logbox.pack(fill='both', expand=True)

    def log(self, text):
        write_log(text)
        self.q.put(('log', text))

    def refresh_scripts(self):
        self.scripts = sorted(glob.glob(os.path.join(SCRIPTS, '*.json')))
        self.lst.delete(0, 'end')
        for p in self.scripts:
            self.lst.insert('end', os.path.basename(p))
        if self.scripts:
            self.lst.selection_set(0)
            self.on_select()

    def add_script(self):
        ps = filedialog.askopenfilenames(title='Chọn kịch bản JSON', filetypes=[('JSON', '*.json')])
        for p in ps:
            shutil.copy(p, SCRIPTS)
        self.refresh_scripts()

    def current(self):
        sel = self.lst.curselection()
        return self.scripts[sel[0]] if sel and sel[0] < len(self.scripts) else None

    def on_select(self):
        p = self.current()
        if not p:
            return
        try:
            import script_io
            s = script_io.load(p)
            n = max(1, len(s['scenes']))
            self.scene_scale.configure(to=n)
            self.scene_scale.set(1)
            self.status.configure(text=f'{s["title"]} | {n} cảnh')
            self._scene_moved(force=True)
        except Exception as e:
            self.status.configure(text='Lỗi đọc kịch bản: %s' % e)

    def _subs_changed(self):
        self.cfg['subtitles'] = self.subs_var.get()
        save_cfg(self.cfg)
        self._scene_moved(force=True)

    def _scene_moved(self, force=False):
        idx = int(round(float(self.scene_scale.get()))) - 1
        if not force and getattr(self, '_last_idx', None) == idx:
            return
        self._last_idx = idx
        p = self.current()
        if not p:
            return
        subs = self.subs_var.get()
        self.root.update_idletasks()
        width = max(480, min(960, self.mid.winfo_width() - 24)) // 16 * 16

        def work():
            try:
                import render
                img, n, total, sc = render.still(self.cfg, p, idx, at=0.8, width=width, subs=subs)
                self.q.put(('still', (idx, img, n, total, sc)))
            except Exception:
                self.q.put(('log', 'Xem trước lỗi:\n' + traceback.format_exc()[-800:]))
        threading.Thread(target=work, daemon=True).start()

    def check_script(self):
        p = self.current()
        if not p:
            return
        import script_io
        try:
            s = script_io.load(p)
        except Exception as e:
            messagebox.showerror('Kịch bản lỗi', f'Không đọc được JSON:\n{e}')
            return
        msgs = script_io.check(s)
        if not msgs:
            messagebox.showinfo('Kiểm tra kịch bản', 'Không thấy vấn đề nào. Sẵn sàng xuất video!')
        else:
            messagebox.showinfo('Kiểm tra kịch bản', '\n'.join(f'[{lvl}] {m}' for lvl, m in msgs[:25]))

    def start(self):
        p = self.current()
        if not p:
            messagebox.showwarning('Chưa chọn', 'Chọn một kịch bản ở cột bên trái.')
            return
        if self.job:
            return
        import render
        self.cfg['make_shorts'] = bool(self.shorts_var.get())
        self.cfg['subtitles'] = self.subs_var.get()
        save_cfg(self.cfg)
        self.job = render.Job(self.cfg, p, subs=self.subs_var.get(), test_voice=self.test_var.get(),
                              preview_secs=40 if self.prev_var.get() else None, shorts=self.shorts_var.get(),
                              report=lambda k, f, t: self.q.put(('prog', (k, f, t))), log=self.log)
        self.go_btn.state(['disabled'])
        self.prog['value'] = 0
        self.log(f'--- Xuất: {os.path.basename(p)} | phụ đề: {dict(SUBS)[self.subs_var.get()]}')

        def work():
            try:
                out = self.job.run()
                self.q.put(('done', out))
            except Exception as e:
                write_log(traceback.format_exc())
                self.q.put(('error', str(e)))
        threading.Thread(target=work, daemon=True).start()

    def cancel(self):
        if self.job:
            self.job.cancel = True
            self.status.configure(text='Đang hủy...')

    def open_output(self):
        open_path(self.last_out or OUTPUT)

    # ------------------------------------------------------------ tab 2
    def _tab_ai(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        top = ttk.Frame(tab, style='Panel.TFrame', padding=10)
        top.grid(row=0, column=0, sticky='ew')
        for c in (1, 3):
            top.columnconfigure(c, weight=1)
        ttk.Label(top, text='Chủ đề (Anh hoặc Việt):', style='Panel.TLabel').grid(row=0, column=0, sticky='w')
        self.topic = ttk.Entry(top)
        self.topic.grid(row=0, column=1, columnspan=3, sticky='ew', padx=6, pady=3)
        ttk.Label(top, text='Nhóm chủ đề:', style='Panel.TLabel').grid(row=1, column=0, sticky='w')
        self.pillar = ttk.Combobox(top, values=PILLARS, state='readonly')
        self.pillar.current(0)
        self.pillar.grid(row=1, column=1, sticky='ew', padx=6, pady=3)
        ttk.Label(top, text='Số phút:', style='Panel.TLabel').grid(row=1, column=2, sticky='e')
        self.minutes = ttk.Spinbox(top, from_=1, to=20, width=6)
        self.minutes.set(10)
        self.minutes.grid(row=1, column=3, sticky='w', padx=6)
        ttk.Label(top, text='Linh vật:', style='Panel.TLabel').grid(row=2, column=0, sticky='w')
        self.mascot = ttk.Combobox(top, values=['ben', 'piggy', 'both'], state='readonly', width=10)
        self.mascot.current(0)
        self.mascot.grid(row=2, column=1, sticky='w', padx=6, pady=3)
        btns = ttk.Frame(top, style='Panel.TFrame')
        btns.grid(row=3, column=0, columnspan=4, sticky='w', pady=(8, 0))
        ttk.Button(btns, text='Copy prompt (dán vào Claude chat - miễn phí)', command=self.copy_prompt).pack(
            side='left', padx=(0, 6))
        ttk.Button(btns, text='VIẾT BẰNG API', command=self.ai_write).pack(side='left', padx=6)
        ttk.Button(btns, text='Dịch phụ đề tiếng Việt còn thiếu (API)', command=self.ai_translate).pack(side='left',
                                                                                                      padx=6)
        ttk.Button(btns, text='Dừng', command=self._ai_stop).pack(side='left', padx=6)

        body = ttk.Frame(tab, style='Panel.TFrame', padding=10)
        body.grid(row=1, column=0, sticky='nsew', pady=(8, 0))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)
        bar = ttk.Frame(body, style='Panel.TFrame')
        bar.grid(row=0, column=0, sticky='ew')
        ttk.Label(bar, text='Kịch bản JSON', style='H.TLabel').pack(side='left')
        ttk.Button(bar, text='Lưu vào scripts', command=self.ai_save).pack(side='right', padx=3)
        ttk.Button(bar, text='Kiểm tra JSON', command=self.ai_check).pack(side='right', padx=3)
        ttk.Button(bar, text='Dán từ clipboard', command=self.ai_paste).pack(side='right', padx=3)
        ttk.Button(bar, text='Mở kịch bản đang chọn', command=self.ai_load_current).pack(side='right', padx=3)
        self.ai_txt = self._text(body, 20, mono=True)
        self.ai_txt.grid(row=1, column=0, sticky='nsew', pady=6)
        self.ai_status = ttk.Label(body, text='Cách miễn phí: bấm "Copy prompt", dán vào Claude chat, copy JSON '
                                              'Claude trả về, bấm "Dán từ clipboard" rồi "Lưu vào scripts".',
                                   style='Muted.TLabel')
        self.ai_status.grid(row=2, column=0, sticky='w')

    def copy_prompt(self):
        import claude_api
        text = claude_api.prompt_doc() + '\n\n---\n\n' + claude_api.user_prompt(
            self.topic.get().strip(), self.pillar.get().split(' (')[0], self.minutes.get(), self.mascot.get())
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.ai_status.configure(text='Đã copy prompt. Dán vào Claude chat, rồi dán JSON trả về vào ô bên trên.')

    def _ai_key(self):
        key = self.cfg.get('anthropic_api_key', '').strip()
        if not key:
            messagebox.showinfo('Cần API key', 'Nhập Anthropic API key ở tab "3. Giọng đọc & cài đặt" trước.\n'
                                              'Hoặc dùng cách miễn phí: "Copy prompt" rồi dán vào Claude chat.')
        return key

    def ai_write(self):
        key = self._ai_key()
        if not key:
            return
        self.ai_cancel = False
        self.ai_txt.delete('1.0', 'end')
        self.ai_status.configure(text='Claude đang viết kịch bản...')
        args = (self.topic.get().strip(), self.pillar.get().split(' (')[0], int(self.minutes.get()), self.mascot.get())

        def work():
            try:
                import claude_api
                claude_api.write_script(key, *args, model=self.cfg.get('claude_model'),
                                        on_text=lambda s: self.q.put(('ai_text', s)),
                                        cancelled=lambda: self.ai_cancel)
                self.q.put(('ai_done', 'Xong. Bấm "Kiểm tra JSON" rồi "Lưu vào scripts".'))
            except Exception as e:
                self.q.put(('ai_done', 'Lỗi: %s' % e))
        threading.Thread(target=work, daemon=True).start()

    def ai_translate(self):
        key = self._ai_key()
        if not key:
            return
        try:
            data = json.loads(self.ai_txt.get('1.0', 'end'))
        except Exception:
            messagebox.showwarning('Chưa có JSON', 'Bấm "Mở kịch bản đang chọn" hoặc dán JSON vào ô trước.')
            return
        self.ai_cancel = False
        self.ai_status.configure(text='Claude đang dịch phụ đề tiếng Việt...')

        def work():
            try:
                import claude_api
                n = claude_api.translate_vi(key, data, model=self.cfg.get('claude_model'),
                                            cancelled=lambda: self.ai_cancel)
                self.q.put(('ai_json', data))
                self.q.put(('ai_done', f'Đã dịch {n} câu. Kiểm tra lại rồi bấm "Lưu vào scripts".'))
            except Exception as e:
                self.q.put(('ai_done', 'Lỗi: %s' % e))
        threading.Thread(target=work, daemon=True).start()

    def _ai_stop(self):
        self.ai_cancel = True

    def ai_paste(self):
        try:
            txt = self.root.clipboard_get()
        except Exception:
            txt = ''
        self.ai_txt.delete('1.0', 'end')
        self.ai_txt.insert('1.0', txt)

    def ai_load_current(self):
        p = self.current()
        if not p:
            return
        with open(p, 'r', encoding='utf-8') as f:
            self.ai_txt.delete('1.0', 'end')
            self.ai_txt.insert('1.0', f.read())
        self._ai_loaded = p

    def _ai_parse(self):
        import claude_api
        return claude_api.extract_json(self.ai_txt.get('1.0', 'end'))

    def ai_check(self):
        import script_io
        try:
            s = script_io.normalise(self._ai_parse())
        except Exception as e:
            messagebox.showerror('JSON lỗi', str(e))
            return
        msgs = script_io.check(s)
        messagebox.showinfo('Kiểm tra', '\n'.join(f'[{lvl}] {m}' for lvl, m in msgs[:25]) or 'JSON hợp lệ, không có vấn đề.')

    def ai_save(self):
        try:
            data = self._ai_parse()
        except Exception as e:
            messagebox.showerror('JSON lỗi', str(e))
            return
        base = re.sub(r'[^a-z0-9]+', '_', data.get('title', 'episode').lower()).strip('_')[:50] or 'episode'
        loaded = getattr(self, '_ai_loaded', None)
        if loaded and os.path.basename(loaded).startswith(base[:10]):
            path = loaded
        else:
            n = len(glob.glob(os.path.join(SCRIPTS, 'ep*.json'))) + 1
            path = os.path.join(SCRIPTS, f'ep{n:02d}_{base}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self.ai_status.configure(text=f'Đã lưu: {os.path.basename(path)}')
        self.refresh_scripts()

    # ------------------------------------------------------------ tab 3
    def _tab_settings(self, tab):
        import tts
        f = ttk.Frame(tab, style='Panel.TFrame', padding=14)
        f.pack(fill='both', expand=True)
        f.columnconfigure(1, weight=1)
        r = 0
        ttk.Label(f, text='Kết nối giọng đọc Kokoro (dùng chung với Horror Studio / Relatable Studio)',
                  style='H.TLabel').grid(row=r, column=0, columnspan=3, sticky='w')
        r += 1
        self.v_py = tk.StringVar(value=self.cfg.get('kokoro_python', ''))
        self.v_hf = tk.StringVar(value=self.cfg.get('hf_home', ''))
        for lab, var, is_file in (('Python của Kokoro:', self.v_py, True), ('Thư mục model (HF_HOME):', self.v_hf, False)):
            ttk.Label(f, text=lab, style='Panel.TLabel').grid(row=r, column=0, sticky='w', pady=3)
            ttk.Entry(f, textvariable=var).grid(row=r, column=1, sticky='ew', padx=6)
            ttk.Button(f, text='Chọn...', command=lambda v=var, fi=is_file: self._browse(v, fi)).grid(row=r, column=2)
            r += 1
        ttk.Button(f, text='Kiểm tra kết nối', command=self.check_voice).grid(row=r, column=1, sticky='w', pady=4)
        r += 1
        self.voice_status = ttk.Label(f, text='', style='Muted.TLabel')
        self.voice_status.grid(row=r, column=0, columnspan=3, sticky='w')
        r += 1
        ttk.Separator(f).grid(row=r, column=0, columnspan=3, sticky='ew', pady=10)
        r += 1
        ttk.Label(f, text='Giọng đọc mặc định', style='H.TLabel').grid(row=r, column=0, sticky='w')
        r += 1
        self.v_voice = ttk.Combobox(f, values=tts.VOICES, width=18)
        self.v_voice.set(self.cfg.get('narrator_voice', 'am_michael'))
        self.v_voice.grid(row=r, column=0, sticky='w', pady=3)
        self.v_speed = tk.DoubleVar(value=float(self.cfg.get('speed', 1.0)))
        ttk.Label(f, text='Tốc độ:', style='Panel.TLabel').grid(row=r, column=1, sticky='w', padx=6)
        ttk.Spinbox(f, from_=0.8, to=1.3, increment=0.05, textvariable=self.v_speed, width=6).grid(row=r, column=1,
                                                                                                   padx=70, sticky='w')
        r += 1
        self.sample = ttk.Entry(f)
        self.sample.insert(0, 'Ben makes three thousand dollars a month. By day ten... thirty-three are left.')
        self.sample.grid(row=r, column=0, columnspan=2, sticky='ew', pady=3)
        ttk.Button(f, text='Nghe thử', command=self.test_voice).grid(row=r, column=2)
        r += 1
        ttk.Separator(f).grid(row=r, column=0, columnspan=3, sticky='ew', pady=10)
        r += 1
        ttk.Label(f, text='Âm thanh & xuất video', style='H.TLabel').grid(row=r, column=0, sticky='w')
        r += 1
        self.v_music = tk.DoubleVar(value=float(self.cfg.get('music_volume', 0.35)))
        self.v_sfx = tk.DoubleVar(value=float(self.cfg.get('sfx_volume', 0.8)))
        for lab, var in (('Nhạc nền:', self.v_music), ('Hiệu ứng:', self.v_sfx)):
            ttk.Label(f, text=lab, style='Panel.TLabel').grid(row=r, column=0, sticky='w')
            ttk.Scale(f, from_=0, to=1, variable=var).grid(row=r, column=1, sticky='ew', padx=6)
            r += 1
        ttk.Label(f, text='Bộ mã hóa video:', style='Panel.TLabel').grid(row=r, column=0, sticky='w')
        self.v_enc = ttk.Combobox(f, values=['auto', 'libx264'], state='readonly', width=12)
        self.v_enc.set(self.cfg.get('encoder', 'auto'))
        self.v_enc.grid(row=r, column=1, sticky='w', padx=6, pady=3)
        r += 1
        ttk.Label(f, text='(auto = dùng card NVIDIA nếu có, nhanh hơn nhiều)', style='Muted.TLabel').grid(
            row=r, column=1, sticky='w', padx=6)
        r += 1
        ttk.Separator(f).grid(row=r, column=0, columnspan=3, sticky='ew', pady=10)
        r += 1
        ttk.Label(f, text='Claude API (không bắt buộc)', style='H.TLabel').grid(row=r, column=0, sticky='w')
        r += 1
        self.v_key = tk.StringVar(value=self.cfg.get('anthropic_api_key', ''))
        self.v_model = tk.StringVar(value=self.cfg.get('claude_model', 'claude-opus-5-5'))
        ttk.Label(f, text='API key:', style='Panel.TLabel').grid(row=r, column=0, sticky='w')
        ttk.Entry(f, textvariable=self.v_key, show='•').grid(row=r, column=1, sticky='ew', padx=6, pady=3)
        r += 1
        ttk.Label(f, text='Model:', style='Panel.TLabel').grid(row=r, column=0, sticky='w')
        ttk.Entry(f, textvariable=self.v_model, width=24).grid(row=r, column=1, sticky='w', padx=6, pady=3)
        r += 1
        ttk.Button(f, text='LƯU CÀI ĐẶT', style='Go.TButton', command=self.save_settings).grid(row=r, column=0,
                                                                                            sticky='w', pady=14)

    def _browse(self, var, is_file):
        p = filedialog.askopenfilename(title='Chọn python.exe') if is_file else \
            filedialog.askdirectory(title='Chọn thư mục')
        if p:
            var.set(p)

    def save_settings(self):
        self.cfg.update({'kokoro_python': self.v_py.get().strip(), 'hf_home': self.v_hf.get().strip(),
                         'narrator_voice': self.v_voice.get().strip() or 'am_michael',
                         'speed': round(float(self.v_speed.get()), 2), 'music_volume': round(self.v_music.get(), 2),
                         'sfx_volume': round(self.v_sfx.get(), 2), 'encoder': self.v_enc.get(),
                         'anthropic_api_key': self.v_key.get().strip(), 'claude_model': self.v_model.get().strip()})
        save_cfg(self.cfg)
        self.voice_status.configure(text='Đã lưu cài đặt.')

    def check_voice(self):
        import tts
        self.save_settings()
        text, ok = tts.Voice(self.cfg, os.path.join(OUTPUT, '_tts_cache')).check()
        self.voice_status.configure(text=text + ('' if ok else '\n→ Sửa đường dẫn rồi bấm Lưu cài đặt.'))

    def test_voice(self):
        self.save_settings()
        text = self.sample.get().strip()
        self.voice_status.configure(text='Đang tạo giọng thử bằng Kokoro (lần đầu có thể mất 20-60 giây)...')

        def work():
            try:
                import numpy as np
                import tts
                v = tts.Voice(self.cfg, os.path.join(OUTPUT, '_tts_cache'), log=self.log)
                segs = [{'text': s, 'voice': self.cfg['narrator_voice'], 'speed': float(self.cfg.get('speed', 1.0))}
                        for s in tts.segments(text)]
                v.synth(segs)
                a = tts.line_audio(segs)
                out = os.path.join(OUTPUT, '_tts_cache', '_sample.wav')
                tts.write_wav(out, np.asarray(a, np.float32))
                self.q.put(('voice_ok', out))
            except Exception as e:
                self.q.put(('voice_err', str(e)))
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------ queue
    def _poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == 'log':
                    self.logbox.insert('end', data + '\n')
                    self.logbox.see('end')
                elif kind == 'still':
                    idx, img, n, total, sc = data
                    if img is not None:
                        from PIL import ImageTk
                        self.preview_img = ImageTk.PhotoImage(img)
                        self.preview.configure(image=self.preview_img, width=img.width, height=img.height)
                    if sc:
                        show = (sc.get('show') or {}).get('type', '-')
                        self.scene_lbl.configure(text=f'Cảnh {idx + 1}/{n} | {sc["purpose"]} | {show} | '
                                                      f'~{sc["duration"]:.1f}s | tổng ~{int(total // 60)}:{int(total % 60):02d}')
                        self.scene_txt.delete('1.0', 'end')
                        for ln in sc['lines']:
                            self.scene_txt.insert('end', 'EN: ' + ln['text'].replace('*', '') + '\n')
                            self.scene_txt.insert('end', 'VI: ' + (ln.get('vi') or '(chưa có bản dịch)').replace('*', '')
                                                  + '\n\n')
                elif kind == 'prog':
                    k, frac, text = data
                    weights = {'voice': (0, 250), 'audio': (250, 280), 'frames': (280, 950), 'extras': (950, 990),
                               'done': (1000, 1000)}
                    a, b = weights.get(k, (0, 1000))
                    self.prog['value'] = a + (b - a) * max(0.0, min(1.0, frac))
                    self.status.configure(text=text)
                elif kind == 'done':
                    self.job = None
                    self.last_out = data
                    self.go_btn.state(['!disabled'])
                    self.prog['value'] = 1000
                    self.log('XONG: ' + data)
                    if messagebox.askyesno('Xong!', 'Đã xuất video.\nMở thư mục kết quả?'):
                        open_path(data)
                elif kind == 'error':
                    self.job = None
                    self.go_btn.state(['!disabled'])
                    self.status.configure(text='Lỗi')
                    self.log('LỖI: ' + data)
                    messagebox.showerror('Lỗi xuất video', data[-1500:])
                elif kind == 'ai_text':
                    self.ai_txt.insert('end', data)
                    self.ai_txt.see('end')
                elif kind == 'ai_json':
                    self.ai_txt.delete('1.0', 'end')
                    self.ai_txt.insert('1.0', json.dumps(data, indent=2, ensure_ascii=False))
                elif kind == 'ai_done':
                    self.ai_status.configure(text=data)
                elif kind == 'voice_ok':
                    self.voice_status.configure(text='Giọng đọc OK. Đang phát thử...')
                    play(data)
                elif kind == 'voice_err':
                    self.voice_status.configure(text='Lỗi: ' + data)
        except queue.Empty:
            pass
        self.root.after(120, self._poll)


def main():
    root = tk.Tk()
    try:
        App(root)
    except Exception:
        write_log(traceback.format_exc())
        raise
    root.mainloop()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
