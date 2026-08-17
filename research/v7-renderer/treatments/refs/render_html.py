import sys, asyncio
from playwright.async_api import async_playwright

W, H = 1680, 1188

async def shot(html_path, png_path):
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        await pg.goto("file://" + html_path)
        await pg.wait_for_load_state("networkidle")
        await pg.evaluate(
            "async () => { await document.fonts.ready; "
            "await Promise.all([...document.images].map(i => i.complete ? 0 : "
            "new Promise(r => { i.onload = i.onerror = r; }))); }"
        )
        await pg.screenshot(path=png_path, clip={"x": 0, "y": 0, "width": W, "height": H})
        await b.close()
        print("WROTE", png_path)

async def main():
    pairs = [(sys.argv[i], sys.argv[i + 1]) for i in range(1, len(sys.argv), 2)]
    for h, p_ in pairs:
        await shot(h, p_)

asyncio.run(main())
