import asyncio
import base64
import json
import os
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "assets" / "ai-lab" / "telegram-loro-piana-source.png"
OUTPUT = ROOT / "assets" / "ai-lab" / "analysis.json"
ENV_FILE = Path(r"C:\Users\magom\OneDrive\Рабочий стол\websites\стас бот по фото\.env")
MODELS = ["gpt-6.1-terra", "gemini-3.1-pro", "claude-opus-5", "qwen3.8-max"]


def load_key() -> str:
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("STARIMG_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("STARIMG_KEY not found")


PROMPT = """Ты — независимый эксперт по поиску одежды по фотографии. Проанализируй одну и ту же исходную фотографию из Telegram-канала магазина. Подпись автора: «Куртка Loro Piana. 100% шерсть. Size: M-3XL».

Ничего не выдумывай и отделяй то, что видно, от предположений. Твоя задача — подготовить собственный план интернет-поиска точного товара и карточку товара.

Верни ТОЛЬКО валидный JSON без markdown:
{
  "model_name": "...",
  "product_type_ru": "...",
  "probable_brand": "...",
  "probable_line_or_model": "... или не установлено",
  "confidence_0_100": 0,
  "visible_evidence_ru": ["..."],
  "uncertainties_ru": ["..."],
  "search_queries": ["ровно 6 конкретных поисковых запросов, пригодных для поиска фото товара"],
  "required_views": ["какие ракурсы нужны"],
  "description_draft_ru": "2-3 предложения в спокойном стиле премиального магазина, без неподтвержденных фактов",
  "characteristics_draft": {
    "бренд": "...",
    "категория": "...",
    "цвет": "...",
    "материал": "...",
    "посадка": "...",
    "размеры_из_поста": "M-3XL"
  }
}"""


async def analyze(client: httpx.AsyncClient, key: str, model: str, image_url: str) -> dict:
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }],
    }
    try:
        response = await client.post(
            "https://ai.starimg.ru/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
            timeout=240,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return {"model": model, "ok": True, "result": json.loads(content)}
    except Exception as exc:
        return {"model": model, "ok": False, "error": str(exc)}


async def main() -> None:
    key = load_key()
    encoded = base64.b64encode(SOURCE.read_bytes()).decode("ascii")
    image_url = f"data:image/png;base64,{encoded}"
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(analyze(client, key, model, image_url) for model in MODELS))
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps([{"model": item["model"], "ok": item["ok"], "error": item.get("error")} for item in results], ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
