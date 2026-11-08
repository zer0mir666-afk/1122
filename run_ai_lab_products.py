import asyncio
import base64
import json
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets" / "ai-lab"
ENV_FILE = Path(r"C:\Users\magom\OneDrive\Рабочий стол\websites\стас бот по фото\.env")
OUTPUT = ASSETS / "products-analysis.json"
PRODUCTS = [
    {
        "id": "jacket",
        "file": "tg-product-jacket.png",
        "post": "Куртка Loro Piana; 100% шерсть; размеры M-3XL",
    },
    {
        "id": "cardigan",
        "file": "tg-product-cardigan.png",
        "post": "Кардиган Brunello Cucinelli; 100% хлопок; размеры M-3XL",
    },
    {
        "id": "suitcase",
        "file": "tg-product-suitcase.png",
        "post": "Чемодан-ручная кладь Louis Vuitton, графитовый пиксельный принт; колёса 360°, выдвижная ручка",
    },
    {
        "id": "hoodie",
        "file": "tg-product-hoodie.png",
        "post": "Худи Loro Piana; размеры M-3XL",
    },
]


def load_key() -> str:
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("STARIMG_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("STARIMG_KEY not found")


def image_url(file_name: str) -> str:
    encoded = base64.b64encode((ASSETS / file_name).read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


async def analyze(client: httpx.AsyncClient, key: str, product: dict) -> dict:
    prompt = f"""Это отдельная фотография товара из Telegram-поста магазина. Данные владельца считаются верными и не требуют перепроверки: {product['post']}.

Фотография образа отсутствует и не нужна. Проанализируй только сам товар. Определи видимые особенности, возможную официальную модель или наиболее близкую линейку и подготовь запросы для поиска чистых фотографий этого товара в интернете. Не заменяй бренд другим.

Верни только JSON:
{{
  "id": "{product['id']}",
  "post_facts": "точная нормализованная запись данных владельца",
  "product_name_ru": "название карточки",
  "possible_model_ru": "модель/линейка или не установлена",
  "visible_details_ru": ["..."],
  "search_queries": ["ровно 4 конкретных поисковых запроса"],
  "description_ru": "2-3 спокойных предложения для карточки",
  "characteristics": {{"бренд":"...","категория":"...","цвет":"...","материал":"...","крой_или_формат":"...","размеры":"..."}},
  "needs_confirmation": ["только то, чего нет в посте и нельзя увидеть"]
}}"""
    payload = {
        "model": "gpt-6.1-terra",
        "temperature": 0.15,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url(product["file"])}},
        ]}],
    }
    response = await client.post(
        "https://ai.starimg.ru/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json=payload,
        timeout=240,
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(raw)


async def main() -> None:
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(analyze(client, load_key(), product) for product in PRODUCTS))
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps([item["id"] for item in results], ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
