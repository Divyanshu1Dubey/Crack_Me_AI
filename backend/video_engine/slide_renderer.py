"""
CrackLabs AI - Professional slide renderer for educational videos (V2).
Uses Pillow to create beautiful dark-mode, multi-section slides at 1280x720.
"""
import os
import re
from typing import Any, Dict
from PIL import Image, ImageDraw, ImageFont


def _clean(text):
    """Strip markdown formatting for slide display."""
    if not text:
        return ""
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
                if font.getlength(w) > max_w:
                    cur = w[:int(max_w / (font.getlength('A') or 10))] + '...'
                else:
                    cur = w
        if cur:
            lines.append(cur)
        return lines or ['']

    def _text_block(self, d, text, pos, font, fill, max_w, max_lines=None, spacing=8, focus_terms=None):
        """Draw wrapped text with basic highlight for focus terms."""
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

    # ── Scene Router ───────────────────────────────────────

    def render_scene(self, scene: Dict[str, Any], metadata: Dict[str, Any], step: int, total: int) -> Image.Image:
        """Route the scene dictionary to the correct rendering method."""
        scene_type = scene.get("type", "concept")
        
        if scene_type == "intro":
            return self.render_intro(scene, metadata, step, total)
        elif scene_type == "question_focus":
            return self.render_question(scene, metadata, step, total)
        elif scene_type in ["option_elimination", "answer_reveal"]:
            return self.render_answer(scene, metadata, step, total)
        elif scene_type in ["concept", "mechanism", "explanation"]:
            return self.render_concept(scene, step, total)
        elif scene_type in ["clinical_pearl", "mnemonic", "exam_strategy", "reference"]:
            return self.render_highlight(scene, step, total)
        elif scene_type == "takeaway":
            return self.render_takeaway(scene, step, total)
        else:
            return self.render_concept(scene, step, total)

    # ── Slide renderers ───────────────────────────────────────

    def render_intro(self, scene, metadata, step, total):
        img, d = self._bg()
        d.rectangle([(0, 0), (self.W, 4)], fill=self.ACCENT)

        cx = self.W // 2
        subject = metadata.get("subject", "General")
        year = metadata.get("year", "")
        difficulty = metadata.get("difficulty", "medium")

        d.text((cx, 170), 'CrackLabs AI', fill=self.WHITE, font=self.f['hero'], anchor='mm')
        d.text((cx, 215), 'AI-Powered Medical Education', fill=self.GRAY, font=self.f['small'], anchor='mm')

        d.line([(cx - 120, 248), (cx + 120, 248)], fill=self.ACCENT, width=2)

        diff_c = {'easy': self.GREEN, 'medium': self.AMBER, 'hard': self.RED}
        badges = [
            (f'UPSC CMS {year}' if year else 'UPSC CMS', self.ACCENT),
            (subject, self.PURPLE),
            (difficulty.upper(), diff_c.get(difficulty, self.GRAY)),
        ]
        widths = [self.f['badge'].getlength(t) + 28 for t, _ in badges if t]
        total_w = sum(widths) + 12 * (len(widths) - 1)
        bx = cx - total_w / 2
        for (txt, bg), bw in zip([b for b in badges if b[0]], widths):
            self._badge(d, (int(bx), 275), txt, bg)
            bx += bw + 12

        title = scene.get("title", f"Topic Review")
        d.text((cx, 345), title, fill=self.LIGHT, font=self.f['head'], anchor='mm')
        
        subtitle = scene.get("subtitle", "Let's break this down step by step")
        d.text((cx, 440), subtitle, fill=self.GRAY, font=self.f['body'], anchor='mm')

        d.rounded_rectangle([cx - 180, 455, cx + 180, 460], radius=2, fill=(*self.ACCENT, 60))

        self._brand(d)
        self._progress(d, step, total)
        return img

    def render_question(self, scene, metadata, step, total):
        img, d = self._bg()
        title = scene.get("title", "QUESTION")
        y = self._header(d, title, self.PAD, self.ACCENT)

        cy0, cy1 = y + 8, self.H - 60
        self._card(d, [self.PAD, cy0, self.W - self.PAD, cy1], accent=self.ACCENT)

        ip = 30
        text = metadata.get("question_text", scene.get("text", ""))
        self._text_block(d, text, (self.PAD + ip + 10, cy0 + ip),
                         self.f['body'], self.WHITE, self.CW - 2 * ip - 10,
                         max_lines=16, spacing=12)

        self._brand(d)
        self._progress(d, step, total)
        return img

    def render_answer(self, scene, metadata, step, total):
        img, d = self._bg()
        
        correct = metadata.get("correct_answer", "")
        options = metadata.get("options", {})
        
        y = self._header(d, scene.get("title", f"ANSWER: {correct}"), self.PAD, self.GREEN)

        opt_h, gap = 100, 14
        labels = ['A', 'B', 'C', 'D']

        for i, lbl in enumerate(labels):
            oy = y + 8 + i * (opt_h + gap)
            is_correct = (lbl == correct)

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

    def render_concept(self, scene, step, total):
        img, d = self._bg()
        title = scene.get("title", "EXPLANATION")
        y = self._header(d, title, self.PAD, self.TEAL)

        cy0, cy1 = y + 8, self.H - 60
        self._card(d, [self.PAD, cy0, self.W - self.PAD, cy1], accent=self.TEAL)

        ip = 28
        curr_y = cy0 + ip
        
        subtitle = scene.get("subtitle", "")
        if subtitle:
            d.text((self.PAD + ip + 10, curr_y), subtitle, fill=self.TEAL, font=self.f['body_b'])
            curr_y += 35
            d.line([(self.PAD + ip + 10, curr_y), (self.W - self.PAD - ip, curr_y)], fill=self.CARD_B, width=1)
            curr_y += 20
        
        bullets = scene.get("bullets", [])
        if bullets:
            for bullet in bullets[:4]: # Max 4 bullets
                # Draw bullet point
                r = 6
                bcx = self.PAD + ip + 15
                bcy = curr_y + 16
                d.ellipse([bcx - r, bcy - r, bcx + r, bcy + r], fill=self.TEAL)
                
                h = self._text_block(d, bullet, (self.PAD + ip + 40, curr_y),
                                   self.f['body'], self.LIGHT, self.CW - 2 * ip - 50,
                                   max_lines=3, spacing=8)
                curr_y += h + 15
        else:
            text = scene.get("narration", "")
            self._text_block(d, text, (self.PAD + ip + 10, curr_y),
                             self.f['body'], self.LIGHT, self.CW - 2 * ip - 10,
                             max_lines=14, spacing=11)

        self._brand(d)
        self._progress(d, step, total)
        return img

    def render_highlight(self, scene, step, total):
        img, d = self._bg()
        
        scene_type = scene.get("type", "")
        if scene_type == "clinical_pearl":
            header_color = self.AMBER
            accent_label = "High-Yield Point"
        elif scene_type == "mnemonic":
            header_color = self.PURPLE
            accent_label = "Remember This"
        else:
            header_color = self.ACCENT
            accent_label = "Key Point"
            
        title = scene.get("title", accent_label.upper())
        y = self._header(d, title, self.PAD, header_color)

        cy0, cy1 = y + 8, self.H - 60
        self._card(d, [self.PAD, cy0, self.W - self.PAD, cy1], accent=header_color)

        ip = 28
        curr_y = cy0 + ip
        
        subtitle = scene.get("subtitle", accent_label)
        if subtitle:
            d.text((self.PAD + ip + 10, curr_y), subtitle, fill=header_color, font=self.f['body_b'])
            curr_y += 35
            d.line([(self.PAD + ip + 10, curr_y), (self.W - self.PAD - ip, curr_y)], fill=self.CARD_B, width=1)
            curr_y += 20
        
        bullets = scene.get("bullets", [])
        if bullets:
            for bullet in bullets[:4]: 
                r = 6
                bcx = self.PAD + ip + 15
                bcy = curr_y + 16
                d.ellipse([bcx - r, bcy - r, bcx + r, bcy + r], fill=header_color)
                
                h = self._text_block(d, bullet, (self.PAD + ip + 40, curr_y),
                                   self.f['body'], self.LIGHT, self.CW - 2 * ip - 50,
                                   max_lines=3, spacing=8)
                curr_y += h + 15
        else:
            text = scene.get("narration", "")
            self._text_block(d, text, (self.PAD + ip + 10, curr_y),
                             self.f['body'], self.LIGHT, self.CW - 2 * ip - 10,
                             max_lines=12, spacing=11)

        self._brand(d)
        self._progress(d, step, total)
        return img

    def render_takeaway(self, scene, step, total):
        img, d = self._bg()
        d.rectangle([(0, 0), (self.W, 4)], fill=self.ACCENT)

        cx = self.W // 2
        d.text((cx, 230), scene.get("title", 'CrackLabs AI'), fill=self.WHITE, font=self.f['hero'], anchor='mm')
        d.text((cx, 280), scene.get("subtitle", 'AI-Powered Medical Education'), fill=self.GRAY, font=self.f['small'], anchor='mm')

        d.line([(cx - 120, 315), (cx + 120, 315)], fill=self.ACCENT, width=2)

        d.text((cx, 365), 'Keep Practicing. Keep Learning.', fill=self.LIGHT, font=self.f['head'], anchor='mm')
        d.text((cx, 415), 'www.cracklabs.app', fill=self.ACCENT, font=self.f['body_b'], anchor='mm')

        self._progress(d, step, total)
        return img
