import asyncio
import base64
import json
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets" / "ai-lab"
SOURCE_IMAGE = ASSETS / "tg-product-jacket.png"
OUTPUT = ASSETS / "direct-search-results.json"
ENV_FILE = Path(r"C:\Users\magom\OneDrive\Рабочий стол\websites\стас бот по фото\.env")

MODELS = [
    ("GPT", "gpt-6.1-terra"),
    ("Gemini", "gemini-3.1-pro"),
    ("Claude", "claude-opus-5-5"),
    ("Grok", "grok-4.7"),
]


def load_key() -> str:
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("STARIMG_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("STARIMG_KEY not found")


def source_data_url() -> str:
    encoded = base64.b64encode(SOURCE_IMAGE.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


PROMPT = """Найди в интернете именно товар с прикрепленной фотографии.

Это отдельная фотография товара из Telegram-поста. Не ограничивайся визуальным описанием и не предлагай просто похожие вещи. Используй доступный тебе интернет-поиск, чтобы установить конкретный бренд и модель, а затем найди 3–4 качественные фотографии именно этого товара на сайтах магазинов, бренда, маркетплейсов или архивов продаж.

Для каждого найденного результата обязательно укажи настоящую проверяемую ссылку на страницу-источник и прямую ссылку на фотографию, если она доступна. Не выдумывай ссылки, артикул, материал или бренд. Если у тебя нет доступа к интернет-поиску либо точный товар установить не удалось, прямо так и напиши.

Верни только JSON:
{
  "search_available": true,
  "exact_product_found": false,
  "brand": null,
  "model": null,
  "product_name_ru": null,
  "description_ru": null,
  "characteristics": {},
  "photos": [
    {"page_url": "https://...", "image_url": "https://...", "match_reason": "..."}
  ],
  "confidence_percent": 0,
  "comment_ru": ""
}
"""


async def run_model(client: httpx.AsyncClient, key: str, label: str, model: str) -> dict:
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": source_data_url()}},
                ],
            }
        ],
    }
    try:
        response = await client.post(
            "https://ai.starimg.ru/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
            timeout=300,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"].strip()
        clean = raw
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        try:
            result = json.loads(clean)
        except json.JSONDecodeError:
            result = {"raw_response": raw}
        return {"ok": True, "label": label, "model": model, "result": result}
    except Exception as exc:
        return {"ok": False, "label": label, "model": model, "error": str(exc)}


async def main() -> None:
    key = load_key()
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(run_model(client, key, label, model) for label, model in MODELS)
        )
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = []
    for item in results:
        result = item.get("result", {})
        summary.append(
            {
                "label": item["label"],
                "ok": item["ok"],
                "search_available": result.get("search_available"),
                "exact_product_found": result.get("exact_product_found"),
                "photos": len(result.get("photos", [])),
            }
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
