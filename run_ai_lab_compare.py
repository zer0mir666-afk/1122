import asyncio
import base64
import json
import sys
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets" / "ai-lab"
ENV_FILE = Path(r"C:\Users\magom\OneDrive\Рабочий стол\websites\стас бот по фото\.env")
OUTPUT = ASSETS / "comparison-results.json"
MODELS = [
    ("GPT", "gpt-6-luna"),
    ("Gemini", "gemini-3.1-pro"),
    ("Claude", "claude-opus-5"),
    ("Qwen + GPT", "qwen3.8-max"),
]
FILES = [
    "tg-product-jacket.png",
    "found-jacket-1.jpg",
    "found-jacket-2.jpg",
    "found-jacket-3.jpg",
]


def load_key() -> str:
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("STARIMG_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("STARIMG_KEY not found")


def image_data(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


async def analyze(client: httpx.AsyncClient, key: str, label: str, model: str) -> dict:
    prompt = """Ты независимо анализируешь один товар для интернет-магазина.
Изображение 1 — исходная отдельная фотография товара из Telegram. Изображения 2–4 — фотографии, найденные в интернете поиском по этому товару.

Данные поста Telegram являются авторитетными и не требуют сомнений: бренд Loro Piana, куртка, материал 100% шерсть, размеры M–3XL.
Сравни найденные фотографии с исходником. Выбери порядок всех найденных фотографий от наиболее полезной к наименее полезной. Не выдумывай точный артикул, если его нельзя установить.

Верни только JSON:
{
  "selected_files": ["found-jacket-1.jpg", "found-jacket-2.jpg", "found-jacket-3.jpg"],
  "status_ru": "короткий итог совпадения",
  "product_name_ru": "название товара",
  "description_ru": "2–3 предложения для карточки товара",
  "characteristics": {
    "бренд": "...",
    "цвет": "...",
    "материал": "...",
    "крой": "...",
    "детали": "...",
    "размеры": "..."
  },
  "comment_ru": "что совпало и что не совпало"
}"""
    content = [{"type": "text", "text": prompt}]
    for file_name in FILES:
        content.append({"type": "image_url", "image_url": {"url": image_data(ASSETS / file_name)}})
    payload = {
        "model": model,
        "temperature": 0.15,
        "messages": [{"role": "user", "content": content}],
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
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return {"ok": True, "label": label, "model": model, "result": json.loads(raw)}
    except Exception as exc:
        return {"ok": False, "label": label, "model": model, "error": str(exc)}


async def main() -> None:
    key = load_key()
    requested = set(sys.argv[1:])
    selected = [item for item in MODELS if not requested or item[0] in requested]
    async with httpx.AsyncClient() as client:
        fresh = await asyncio.gather(*(analyze(client, key, *item) for item in selected))
    if requested and OUTPUT.exists():
        by_label = {item["label"]: item for item in json.loads(OUTPUT.read_text(encoding="utf-8"))}
        by_label.update({item["label"]: item for item in fresh})
        results = [by_label[label] for label, _ in MODELS]
    else:
        results = fresh
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps([{"label": item["label"], "ok": item["ok"]} for item in results], ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
