"""Build windows/autosearch.ico from the app's PNG icon (no Pillow needed:
an .ico may embed a PNG as-is, which Windows Vista and later read fine)."""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
png = (HERE.parent / "autosearch" / "icon-180.png").read_bytes()
if png[:8] != b"\x89PNG\r\n\x1a\n":
    sys.exit("icon-180.png is not a PNG")
w, h = struct.unpack(">II", png[16:24])
if not (0 < w <= 256 and 0 < h <= 256):
    sys.exit(f"icon must be at most 256x256, got {w}x{h}")

ico = struct.pack("<HHH", 0, 1, 1)  # reserved, type 1 = icon, one image
ico += struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(png), 22)
(HERE / "autosearch.ico").write_bytes(ico + png)
print(f"autosearch.ico scritta ({w}x{h}, {len(png) + 22} byte)")
