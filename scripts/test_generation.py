"""Local CLI for testing AI generation without running the full app."""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.routers.generate import _get_api_key, get_provider  # noqa: E402
from app.services.ai.catalogue import PROVIDER_DEFAULT_MODELS  # noqa: E402
from scripts._utils import FakeSettings  # noqa: E402


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
        default=None,
        help="Model name (default: provider's catalogue default)",
    )
    args = parser.parse_args()

    model = args.model or PROVIDER_DEFAULT_MODELS.get(args.provider, "")
    api_key = _get_api_key(FakeSettings(), args.provider)
    if not api_key:
        print(f"Error: no API key for provider '{args.provider}' (set env var)", file=sys.stderr)
        sys.exit(1)

    print(f"Provider: {args.provider}  Model: {model}")
    print(f"Hint: {args.hint}\n")

    provider = get_provider(args.provider, api_key)
    variants = provider.generate_variants(images_b64=[], model=model, hint=args.hint)

    if variants:
        v0 = variants[0]
        cost_line = (
            f"Cost: ${v0.cost_usd:.6f}  ({v0.input_tokens} in + {v0.output_tokens} out tokens)"
        )
        print(cost_line)
        print()

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
