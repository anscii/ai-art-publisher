import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_CANVAS_W = 1080
_CANVAS_H = 1920
_JPEG_QUALITY = 92

_FONT_DIR = Path("/usr/share/fonts/truetype/liberation")
_FONT_SERIF_REGULAR = _FONT_DIR / "LiberationSerif-Regular.ttf"
_FONT_SERIF_BOLD = _FONT_DIR / "LiberationSerif-Bold.ttf"

_BODY_SIZE = 48
_TITLE_SIZE = 60

_PAD_H = 120  # horizontal padding each side
_SAFE_V = 220  # vertical safe area top/bottom
_LINE_SPACING = 1.3
_SHADOW_OFFSET = (2, 3)
_SHADOW_OPACITY = 160  # out of 255
_DIM_OPACITY = 140  # dark overlay (0-255)
_BLUR_RADIUS = 20


def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default(size=size)  # type: ignore[return-value]


def _cover_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize + center-crop image to exactly (target_w, target_h)."""
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Wrap text into lines not exceeding max_width pixels."""
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


def _text_block_height(lines: list[str], font: ImageFont.FreeTypeFont, line_gap: int) -> int:
    if not lines:
        return 0
    _, _, _, h = font.getbbox("Ag")
    return int(len(lines) * (h * _LINE_SPACING) + (len(lines) - 1) * line_gap)


def _draw_shadowed_text(
    draw: ImageDraw.ImageDraw,
    pos: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
) -> None:
    sx, sy = pos[0] + _SHADOW_OFFSET[0], pos[1] + _SHADOW_OFFSET[1]
    draw.text((sx, sy), text, font=font, fill=(0, 0, 0, _SHADOW_OPACITY))
    draw.text(pos, text, font=font, fill=(255, 255, 255, 255))


def _draw_text_block(
    canvas: Image.Image,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    center_y: int,
    pad_x: int,
) -> None:
    """Draw a centered multi-line text block on the canvas using RGBA overlay."""
    draw = ImageDraw.Draw(canvas, "RGBA")
    bbox_h = font.getbbox("Ag")
    line_h = int((bbox_h[3] - bbox_h[1]) * _LINE_SPACING)
    total_h = line_h * len(lines)
    y = center_y - total_h // 2

    for line in lines:
        if line.strip():
            lw = int(font.getbbox(line)[2])
            x = max((_CANVAS_W - lw) // 2, pad_x)
            _draw_shadowed_text(draw, (x, y), line, font)
        y += line_h


class StoryRenderer:
    def __init__(self) -> None:
        self._body_font = _load_font(_FONT_SERIF_REGULAR, _BODY_SIZE)
        self._title_font = _load_font(_FONT_SERIF_BOLD, _TITLE_SIZE)

    def render_frame(self, frame, image_bytes: bytes | None) -> bytes:
        """Render a StoryFrame to a 1080x1920 JPEG and return the bytes."""
        if frame.frame_type == "image":
            return self._render_image_frame(frame, image_bytes)
        return self._render_text_frame(frame, image_bytes)

    def _base_image(self, image_bytes: bytes | None) -> Image.Image:
        """Return a cover-cropped 1080x1920 RGB image from bytes, or dark fallback."""
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
            rgba_canvas = canvas.convert("RGBA")
            draw = ImageDraw.Draw(rgba_canvas, "RGBA")
            # Semi-transparent dark strip at bottom third for readability
            strip_top = int(_CANVAS_H * 0.65)
            draw.rectangle(
                [(0, strip_top), (_CANVAS_W, _CANVAS_H)],
                fill=(0, 0, 0, 120),
            )
            lines = _wrap_text(frame.title, self._title_font, _CANVAS_W - 2 * _PAD_H)
            center_y = strip_top + (_CANVAS_H - strip_top) // 2
            _draw_text_block(rgba_canvas, lines, self._title_font, center_y, _PAD_H)
            canvas = rgba_canvas.convert("RGB")

        return _to_jpeg(canvas)

    def _render_text_frame(self, frame, image_bytes: bytes | None) -> bytes:
        mode = getattr(frame, "background_mode", "image_blur_dim")

        if mode == "solid_dark":
            canvas = Image.new("RGB", (_CANVAS_W, _CANVAS_H), (18, 18, 18))
        elif mode == "solid_light":
            canvas = Image.new("RGB", (_CANVAS_W, _CANVAS_H), (240, 235, 225))
        else:
            # image_blur_dim or image_clean
            bg = self._base_image(image_bytes)
            if mode != "image_clean":
                bg = bg.filter(ImageFilter.GaussianBlur(radius=_BLUR_RADIUS))
            canvas = bg

        canvas = canvas.convert("RGBA")

        if mode not in ("solid_dark", "solid_light", "image_clean"):
            overlay = Image.new("RGBA", (_CANVAS_W, _CANVAS_H), (0, 0, 0, _DIM_OPACITY))
            canvas = Image.alpha_composite(canvas, overlay)

        # Text content area
        usable_w = _CANVAS_W - 2 * _PAD_H
        center_y = _CANVAS_H // 2

        if frame.title:
            title_lines = _wrap_text(frame.title, self._title_font, usable_w)
            body_lines = _wrap_text(frame.text or "", self._body_font, usable_w)

            title_h = _text_block_height(title_lines, self._title_font, 0)
            body_h = _text_block_height(body_lines, self._body_font, 0)
            gap = 40
            total_h = title_h + gap + body_h

            title_center = center_y - total_h // 2 + title_h // 2
            body_center = title_center + title_h // 2 + gap + body_h // 2

            _draw_text_block(canvas, title_lines, self._title_font, title_center, _PAD_H)
            _draw_text_block(canvas, body_lines, self._body_font, body_center, _PAD_H)
        else:
            lines = _wrap_text(frame.text or "", self._body_font, usable_w)
            _draw_text_block(canvas, lines, self._body_font, center_y, _PAD_H)

        return _to_jpeg(canvas.convert("RGB"))


def _to_jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
    return buf.getvalue()
