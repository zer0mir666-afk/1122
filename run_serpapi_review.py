import asyncio
import base64
import io
import json
import re
import sys
from pathlib import Path

import httpx
from PIL import Image


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "inputs" / "serpapi-products"
SEARCH = ROOT / "assets" / "serpapi-lab"
OUTPUT = SEARCH / "review.json"
ENV_FILE = Path(r"C:\Users\magom\OneDrive\Рабочий стол\websites\стас бот по фото\.env")

PRODUCTS = [
    {
        "id": "01-brunello-zip-cardigan",
        "brand": "Brunello Cucinelli",
        "source": "01-brunello-zip-cardigan.jpg",
        "caption": "Brunello Cucinelli — серый вязаный кардиган на молнии",
        "candidate_numbers": [1, 2, 3, 5, 11, 14],
    },
    {
        "id": "02-brunello-shawl-cardigan",
        "brand": "Brunello Cucinelli",
        "source": "02-brunello-shawl-cardigan.jpg",
        "caption": "Brunello Cucinelli — белый кардиган с шалевым воротником",
        "candidate_numbers": [3, 7, 13, 14, 29, 51],
    },
    {
        "id": "03-loro-piana-hoodie",
        "brand": "Loro Piana",
        "source": "03-loro-piana-hoodie.jpg",
        "caption": "Loro Piana — серый худи на молнии",
        "candidate_numbers": [1, 2, 3, 4, 5, 6],
    },
    {
        "id": "04-loro-piana-jacket",
        "brand": "Loro Piana",
        "source": "04-loro-piana-jacket.jpg",
        "caption": "Loro Piana — светлая куртка-бомбер",
        "candidate_numbers": [1, 2, 3, 4, 5, 6],
    },
]


def load_star_key() -> str:
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("STARIMG_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("STARIMG_KEY not found")


def data_url(path: Path) -> str:
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((800, 800))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=82, optimize=True)
    return f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode('ascii')}"


def parse_json(raw: str) -> dict:
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


async def download_candidates(client: httpx.AsyncClient, product: dict) -> list[dict]:
    data = json.loads((SEARCH / f"{product['id']}.json").read_text(encoding="utf-8"))
    matches = data.get("visual_matches", [])
    target = SEARCH / product["id"]
    target.mkdir(parents=True, exist_ok=True)
    downloaded = []

    for number in product["candidate_numbers"]:
        if number < 1 or number > len(matches):
            continue
        item = matches[number - 1]
        image_url = item.get("image") or item.get("thumbnail")
        if not image_url:
            continue
        try:
            response = await client.get(
                image_url,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=45,
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";", 1)[0]
            if not content_type.startswith("image/") or len(response.content) < 3000:
                raise ValueError("candidate URL did not return an image")
        except Exception:
            thumbnail = item.get("thumbnail")
            if not thumbnail or thumbnail == image_url:
                continue
            response = await client.get(thumbnail, follow_redirects=True, timeout=45)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";", 1)[0]

        extension = {"image/png": ".png", "image/webp": ".webp"}.get(content_type, ".jpg")
        path = target / f"candidate-{number:02d}{extension}"
        path.write_bytes(response.content)
        downloaded.append(
            {
                "number": number,
                "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                "title": item.get("title"),
                "source": item.get("source"),
                "page_url": item.get("link"),
                "image_url": image_url,
            }
        )
    return downloaded


async def ask_model(
    client: httpx.AsyncClient,
    key: str,
    model: str,
    product: dict,
    candidates: list[dict],
    previous: dict | None = None,
) -> dict:
    candidate_text = "\n".join(
        f"{index + 2}. result {item['number']}: {item['title']} | {item['source']} | {item['page_url']}"
        for index, item in enumerate(candidates)
    )
    previous_text = ""
    if previous:
        previous_text = (
            "\nGemini уже сделал предварительную проверку. Проверь её независимо и исправь ошибки:\n"
            + json.dumps(previous, ensure_ascii=False)
        )
    prompt = f"""Изображение 1 — исходная фотография товара. Бренд из подписи владельца: {product['brand']}.
Остальные изображения — результаты Google Lens/SerpApi:
{candidate_text}

Сравнивай именно конструкцию товара: силуэт, узор вязки или панели, воротник, застёжку, карманы, манжеты, швы и цвет. Совпадение бренда в заголовке не означает совпадение модели. Выбери до 4 самых полезных изображений. Если точного товара нет, честно напиши, что найдены только аналоги. Не придумывай материал, артикул и состав, которых нет в источниках.{previous_text}

Верни только JSON:
{{
  "selected_result_numbers": [1, 2],
  "match_status_ru": "точное совпадение / вероятное совпадение / только похожие модели",
  "confidence_0_100": 0,
  "product_name_ru": "...",
  "brand_ru": "...",
  "description_ru": "2–3 спокойных предложения для карточки",
  "characteristics": {{
    "цвет": "...",
    "тип": "...",
    "воротник": "...",
    "застёжка": "...",
    "узор_или_фактура": "...",
    "материал": "не подтверждено"
  }},
  "comparison_ru": "какие детали совпали и какие расходятся",
  "uncertainties_ru": ["..."]
}}"""
    content = [{"type": "text", "text": prompt}]
    content.append(
        {"type": "image_url", "image_url": {"url": data_url(INPUT / product["source"])}}
    )
    for item in candidates:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": data_url(ROOT / item["file"])},
            }
        )
    response = await client.post(
        "https://ai.starimg.ru/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "temperature": 0,
            "messages": [{"role": "user", "content": content}],
        },
        timeout=300,
    )
    response.raise_for_status()
    return parse_json(response.json()["choices"][0]["message"]["content"])


async def review_product(client: httpx.AsyncClient, key: str, product: dict) -> dict:
    candidates = await download_candidates(client, product)
    gemini = await ask_model(client, key, "gemini-3.8-flash", product, candidates)
    final = await ask_model(client, key, "gpt-6.1-sol", product, candidates, gemini)
    selected = set(final.get("selected_result_numbers", []))
    return {
        **product,
        "source_file": f"inputs/serpapi-products/{product['source']}",
        "candidates": candidates,
        "gemini": gemini,
        "final": final,
        "selected_candidates": [item for item in candidates if item["number"] in selected],
    }


async def main() -> None:
    key = load_star_key()
    requested = set(sys.argv[1:])
    selected_products = [
        product for product in PRODUCTS if not requested or product["id"] in requested
    ]
    async with httpx.AsyncClient() as client:
        fresh = await asyncio.gather(
            *(review_product(client, key, product) for product in selected_products)
        )
    if requested and OUTPUT.exists():
        previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
        by_id = {item["id"]: item for item in previous}
        by_id.update({item["id"]: item for item in fresh})
        results = [by_id[product["id"]] for product in PRODUCTS]
    else:
        results = fresh
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            [
                {
                    "id": item["id"],
                    "downloaded": len(item["candidates"]),
                    "selected": len(item["selected_candidates"]),
                    "status": item["final"].get("match_status_ru"),
                    "confidence": item["final"].get("confidence_0_100"),
                }
                for item in results
            ],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
