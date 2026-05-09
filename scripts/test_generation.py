"""Local CLI for testing AI generation without running the full app."""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.routers.generate import _get_api_key, get_provider  # noqa: E402


class _FakeSettings:
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    google_api_key = os.environ.get("GOOGLE_API_KEY", "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test AI variant generation")
    parser.add_argument("--hint", required=True, help="Artwork description hint")
    parser.add_argument(
        "--provider",
        default=os.environ.get("DEFAULT_PROVIDER", "anthropic"),
        help="AI provider (anthropic/openai/google)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("DEFAULT_MODEL", "claude-haiku-4-5"),
        help="Model name",
    )
    args = parser.parse_args()

    api_key = _get_api_key(_FakeSettings(), args.provider)
    if not api_key:
        print(f"Error: no API key for provider '{args.provider}' (set env var)", file=sys.stderr)
        sys.exit(1)

    print(f"Provider: {args.provider}  Model: {args.model}")
    print(f"Hint: {args.hint}\n")

    provider = get_provider(args.provider, api_key)
    variants = provider.generate_variants(images_b64=[], model=args.model, hint=args.hint)

    for i, v in enumerate(variants, 1):
        print(f"── Variant {i} ─────────────────────────────")
        print(f"Title        : {v.title}")
        print(f"Description  : {v.description_en}")
        print(f"Description RU: {v.description_ru}")
        print(f"Instagram tags: {' '.join(v.tags_instagram)}")
        print(f"Telegram tags : {' '.join(v.tags_telegram)}")
        print()


if __name__ == "__main__":
    main()
