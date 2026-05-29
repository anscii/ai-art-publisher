import io
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont

_CANVAS_W = 1080
_CANVAS_H = 1920
_JPEG_QUALITY = 92

_FONT_DIR = Path("/usr/share/fonts/opentype/inter")
_FONT_BODY = _FONT_DIR / "Inter-SemiBold.otf"  # weight 600, matches CSS font-weight:600
_FONT_TITLE = _FONT_DIR / "Inter-Bold.otf"  # weight 700

_BODY_SIZE = 64
_TITLE_SIZE = 80

_PAD_H = 120  # horizontal padding each side
_SAFE_V = 220  # vertical safe area top/bottom
_LINE_SPACING = 1.3
_SHADOW_OFFSET = (2, 3)
_SHADOW_OPACITY = 160  # out of 255
_DIM_OPACITY = 140  # dark overlay (0-255)
_BLUR_RADIUS = 20

_BG_COLORS = {
    "solid_dark": (18, 18, 18),
    "solid_light": (240, 235, 225),
    "solid_accent": (184, 80, 31),
}


def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default(size=size)  # type: ignore[return-value]


def _cover_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def _parse_color(hex_color: str) -> tuple[int, int, int]:
    try:
        rgb = ImageColor.getrgb(hex_color)
        return (rgb[0], rgb[1], rgb[2])
    except (ValueError, AttributeError):
        return (255, 255, 255)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            test = f"{current} {word}"
            bbox = font.getbbox(test)
            if bbox[2] - bbox[0] <= max_width:
                current = test
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _line_height(font: ImageFont.FreeTypeFont) -> int:
    _, _, _, h = font.getbbox("Ag")
    return int(h * _LINE_SPACING)


def _block_height(lines: list[str], font: ImageFont.FreeTypeFont) -> int:
    return _line_height(font) * len(lines) if lines else 0


def _draw_text_block(
    canvas: Image.Image,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    top_y: int,
    pad_x: int,
    color: tuple[int, int, int] = (255, 255, 255),
) -> None:
    draw = ImageDraw.Draw(canvas, "RGBA")
    lh = _line_height(font)
    y = top_y
    for line in lines:
        if line.strip():
            lw = int(font.getbbox(line)[2])
            x = max((_CANVAS_W - lw) // 2, pad_x)
            # shadow
            draw.text(
                (x + _SHADOW_OFFSET[0], y + _SHADOW_OFFSET[1]),
                line,
                font=font,
                fill=(0, 0, 0, _SHADOW_OPACITY),
            )
            draw.text((x, y), line, font=font, fill=(*color, 255))
        y += lh


def _text_top_y(total_h: int, align: str) -> int:
    if align == "top":
        return _SAFE_V
    if align == "bottom":
        return _CANVAS_H - _SAFE_V - total_h
    return (_CANVAS_H - total_h) // 2  # middle


class StoryRenderer:
    def __init__(self) -> None:
        self._cached_body_size = _BODY_SIZE
        self._body_font = _load_font(_FONT_BODY, _BODY_SIZE)
        self._title_font = _load_font(_FONT_TITLE, _TITLE_SIZE)

    def render_frame(self, frame, image_bytes: bytes | None) -> bytes:
        # Per-frame font size override; falls back to global defaults
        fs = getattr(frame, "font_size", None)
        body_size = fs if fs is not None else _BODY_SIZE
        title_size = round(body_size * 1.25)
        # Reload fonts only when size changes (avoids repeated disk reads)
        if body_size != self._cached_body_size:
            self._body_font = _load_font(_FONT_BODY, body_size)
            self._title_font = _load_font(_FONT_TITLE, title_size)
            self._cached_body_size = body_size
        if frame.frame_type == "image":
            return self._render_image_frame(frame, image_bytes)
        return self._render_text_frame(frame, image_bytes)

    def _base_image(self, image_bytes: bytes | None) -> Image.Image:
        if image_bytes:
            try:
                src = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                return _cover_crop(src, _CANVAS_W, _CANVAS_H)
            except Exception:
                pass
        return Image.new("RGB", (_CANVAS_W, _CANVAS_H), (18, 18, 18))

    def _render_image_frame(self, frame, image_bytes: bytes | None) -> bytes:
        canvas = self._base_image(image_bytes)

        if frame.title:
            title_pos = getattr(frame, "title_position", "bottom")
            rgba = canvas.convert("RGBA")
            draw = ImageDraw.Draw(rgba, "RGBA")

            # Bar height: at least 22% of frame, grows to fit wrapped title text
            title_lines = _wrap_text(frame.title, self._title_font, _CANVAS_W - 2 * _PAD_H)
            text_h = _block_height(title_lines, self._title_font)
            _BAR_V_PAD = 112  # top + bottom padding (px at full resolution)
            bar_h = max(int(_CANVAS_H * 0.22), text_h + _BAR_V_PAD)
            if title_pos == "top":
                bar_top, bar_bot = 0, bar_h
            elif title_pos == "middle":
                bar_top = (_CANVAS_H - bar_h) // 2
                bar_bot = bar_top + bar_h
            else:
                bar_top, bar_bot = _CANVAS_H - bar_h, _CANVAS_H

            bg_mode = getattr(frame, "background_mode", "solid_dark")
            _BAR_FILL: dict[str, tuple[int, int, int, int]] = {
                "solid_dark": (0, 0, 0, 217),
                "solid_light": (245, 240, 230, 235),
                "solid_accent": (184, 80, 31, 235),
            }
            title_color = _parse_color(getattr(frame, "text_color", "#ffffff"))
            lines = title_lines  # already wrapped above
            total_h = text_h

            if bg_mode == "image_clean":
                # floating title — no bar rectangle, just shadowed text
                center_y = (bar_top + bar_bot) // 2
                top_y = center_y - total_h // 2
            else:
                bar_fill = _BAR_FILL.get(bg_mode, (0, 0, 0, 120))
                draw.rectangle([(0, bar_top), (_CANVAS_W, bar_bot)], fill=bar_fill)
                center_y = (bar_top + bar_bot) // 2
                top_y = center_y - total_h // 2

            _draw_text_block(rgba, lines, self._title_font, top_y, _PAD_H, title_color)
            canvas = rgba.convert("RGB")

        return _to_jpeg(canvas)

    def _render_text_frame(self, frame, image_bytes: bytes | None) -> bytes:
        mode = getattr(frame, "background_mode", "image_blur_dim")

        if mode in _BG_COLORS:
            canvas: Image.Image = Image.new("RGB", (_CANVAS_W, _CANVAS_H), _BG_COLORS[mode])
        else:
            bg = self._base_image(image_bytes)
            if mode != "image_clean":
                bg = bg.filter(ImageFilter.GaussianBlur(radius=_BLUR_RADIUS))
            canvas = bg

        canvas = canvas.convert("RGBA")

        if mode == "image_blur_dim":
            overlay = Image.new("RGBA", (_CANVAS_W, _CANVAS_H), (0, 0, 0, _DIM_OPACITY))
            canvas = Image.alpha_composite(canvas, overlay)

        text_color = _parse_color(getattr(frame, "text_color", "#ffffff"))
        text_align = getattr(frame, "text_align", "middle")
        usable_w = _CANVAS_W - 2 * _PAD_H

        if frame.title:
            title_lines = _wrap_text(frame.title, self._title_font, usable_w)
            body_lines = _wrap_text(frame.text or "", self._body_font, usable_w)
            gap = 40
            total_h = (
                _block_height(title_lines, self._title_font)
                + gap
                + _block_height(body_lines, self._body_font)
            )
            top_y = _text_top_y(total_h, text_align)
            _draw_text_block(canvas, title_lines, self._title_font, top_y, _PAD_H, text_color)
            title_h = _block_height(title_lines, self._title_font)
            _draw_text_block(
                canvas, body_lines, self._body_font, top_y + title_h + gap, _PAD_H, text_color
            )
        else:
            lines = _wrap_text(frame.text or "", self._body_font, usable_w)
            total_h = _block_height(lines, self._body_font)
            top_y = _text_top_y(total_h, text_align)
            _draw_text_block(canvas, lines, self._body_font, top_y, _PAD_H, text_color)

        return _to_jpeg(canvas.convert("RGB"))


def _to_jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
    return buf.getvalue()
