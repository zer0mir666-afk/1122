import asyncio
import base64
import json
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets" / "ai-lab"
ENV_FILE = Path(r"C:\Users\magom\OneDrive\Рабочий стол\websites\стас бот по фото\.env")
OUTPUT = ASSETS / "search-queries.json"
SOURCE = ASSETS / "tg-product-jacket.png"
MODELS = [
    ("GPT", "gpt-6-luna"),
    ("Gemini", "gemini-3.1-pro"),
    ("Claude", "claude-opus-5"),
    ("Qwen", "qwen3.8-max"),
]


def load_key() -> str:
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("STARIMG_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("STARIMG_KEY not found")


def image_data(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


async def inspect(client: httpx.AsyncClient, key: str, label: str, model: str) -> dict:
    prompt = """Проанализируй отдельную фотографию товара из Telegram для точного поиска в интернете.
Данные подписи авторитетны: Loro Piana, куртка, 100% шерсть, размеры M–3XL.
Не ищи просто похожую светлую куртку. Зафиксируй конструктивные признаки, которые обязательно должны совпасть: воротник, застёжка, карманы, манжеты, низ и швы. Составь один максимально точный поисковый запрос для поиска фотографий именно этой модели.

Верни только JSON:
{
  "query": "поисковый запрос на английском",
  "visible_product_ru": "что видно на исходнике",
  "must_match_ru": ["обязательный признак"],
  "reject_if_ru": ["признак, при котором кандидат надо отклонить"]
}"""
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_data(SOURCE)}},
    ]
    response = await client.post(
        "https://ai.starimg.ru/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "temperature": 0.1, "messages": [{"role": "user", "content": content}]},
        timeout=300,
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return {"label": label, "model": model, "result": json.loads(raw)}


async def main() -> None:
    key = load_key()
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(inspect(client, key, *item) for item in MODELS), return_exceptions=True)
    clean = []
    for model_info, result in zip(MODELS, results):
        if isinstance(result, Exception):
            clean.append({"label": model_info[0], "model": model_info[1], "error": str(result)})
        else:
            clean.append(result)
    OUTPUT.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps([{"label": item["label"], "ok": "result" in item} for item in clean], ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
