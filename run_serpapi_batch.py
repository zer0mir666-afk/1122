import argparse
import json
import os
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "inputs" / "serpapi-products"
DEFAULT_OUTPUT = ROOT / "assets" / "serpapi-lab"
ENV_FILES = [
    ROOT / ".env",
    ROOT / ".env.local",
    Path(r"C:\Users\magom\OneDrive\Рабочий стол\websites\стас бот по фото\.env"),
]
IMAGE_SUFFIXES = {".jpg", ".jpeg"}
QUERY_BY_STEM = {
    "03-loro-piana-hoodie": "Loro Piana men's grey zip-up hoodie",
    "04-loro-piana-jacket": "Loro Piana men's light beige zip jacket shirt collar",
}


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

    raise RuntimeError("SERPAPI_KEY not found")


def search_image(client: httpx.Client, key: str, image_path: Path) -> dict:
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    with image_path.open("rb") as image_file:
        upload = client.post(
            "https://serpapi.com/image",
            data={"api_key": key},
            files={"image": (image_path.name, image_file, mime)},
        )
    upload.raise_for_status()
    upload_data = upload.json()
    if upload_data.get("error"):
        raise RuntimeError(upload_data["error"])

    params = {
        "engine": "google_lens",
        "image_id": upload_data["image_id"],
        "type": "visual_matches",
        "hl": "en",
        "country": "us",
        "auto_crop": "false",
        "api_key": key,
    }
    query = QUERY_BY_STEM.get(image_path.stem)
    if query:
        params["q"] = query
    search = client.get(
        "https://serpapi.com/search",
        params=params,
    )
    search.raise_for_status()
    result = search.json()
    if result.get("error"):
        raise RuntimeError(result["error"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--only", nargs="*", default=[])
    args = parser.parse_args()

    images = sorted(
        path for path in args.input.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES
    )
    if args.only:
        selected = set(args.only)
        images = [path for path in images if path.stem in selected]
    if not images:
        raise RuntimeError(f"No images found in {args.input}")

    args.output.mkdir(parents=True, exist_ok=True)
    key = load_key()
    summary = []
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        for image_path in images:
            result = search_image(client, key, image_path)
            output_path = args.output / f"{image_path.stem}.json"
            output_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            summary.append(
                {
                    "source": image_path.name,
                    "result": output_path.name,
                    "status": result.get("search_metadata", {}).get("status"),
                    "visual_matches": len(result.get("visual_matches", [])),
                    "exact_matches": len(result.get("exact_matches", [])),
                }
            )
            print(json.dumps(summary[-1], ensure_ascii=False))

    (args.output / "index.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
