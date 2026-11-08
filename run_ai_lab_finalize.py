import asyncio
import base64
import json
import sys
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets" / "ai-lab"
ENV_FILE = Path(r"C:\Users\magom\OneDrive\Рабочий стол\websites\стас бот по фото\.env")
ANALYSIS = json.loads((ASSETS / "analysis.json").read_text(encoding="utf-8"))
OUTPUT = ASSETS / "final-results.json"
CANDIDATES = [
    "maurin-front.jpg",
    "maurin-model.jpg",
    "blackrock.jpg",
    "gift-kings-1.jpg",
    "gift-kings-2.jpg",
    "maurin-official.jpg",
    "wool-blend.jpg",
    "breia.jpg",
    "pray-shirt.jpg",
]
PIPELINES = [
    ("GPT", "gpt-6.1-terra", "gpt-6.1-sol"),
    ("Gemini", "gemini-3.1-pro", "gemini-3.8-flash"),
    ("Claude", "claude-opus-5", "claude-sonnet-5"),
    ("Qwen + GPT", "qwen3.8-max", "gpt-6-luna"),
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


async def finalize(client: httpx.AsyncClient, key: str, label: str, analyst: str, finalizer: str) -> dict:
    first = next(item["result"] for item in ANALYSIS if item["model"] == analyst)
    numbered = "\n".join(f"{index + 2}: {name}" for index, name in enumerate(CANDIDATES))
    prompt = f"""Ты — второй этап независимого конвейера {label}. Первая модель ({analyst}) проанализировала исходник из Telegram и дала такой результат:
{json.dumps(first, ensure_ascii=False)}

Изображение 1 — исходник из Telegram. Изображения 2–{len(CANDIDATES) + 1} — реальные фотографии, найденные в интернете по запросам первой модели:
{numbered}

Сопоставь детали одежды покадрово. Не называй точную модель установленной, если конструкция не совпадает. Выбери не больше 5 наиболее полезных найденных фото; близкие ракурсы одной модели можно сохранить. Описание должно быть спокойным и одинаково пригодным для карточки магазина. Факты из подписи Telegram помечай отдельно от подтвержденных веб-источниками.

Верни ТОЛЬКО JSON без markdown:
{{
  "pipeline": "{label}: {analyst} → {finalizer}",
  "selected_files": ["имена файлов из списка"],
  "match_status_ru": "точное совпадение / вероятная модель / только близкие аналоги",
  "product_name_ru": "...",
  "brand_ru": "...",
  "category_ru": "...",
  "confidence_0_100": 0,
  "why_selected_ru": "...",
  "description_ru": "2-3 предложения без рекламной воды",
  "characteristics": {{
    "цвет": "...",
    "материал": "...",
    "крой": "...",
    "воротник": "...",
    "застежка": "...",
    "размеры_из_поста": "M-3XL"
  }},
  "uncertainties_ru": ["..."]
}}"""
    content = [{"type": "text", "text": prompt}]
    for file_name in ["telegram-loro-piana-source.png", *CANDIDATES]:
        content.append({"type": "image_url", "image_url": {"url": image_data(ASSETS / file_name)}})
    payload = {"model": finalizer, "temperature": 0.15, "messages": [{"role": "user", "content": content}]}
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
        return {"ok": True, "label": label, "analyst": analyst, "finalizer": finalizer, "result": json.loads(raw)}
    except Exception as exc:
        return {"ok": False, "label": label, "analyst": analyst, "finalizer": finalizer, "error": str(exc)}


async def main() -> None:
    key = load_key()
    requested = set(sys.argv[1:])
    selected = [pipeline for pipeline in PIPELINES if not requested or pipeline[0] in requested]
    async with httpx.AsyncClient() as client:
        fresh = await asyncio.gather(*(finalize(client, key, *pipeline) for pipeline in selected))
    if requested and OUTPUT.exists():
        previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
        by_label = {item["label"]: item for item in previous}
        by_label.update({item["label"]: item for item in fresh})
        results = [by_label[label] for label, _, _ in PIPELINES]
    else:
        results = fresh
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps([{"label": item["label"], "ok": item["ok"], "error": item.get("error")} for item in results], ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
