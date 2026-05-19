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
    parser = argparse.ArgumentParser(description="Test AI variant generation (2-step)")
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
    parser.add_argument(
        "--variants",
        type=int,
        default=1,
        help="Number of draft variants to generate (default: 1)",
    )
    parser.add_argument(
        "--language",
        default="en",
        choices=["en", "ru"],
        help="Language for step 1 drafts (default: en)",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=1,
        choices=[1, 2],
        help="1=generate drafts, 2=generate drafts then expand first one (default: 1)",
    )
    args = parser.parse_args()

    model = args.model or PROVIDER_DEFAULT_MODELS.get(args.provider, "")
    api_key = _get_api_key(FakeSettings(), args.provider)
    if not api_key:
        print(f"Error: no API key for provider '{args.provider}' (set env var)", file=sys.stderr)
        sys.exit(1)

    print(f"Provider: {args.provider}  Model: {model}  Language: {args.language}")
    print(f"Hint: {args.hint}\n")

    provider = get_provider(args.provider, api_key)

    print("── Step 1: Generate drafts ──────────────────────────────")
    drafts = provider.generate_variants(
        images_b64=[],
        model=model,
        hint=args.hint,
        num_variants=args.variants,
        language=args.language,
    )

    if drafts:
        v0 = drafts[0]
        cost_line = (
            f"Cost: ${v0.cost_usd:.6f}  ({v0.input_tokens} in + {v0.output_tokens} out tokens)"
        )
        print(cost_line)
        print()

    for i, v in enumerate(drafts, 1):
        print(f"── Draft {i} ─────────────────────────────")
        if args.language == "ru":
            print(f"Description RU: {v.description_ru}")
        else:
            print(f"Description EN: {v.description_en}")
        print()

    if args.step == 2 and drafts:
        first = drafts[0]
        description = first.description_en if args.language == "en" else first.description_ru
        print("── Step 2: Generate full content ─────────────────────")
        print(f"Expanding from: {description[:80]}...\n")
        expanded = provider.expand_variant(
            description=description, language=args.language, model=model, hint=args.hint
        )
        cost_line = f"Cost: ${expanded.cost_usd:.6f}  ({expanded.input_tokens} in + {expanded.output_tokens} out tokens)"
        print(cost_line)
        print()
        print(f"Title        : {expanded.title}")
        print(f"Title RU     : {expanded.title_ru}")
        print(f"Description EN: {expanded.description_en}")
        print(f"Description RU: {expanded.description_ru}")
        print(f"Instagram tags: {' '.join(expanded.tags_instagram)}")
        print(f"Telegram tags : {' '.join(expanded.tags_telegram)}")
        print(f"Instagram SEO : {expanded.instagram_seo}")
        print(f"Pinterest     : {expanded.pinterest_title}")


if __name__ == "__main__":
    main()
