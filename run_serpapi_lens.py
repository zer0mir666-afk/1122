import json
import os
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets" / "ai-lab"
SOURCE_IMAGE = ASSETS / "tg-product-jacket-serp.jpg"
OUTPUT = ASSETS / "serpapi-lens-results.json"
ENV_FILES = [
    ROOT / ".env",
    ROOT / ".env.local",
    Path(r"C:\Users\magom\OneDrive\Рабочий стол\websites\стас бот по фото\.env"),
]


def load_key() -> str:
    key = os.environ.get("SERPAPI_KEY", "").strip()
    if key:
        return key

    for env_file in ENV_FILES:
        if not env_file.exists():
            continue
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("SERPAPI_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")

    raise RuntimeError(
        "SERPAPI_KEY not found. Add SERPAPI_KEY=... to the existing .env file."
    )


def main() -> None:
    if not SOURCE_IMAGE.exists():
        raise RuntimeError(f"Prepared image not found: {SOURCE_IMAGE}")

    key = load_key()
    with httpx.Client(timeout=120) as client:
        with SOURCE_IMAGE.open("rb") as image_file:
            upload = client.post(
                "https://serpapi.com/image",
                data={"api_key": key},
                files={"image": (SOURCE_IMAGE.name, image_file, "image/jpeg")},
            )
        upload.raise_for_status()
        upload_data = upload.json()
        if upload_data.get("error"):
            raise RuntimeError(upload_data["error"])

        search = client.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_lens",
                "image_id": upload_data["image_id"],
                "type": "all",
                "hl": "en",
                "country": "us",
                "auto_crop": "false",
                "api_key": key,
            },
        )
        search.raise_for_status()
        result = search.json()
        if result.get("error"):
            raise RuntimeError(result["error"])

    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result.get("search_metadata", {}).get("status"),
                "visual_matches": len(result.get("visual_matches", [])),
                "exact_matches": len(result.get("exact_matches", [])),
                "output": str(OUTPUT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
