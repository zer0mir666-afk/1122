import asyncio
import base64
import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets" / "ai-lab"
SOURCE_IMAGE = ASSETS / "tg-product-jacket.png"
OUTPUT = ASSETS / "multi-model-hunt-results.json"
DOWNLOAD_ROOT = ASSETS / "model-hunt"
ENV_FILE = Path(r"C:\Users\magom\OneDrive\Рабочий стол\websites\стас бот по фото\.env")

MODELS = [
    ("Gemini 3.8 Flash", "gemini-3.8-flash"),
    ("Gemini 3.7 Flash", "gemini-3.7-flash"),
    ("GPT 5.6 Sol", "gpt-5.6-sol"),
    ("GPT 6 Sol", "gpt-6-sol"),
    ("GPT 6 Astra", "gpt-6-astra"),
    ("GPT 6.1 Sol", "gpt-6.1-sol"),
    ("Grok 4.7", "grok-4.7"),
    ("Claude Sonnet 5.5", "claude-sonnet-5-5"),
]

PROMPT = """Найди в интернете именно товар с прикреплённой фотографии и верни 3–4 фотографии этого же товара в хорошем качестве.

Из Telegram-поста известно: бренд Loro Piana, куртка, материал 100% шерсть, размеры M–3XL. Эти данные считай исходными, но не выдумывай точную модель или артикул.

Используй доступный тебе интернет-поиск. Нужны разные фотографии именно этого товара, а не просто визуально похожие куртки. Для каждой фотографии обязательно укажи настоящую страницу-источник и прямую ссылку на файл изображения. Если интернет-поиска у тебя нет или точный товар не найден — честно укажи это и не придумывай ссылки.

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


def load_key() -> str:
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("STARIMG_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("STARIMG_KEY not found")


def image_data_url() -> str:
    encoded = base64.b64encode(SOURCE_IMAGE.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def parse_json(raw: str) -> dict:
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {"raw_response": raw}


def public_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        if parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}:
            return False
        try:
            return not ipaddress.ip_address(parsed.hostname).is_private
        except ValueError:
            return True
    except Exception:
        return False


async def ask_model(client: httpx.AsyncClient, key: str, label: str, model: str) -> dict:
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": image_data_url()}},
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
        raw = response.json()["choices"][0]["message"]["content"]
        return {"ok": True, "label": label, "model": model, "result": parse_json(raw)}
    except Exception as exc:
        return {"ok": False, "label": label, "model": model, "error": str(exc)}


async def download_photos(client: httpx.AsyncClient, item: dict) -> None:
    result = item.get("result", {})
    photos = result.get("photos", []) if isinstance(result, dict) else []
    slug = re.sub(r"[^a-z0-9]+", "-", item["model"].lower()).strip("-")
    target_dir = DOWNLOAD_ROOT / slug
    target_dir.mkdir(parents=True, exist_ok=True)
    verified = []

    for index, photo in enumerate(photos[:4], start=1):
        url = photo.get("image_url", "") if isinstance(photo, dict) else ""
        record = dict(photo) if isinstance(photo, dict) else {"image_url": url}
        record["downloaded"] = False
        if not public_http_url(url):
            record["verification_error"] = "invalid or non-public URL"
            verified.append(record)
            continue
        try:
            response = await client.get(
                url,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=45,
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";", 1)[0]
            if not content_type.startswith("image/") or len(response.content) < 5000:
                raise ValueError(f"not an image: {content_type or 'unknown'}")
            extension = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
            }.get(content_type, ".img")
            path = target_dir / f"{index}{extension}"
            path.write_bytes(response.content)
            record["downloaded"] = True
            record["local_file"] = str(path.relative_to(ROOT)).replace("\\", "/")
            record["bytes"] = len(response.content)
        except Exception as exc:
            record["verification_error"] = str(exc)
        verified.append(record)

    result["photos"] = verified
    result["verified_downloads"] = sum(1 for photo in verified if photo.get("downloaded"))


async def main() -> None:
    key = load_key()
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(ask_model(client, key, label, model) for label, model in MODELS)
        )
        await asyncio.gather(*(download_photos(client, item) for item in results if item["ok"]))

    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            [
                {
                    "label": item["label"],
                    "ok": item["ok"],
                    "search_available": item.get("result", {}).get("search_available"),
                    "exact_product_found": item.get("result", {}).get("exact_product_found"),
                    "returned_photos": len(item.get("result", {}).get("photos", [])),
                    "verified_downloads": item.get("result", {}).get("verified_downloads", 0),
                }
                for item in results
            ],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
