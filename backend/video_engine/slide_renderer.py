"""
CrackLabs AI - Professional slide renderer for educational videos.
Uses Pillow to create beautiful dark-mode, multi-section slides at 1280x720.
"""
import os
import re
from PIL import Image, ImageDraw, ImageFont


def _clean(text):
    """Strip markdown formatting for slide display."""
    t = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    t = re.sub(r'\*(.*?)\*', r'\1', t)
    t = re.sub(r'#{1,6}\s+', '', t)
    t = re.sub(r'`(.*?)`', r'\1', t)
    t = re.sub(r'\n{2,}', '\n', t)
    return t.strip()


class SlideRenderer:
    """Renders dark-mode educational slides with Pillow."""

    W, H = 1280, 720
    PAD = 50
    CW = W - 2 * PAD  # content width

    # ── Design tokens ─────────────────────────────────────────
    BG_TOP    = (8, 12, 28)
    BG_BOT    = (20, 30, 52)
    CARD      = (22, 33, 58)
    CARD_B    = (40, 55, 85)
    WHITE     = (240, 240, 245)
    GRAY      = (140, 155, 175)
    LIGHT     = (195, 205, 218)
    ACCENT    = (99, 102, 241)
    GREEN     = (34, 197, 94)
    RED       = (239, 68, 68)
    PURPLE    = (139, 92, 246)
    AMBER     = (245, 158, 11)
    TEAL      = (20, 184, 166)
    CORRECT   = (15, 58, 38)
    DIMMED    = (60, 70, 90)

    def __init__(self):
        self._init_fonts()

    # ── Font loading ──────────────────────────────────────────

    def _init_fonts(self):
        reg_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            'C:/Windows/Fonts/segoeui.ttf',
            'C:/Windows/Fonts/arial.ttf',
        ]
        bold_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            'C:/Windows/Fonts/segoeuib.ttf',
            'C:/Windows/Fonts/arialbd.ttf',
        ]
        reg = next((p for p in reg_paths if os.path.exists(p)), None)
        bold = next((p for p in bold_paths if os.path.exists(p)), None) or reg

        def mk(path, sz):
            if path:
                try:
                    return ImageFont.truetype(path, sz)
                except Exception:
                    pass
            return ImageFont.load_default()

        self.f = {
            'hero':   mk(bold, 48),
            'title':  mk(bold, 38),
            'head':   mk(bold, 30),
            'body':   mk(reg, 26),
            'body_b': mk(bold, 26),
            'small':  mk(reg, 22),
            'tiny':   mk(reg, 18),
            'opt':    mk(reg, 24),
            'opt_l':  mk(bold, 28),
            'badge':  mk(bold, 20),
            'brand':  mk(bold, 18),
        }

    # ── Drawing helpers ───────────────────────────────────────

    def _bg(self):
        """Create a vertical gradient background."""
        img = Image.new('RGB', (self.W, self.H))
        d = ImageDraw.Draw(img)
        for y in range(self.H):
            r = y / self.H
            c = tuple(int(self.BG_TOP[i] + (self.BG_BOT[i] - self.BG_TOP[i]) * r) for i in range(3))
            d.line([(0, y), (self.W, y)], fill=c)
        return img, d

    def _card(self, d, xy, accent=None, radius=16):
        d.rounded_rectangle(xy, radius=radius, fill=self.CARD, outline=self.CARD_B)
        if accent:
            x0, y0, _, y1 = xy
            d.rounded_rectangle([x0, y0 + 6, x0 + 5, y1 - 6], radius=2, fill=accent)

    def _badge(self, d, pos, text, bg, fg=None):
        fg = fg or self.WHITE
        font = self.f['badge']
        tw = font.getlength(text)
        bbox = font.getbbox(text)
        th = bbox[3] - bbox[1]
        px, py = 14, 6
        x, y = pos
        d.rounded_rectangle([x, y, x + tw + 2 * px, y + th + 2 * py], radius=12, fill=bg)
        d.text((x + px, y + py - 2), text, fill=fg, font=font)
        return int(tw + 2 * px)

    def _wrap(self, text, font, max_w):
        """Word-wrap text to fit within max_w pixels."""
        words = text.split()
        if not words:
            return ['']
        lines, cur = [], ''
        for w in words:
            test = f'{cur} {w}'.strip()
            if font.getlength(test) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                # Handle very long words
                if font.getlength(w) > max_w:
                    cur = w[:int(max_w / (font.getlength('A') or 10))] + '...'
                else:
                    cur = w
        if cur:
            lines.append(cur)
        return lines or ['']

    def _text_block(self, d, text, pos, font, fill, max_w, max_lines=None, spacing=8):
        """Draw wrapped text. Returns height used."""
        text = _clean(text)
        lines = self._wrap(text, font, max_w)
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1][:-3] + '...' if len(lines[-1]) > 3 else '...'
        x, y = pos
        h = 0
        for ln in lines:
            d.text((x, y), ln, fill=fill, font=font)
            lh = font.getbbox(ln)[3] - font.getbbox(ln)[1]
            y += lh + spacing
            h += lh + spacing
        return h

    def _brand(self, d):
        d.text((self.W - self.PAD, self.H - 38), 'CrackLabs AI',
               fill=self.ACCENT, font=self.f['brand'], anchor='ra')

    def _progress(self, d, step, total):
        by = self.H - 4
        d.rectangle([(0, by), (self.W, self.H)], fill=(25, 35, 55))
        pw = int((step / max(total, 1)) * self.W)
        d.rectangle([(0, by), (pw, self.H)], fill=self.ACCENT)

    def _header(self, d, text, y, dot=None):
        x = self.PAD
        if dot:
            d.ellipse([x, y + 4, x + 14, y + 18], fill=dot)
            x += 22
        d.text((x, y), text.upper(), fill=self.GRAY, font=self.f['small'])
        return y + 34

    # ── Slide renderers ───────────────────────────────────────

    def render_title(self, subject, year, difficulty, q_id, step, total):
        img, d = self._bg()
        d.rectangle([(0, 0), (self.W, 4)], fill=self.ACCENT)

        cx = self.W // 2

        # Brand
        d.text((cx, 170), 'CrackLabs AI', fill=self.WHITE, font=self.f['hero'], anchor='mm')
        d.text((cx, 215), 'AI-Powered Medical Education', fill=self.GRAY, font=self.f['small'], anchor='mm')

        # Decorative line
        d.line([(cx - 120, 248), (cx + 120, 248)], fill=self.ACCENT, width=2)

        # Badges
        diff_c = {'easy': self.GREEN, 'medium': self.AMBER, 'hard': self.RED}
        badges = [
            (f'UPSC CMS {year}', self.ACCENT),
            (subject, self.PURPLE),
            (difficulty.upper(), diff_c.get(difficulty, self.GRAY)),
        ]
        widths = [self.f['badge'].getlength(t) + 28 for t, _ in badges]
        total_w = sum(widths) + 12 * (len(badges) - 1)
        bx = cx - total_w / 2
        for (txt, bg), bw in zip(badges, widths):
            self._badge(d, (int(bx), 275), txt, bg)
            bx += bw + 12

        d.text((cx, 345), f'Question #{q_id}', fill=self.LIGHT, font=self.f['head'], anchor='mm')

        # Subtitle
        d.text((cx, 440), "Let's break this down step by step", fill=self.GRAY, font=self.f['body'], anchor='mm')

        # Subtle glow effect
        d.rounded_rectangle([cx - 180, 455, cx + 180, 460], radius=2, fill=(*self.ACCENT, 60))

        self._brand(d)
        self._progress(d, step, total)
        return img

    def render_question(self, text, step, total):
        img, d = self._bg()
        y = self._header(d, 'QUESTION', self.PAD, self.ACCENT)

        cy0, cy1 = y + 8, self.H - 60
        self._card(d, [self.PAD, cy0, self.W - self.PAD, cy1], accent=self.ACCENT)

        ip = 30
        self._text_block(d, text, (self.PAD + ip + 10, cy0 + ip),
                         self.f['body'], self.WHITE, self.CW - 2 * ip - 10,
                         max_lines=16, spacing=12)

        self._brand(d)
        self._progress(d, step, total)
        return img

    def render_options(self, options, step, total):
        img, d = self._bg()
        y = self._header(d, 'OPTIONS  —  THINK ABOUT YOUR ANSWER', self.PAD, self.AMBER)

        opt_h, gap = 100, 14
        labels = ['A', 'B', 'C', 'D']
        colors = [self.ACCENT, self.PURPLE, self.TEAL, self.AMBER]

        for i, lbl in enumerate(labels):
            oy = y + 8 + i * (opt_h + gap)
            self._card(d, [self.PAD, oy, self.W - self.PAD, oy + opt_h])

            # Label circle
            cx_c = self.PAD + 44
            cy_c = oy + opt_h // 2
            r = 22
            d.ellipse([cx_c - r, cy_c - r, cx_c + r, cy_c + r], fill=colors[i])
            d.text((cx_c, cy_c), lbl, fill=self.WHITE, font=self.f['opt_l'], anchor='mm')

            # Option text
            self._text_block(d, options.get(lbl, ''), (self.PAD + 82, oy + 20),
                             self.f['opt'], self.LIGHT, self.CW - 100, max_lines=3, spacing=6)

        self._brand(d)
        self._progress(d, step, total)
        return img

    def render_answer(self, options, correct, step, total):
        img, d = self._bg()
        y = self._header(d, f'CORRECT ANSWER:  {correct}', self.PAD, self.GREEN)

        opt_h, gap = 100, 14
        labels = ['A', 'B', 'C', 'D']

        for i, lbl in enumerate(labels):
            oy = y + 8 + i * (opt_h + gap)
            is_correct = lbl == correct

            if is_correct:
                d.rounded_rectangle([self.PAD, oy, self.W - self.PAD, oy + opt_h],
                                    radius=16, fill=self.CORRECT, outline=self.GREEN, width=2)
            else:
                self._card(d, [self.PAD, oy, self.W - self.PAD, oy + opt_h])

            cx_c = self.PAD + 44
            cy_c = oy + opt_h // 2
            r = 22
            circle_c = self.GREEN if is_correct else self.DIMMED
            d.ellipse([cx_c - r, cy_c - r, cx_c + r, cy_c + r], fill=circle_c)
            d.text((cx_c, cy_c), lbl, fill=self.WHITE, font=self.f['opt_l'], anchor='mm')

            txt_c = self.WHITE if is_correct else self.DIMMED
            self._text_block(d, options.get(lbl, ''), (self.PAD + 82, oy + 20),
                             self.f['opt'], txt_c, self.CW - 100, max_lines=3, spacing=6)

        self._brand(d)
        self._progress(d, step, total)
        return img

    def render_explanation(self, text, slide_num, total_exp, step, total):
        img, d = self._bg()
        label = 'EXPLANATION'
        if total_exp > 1:
            label += f'  ({slide_num}/{total_exp})'
        y = self._header(d, label, self.PAD, self.TEAL)

        cy0, cy1 = y + 8, self.H - 60
        self._card(d, [self.PAD, cy0, self.W - self.PAD, cy1], accent=self.TEAL)

        ip = 28
        self._text_block(d, text, (self.PAD + ip + 10, cy0 + ip),
                         self.f['body'], self.LIGHT, self.CW - 2 * ip - 10,
                         max_lines=16, spacing=11)

        self._brand(d)
        self._progress(d, step, total)
        return img

    def render_clinical_pearl(self, text, step, total):
        img, d = self._bg()
        y = self._header(d, 'CLINICAL PEARL', self.PAD, self.AMBER)

        cy0, cy1 = y + 8, self.H - 60
        self._card(d, [self.PAD, cy0, self.W - self.PAD, cy1], accent=self.AMBER)

        # Header inside card
        ip = 28
        d.text((self.PAD + ip + 10, cy0 + ip), 'High-Yield Point',
               fill=self.AMBER, font=self.f['body_b'])

        d.line([(self.PAD + ip + 10, cy0 + ip + 35),
                (self.W - self.PAD - ip, cy0 + ip + 35)], fill=self.CARD_B, width=1)

        self._text_block(d, text, (self.PAD + ip + 10, cy0 + ip + 48),
                         self.f['body'], self.LIGHT, self.CW - 2 * ip - 10,
                         max_lines=13, spacing=11)

        self._brand(d)
        self._progress(d, step, total)
        return img

    def render_mnemonic(self, text, step, total):
        img, d = self._bg()
        y = self._header(d, 'MEMORY TRICK', self.PAD, self.PURPLE)

        cy0, cy1 = y + 8, self.H - 60
        self._card(d, [self.PAD, cy0, self.W - self.PAD, cy1], accent=self.PURPLE)

        ip = 28
        d.text((self.PAD + ip + 10, cy0 + ip), 'Remember This',
               fill=self.PURPLE, font=self.f['body_b'])

        d.line([(self.PAD + ip + 10, cy0 + ip + 35),
                (self.W - self.PAD - ip, cy0 + ip + 35)], fill=self.CARD_B, width=1)

        self._text_block(d, text, (self.PAD + ip + 10, cy0 + ip + 48),
                         self.f['body'], self.LIGHT, self.CW - 2 * ip - 10,
                         max_lines=13, spacing=11)

        self._brand(d)
        self._progress(d, step, total)
        return img

    def render_key_differentiators(self, text, step, total):
        """Extra slide for key differentiators / why-wrong analysis."""
        img, d = self._bg()
        y = self._header(d, 'KEY DIFFERENTIATORS', self.PAD, self.ACCENT)

        cy0, cy1 = y + 8, self.H - 60
        self._card(d, [self.PAD, cy0, self.W - self.PAD, cy1], accent=self.ACCENT)

        ip = 28
        self._text_block(d, text, (self.PAD + ip + 10, cy0 + ip),
                         self.f['body'], self.LIGHT, self.CW - 2 * ip - 10,
                         max_lines=16, spacing=11)

        self._brand(d)
        self._progress(d, step, total)
        return img

    def render_outro(self, step, total):
        img, d = self._bg()
        d.rectangle([(0, 0), (self.W, 4)], fill=self.ACCENT)

        cx = self.W // 2
        d.text((cx, 230), 'CrackLabs AI', fill=self.WHITE, font=self.f['hero'], anchor='mm')
        d.text((cx, 280), 'AI-Powered Medical Education', fill=self.GRAY, font=self.f['small'], anchor='mm')

        d.line([(cx - 120, 315), (cx + 120, 315)], fill=self.ACCENT, width=2)

        d.text((cx, 365), 'Keep Practicing. Keep Learning.', fill=self.LIGHT, font=self.f['head'], anchor='mm')
        d.text((cx, 415), 'www.cracklabs.app', fill=self.ACCENT, font=self.f['body_b'], anchor='mm')

        self._progress(d, step, total)
        return img
