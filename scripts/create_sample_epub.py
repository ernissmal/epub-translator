"""Create a small original EPUB for end-to-end translation testing.

The book is intentionally short (well below free translation API limits) while
including headings, emphasis, lists, a quote, a link, and a table.
"""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "sample-books" / "the-lantern-at-dawn.epub"


def xhtml(title: str, body: str) -> str:
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head><title>{title}</title><link rel="stylesheet" type="text/css" href="style.css"/></head>
<body><main><h1>{title}</h1>{body}</main></body>
</html>
'''


CHAPTERS = [
    (
        "Chapter One: The Quiet Signal",
        '<p>At six minutes past dawn, Mara heard the old signal bell ring beneath the harbour. The bell had been silent for twenty years, and everyone in North Quay knew that silence was part of the town\'s history.</p>'
        '<p>She carried a <em>small brass lantern</em> down the hill. Its glass was cloudy, but a blue spark moved inside it whenever the tide turned. On the sea wall, she found a note tied with red thread: <q>Bring the light to the place where the maps end.</q></p>'
        '<p>Mara did not know who had written the message. She knew only that the handwriting matched her grandmother\'s old notebooks.</p>',
    ),
    (
        "Chapter Two: North Quay",
        '<p>The harbour woke slowly. Nets dried on wooden frames, gulls argued over a silver fish, and the bakery opened its blue door to the morning wind. Mara stopped at the clockmaker\'s shop because the sign in the window had changed overnight.</p>'
        '<blockquote><p>Every clock keeps two times: the time it shows and the time it remembers.</p></blockquote>'
        '<p>Inside, Tomas the clockmaker listened without interrupting. When Mara showed him the lantern, he became pale.</p>'
        '<p>“Your grandmother asked me to protect that,” he said. “If it is shining again, the northern path has opened.”</p>',
    ),
    (
        "Chapter Three: The Map Room",
        '<p>Tomas led Mara below the shop, where a narrow stair ended at a round iron door. Behind it stood a room filled with maps. Some were printed on paper; others were painted on thin sheets of copper.</p>'
        '<p>Three rules were written above the desk:</p><ul><li>Do not copy a living road.</li><li>Do not follow a name you do not understand.</li><li>Return before the lantern turns white.</li></ul>'
        '<p>The largest map showed the coastline, then faded into blank space. At its edge, a tiny mark pulsed in the same blue rhythm as the lantern.</p>',
    ),
    (
        "Chapter Four: Beyond the Breakwater",
        '<p>They left the harbour in a boat with a red sail. The water beyond the breakwater was calm, although the weather vane on the mast pointed in three directions at once.</p>'
        '<p>“The sea is remembering another shape,” Tomas explained.</p>'
        '<p>Mara watched the horizon. The blank space on the map appeared in front of them as a pale line in the water. When the boat crossed it, the town behind them vanished—not dramatically, but as if someone had closed a book.</p>'
        '<p>For a while there was only water, sky, and the steady blue glow of the lantern.</p>',
    ),
    (
        "Chapter Five: The Garden of Names",
        '<p>The northern path led to an island covered with glass flowers. Each flower carried a name, and each name belonged to someone who had once been forgotten.</p>'
        '<p>Mara found her grandmother\'s name on a white stem. Beneath it was a date and a short instruction: <strong>Speak the true direction aloud.</strong></p>'
        '<p>She thought of North Quay, the clockmaker, and the red thread. Then she said, “Home is the direction that leaves a light for the next traveller.”</p>'
        '<p>The flowers opened. Their reflections joined together and formed a bridge across the dark water.</p>',
    ),
    (
        "Chapter Six: The Light Returns",
        '<p>Mara and Tomas crossed the bridge before the lantern turned white. At the far end, the harbour waited beneath a violet sky. The town had not moved, but every window held a small blue flame.</p>'
        '<p>Years later, children would ask Mara why the harbour bell rang at dawn. She would tell them that some warnings are also invitations.</p>'
        '<p>For additional notes about the town\'s history, visit <a href="https://example.com/north-quay">the North Quay archive</a>. The archive was never real, but it was a useful place to begin.</p>'
        '<table><thead><tr><th>Object</th><th>Meaning</th></tr></thead><tbody><tr><td>Blue lantern</td><td>Return safely</td></tr><tr><td>Red thread</td><td>Follow memory</td></tr></tbody></table>',
    ),
]


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w") as epub:
        epub.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        epub.writestr("META-INF/container.xml", '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>''')
        epub.writestr("OEBPS/style.css", "body{font-family:serif;line-height:1.6;margin:8%} main{max-width:42em;margin:auto} table{border-collapse:collapse} td,th{border:1px solid #888;padding:.4em}")
        epub.writestr("OEBPS/title.xhtml", xhtml("The Lantern at Dawn", '<p>An original short story for EPUB translation testing.</p><p><em>Created for the EPUB Translator project.</em></p>'))

        manifest = ['<item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>', '<item id="css" href="style.css" media-type="text/css"/>']
        spine = ['<itemref idref="title"/>']
        for index, (title, body) in enumerate(CHAPTERS, start=1):
            item_id = f"chapter-{index}"
            href = f"chapter-{index}.xhtml"
            epub.writestr(f"OEBPS/{href}", xhtml(title, body))
            manifest.append(f'<item id="{item_id}" href="{href}" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="{item_id}"/>')

        epub.writestr("OEBPS/content.opf", f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">urn:uuid:6e7c2db4-0d24-4f92-bf57-7a0bc02bda44</dc:identifier>
    <dc:title>The Lantern at Dawn</dc:title><dc:language>en</dc:language><dc:creator>AR Ltd SIA</dc:creator>
  </metadata>
  <manifest>{''.join(manifest)}</manifest>
  <spine>{''.join(spine)}</spine>
</package>''')

    print(f"Created {OUTPUT}")
    print(f"Approximate source characters: {sum(len(body) for _, body in CHAPTERS):,}")


if __name__ == "__main__":
    main()
