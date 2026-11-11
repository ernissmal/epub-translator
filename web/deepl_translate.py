from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from lxml import etree


LANGUAGE_CODES = {
    "bulgarian": "BG",
    "czech": "CS",
    "danish": "DA",
    "dutch": "NL",
    "english": "EN-US",
    "estonian": "ET",
    "finnish": "FI",
    "french": "FR",
    "german": "DE",
    "greek": "EL",
    "hungarian": "HU",
    "italian": "IT",
    "japanese": "JA",
    "latvian": "LV",
    "lithuanian": "LT",
    "polish": "PL",
    "portuguese": "PT-PT",
    "romanian": "RO",
    "russian": "RU",
    "slovak": "SK",
    "slovenian": "SL",
    "spanish": "ES",
    "swedish": "SV",
    "turkish": "TR",
    "ukrainian": "UK",
}


def _target_code(language: str) -> str:
    normalized = language.strip().lower()
    if normalized in LANGUAGE_CODES:
        return LANGUAGE_CODES[normalized]
    return language.strip().upper()


def _translate_html(html: str, target_language: str) -> str:
    api_key = (os.getenv("DEEPL_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("DEEPL_API_KEY is not configured")

    endpoint = (os.getenv("DEEPL_API_URL") or "https://api-free.deepl.com/v2/translate").strip()
    payload = urllib.parse.urlencode(
        {
            "text": html,
            "target_lang": _target_code(target_language),
            "tag_handling": "html",
            "preserve_formatting": "1",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Authorization": f"DeepL-Auth-Key {api_key}", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"DeepL API error ({error.code}): {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"DeepL connection error: {error.reason}") from error

    translations = result.get("translations") or []
    if not translations or not translations[0].get("text"):
        raise RuntimeError("DeepL returned an empty translation")
    return translations[0]["text"]


def _translate_xhtml(data: bytes, target_language: str) -> bytes:
    parser = etree.XMLParser(remove_blank_text=False, recover=True)
    root = etree.fromstring(data, parser)
    body = next((element for element in root.iter() if etree.QName(element).localname == "body"), None)
    if body is None or len(body) == 0:
        return data

    children = list(body)
    translated_fragments: list[str] = []
    batch: list[str] = []
    batch_size = 0
    for child in children:
        fragment = etree.tostring(child, encoding="unicode", with_tail=False)
        if batch and batch_size + len(fragment) > 40000:
            translated_fragments.append(_translate_html("<div>" + "".join(batch) + "</div>", target_language))
            batch = []
            batch_size = 0
        batch.append(fragment)
        batch_size += len(fragment)
    if batch:
        translated_fragments.append(_translate_html("<div>" + "".join(batch) + "</div>", target_language))

    for child in children:
        body.remove(child)
    for fragment in translated_fragments:
        wrapper = etree.fromstring(fragment.encode("utf-8"), parser)
        for child in list(wrapper):
            body.append(child)
    return etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=False)


def translate_epub_with_deepl(source_path: Path, target_path: Path, target_language: str) -> None:
    with ZipFile(source_path, "r") as source:
        entries = [(info, source.read(info.filename)) for info in source.infolist()]

    with ZipFile(target_path, "w") as target:
        for info, data in entries:
            if info.filename.lower().endswith((".xhtml", ".html", ".htm")):
                data = _translate_xhtml(data, target_language)
            compression = ZIP_STORED if info.filename == "mimetype" else ZIP_DEFLATED
            target.writestr(info, data, compress_type=compression)
