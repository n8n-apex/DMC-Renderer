"""Deterministic neutral grain tile -> base64 PNG. Run once; paste output into styles/_grain.py.
Brand-agnostic (neutral noise only). Run: python scripts/gen_grain_tile.py"""
import base64, io, random
from PIL import Image

def make_tile(size=128, seed=7, alpha=14):
    rnd = random.Random(seed)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    for y in range(size):
        for x in range(size):
            v = rnd.randint(40, 215)                      # neutral grey noise
            px[x, y] = (v, v, v, rnd.randint(0, alpha))   # very low alpha (whisper)
    buf = io.BytesIO(); img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()

if __name__ == "__main__":
    print(make_tile())
