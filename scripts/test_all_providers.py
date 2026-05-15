"""Run AI generation across all providers and models, write results to HTML report.

Usage:
    .venv/bin/python scripts/test_all_providers.py --hint "a fox spirit in winter forest"
    .venv/bin/python scripts/test_all_providers.py --hint "a fox spirit" --hint "a sea dragon"
    .venv/bin/python scripts/test_all_providers.py --hint "a fox" --providers anthropic openai
    .venv/bin/python scripts/test_all_providers.py --hint "a fox" --providers anthropic --models claude-sonnet-4-6
    .venv/bin/python scripts/test_all_providers.py --hint "a fox" --out report.html
"""

import argparse
import html
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.routers.generate import _get_api_key, get_provider  # noqa: E402
from app.services.ai.catalogue import PROVIDER_MODELS  # noqa: E402
from scripts._utils import FakeSettings  # noqa: E402

_PROVIDER_COLORS = {
    "anthropic": "#d97706",
    "openai": "#2563eb",
    "google": "#16a34a",
}

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0f0f1a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; padding: 24px; }
h1 { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
.meta { color: #94a3b8; font-size: 13px; margin-bottom: 32px; }
.hint-section { margin-bottom: 40px; }
.hint-label { font-size: 13px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: .06em; border-bottom: 1px solid #1e293b; padding-bottom: 8px; margin-bottom: 16px; }
.hint-label span { color: #f1f5f9; font-weight: 700; font-style: italic; }
.cards { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }
.card { background: #16213e; border-radius: 10px; padding: 0; width: 340px; flex-shrink: 0; overflow: hidden; border: 1px solid #1e2d47; }
.card.error { border-left: 4px solid #e74c3c; }
.card-header { padding: 10px 14px; background: #0f172a; display: flex; align-items: center; gap: 8px; }
.badge { font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 4px; color: #fff; }
.model-name { font-size: 12px; color: #94a3b8; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.time-chip { font-size: 11px; color: #64748b; white-space: nowrap; }
.variants { padding: 10px 14px 14px; display: flex; flex-direction: column; gap: 14px; }
.variant { border-top: 1px solid #1e293b; padding-top: 12px; }
.variant:first-child { border-top: none; padding-top: 0; }
.var-num { font-size: 10px; color: #475569; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 6px; }
.title { font-weight: 600; font-size: 14px; color: #f1f5f9; margin-bottom: 6px; }
.field-label { font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: .06em; margin-top: 8px; margin-bottom: 3px; }
.field-value { color: #cbd5e1; line-height: 1.5; font-size: 13px; }
.tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 3px; }
.tag { background: #1e2d47; color: #7dd3fc; font-size: 11px; padding: 1px 6px; border-radius: 4px; font-family: monospace; }
.error-msg { padding: 14px; color: #fca5a5; font-size: 13px; line-height: 1.5; word-break: break-word; }
"""


def _e(text: str) -> str:
    return html.escape(str(text))


def _tags_html(tags_str: str) -> str:
    if not tags_str:
        return ""
    tags = tags_str.split()
    return "".join(f'<span class="tag">{_e(t)}</span>' for t in tags)


def _write_html(path: str, rows: list[dict], run_info: dict) -> None:
    # group: hint → (provider, model) → [row, ...]
    groups: dict[str, dict[tuple, list]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        groups[row["hint"]][(row["provider"], row["model"])].append(row)

    parts = [
        "<!doctype html><html lang='en'><head>",
        "<meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>AI Generation Results — {_e(run_info['generated_at'])}</title>",
        f"<style>{_CSS}</style>",
        "</head><body>",
        "<h1>AI Generation Results</h1>",
        f"<p class='meta'>{_e(run_info['generated_at'])} &nbsp;·&nbsp; "
        f"{run_info['total_combinations']} combination(s) &nbsp;·&nbsp; "
        f"{run_info['elapsed_total']:.1f}s total"
        + (
            f" &nbsp;·&nbsp; ${run_info['total_cost_usd']:.4f} total"
            if run_info.get("total_cost_usd")
            else ""
        )
        + "</p>",
    ]

    for hint in run_info["hints"]:
        model_groups = groups.get(hint, {})
        parts.append("<div class='hint-section'>")
        parts.append(f"<div class='hint-label'>Hint: <span>{_e(hint)}</span></div>")
        parts.append("<div class='cards'>")

        for (provider, model), model_rows in model_groups.items():
            color = _PROVIDER_COLORS.get(provider, "#6366f1")
            first = model_rows[0]
            is_error = bool(first.get("error"))
            card_cls = "card error" if is_error else "card"
            time_val = first.get("time_s", "")
            cost_val = first.get("cost_usd") or 0
            perf_label = (f"{time_val}s" if time_val else "") + (
                f" · ${cost_val:.4f}" if cost_val else ""
            )

            parts.append(f"<div class='{card_cls}'>")
            parts.append(
                f"<div class='card-header'>"
                f"<span class='badge' style='background:{color}'>{_e(provider)}</span>"
                f"<span class='model-name'>{_e(model)}</span>"
                f"<span class='time-chip'>{_e(perf_label)}</span>"
                f"</div>"
            )

            if is_error:
                parts.append(f"<div class='error-msg'>{_e(first['error'])}</div>")
            else:
                parts.append("<div class='variants'>")
                for i, row in enumerate(model_rows, 1):
                    parts.append("<div class='variant'>")
                    parts.append(f"<div class='var-num'>Variant {i}</div>")
                    parts.append(f"<div class='title'>{_e(row['title'])}</div>")
                    parts.append("<div class='field-label'>EN</div>")
                    parts.append(f"<div class='field-value'>{_e(row['description_en'])}</div>")
                    parts.append("<div class='field-label'>RU</div>")
                    parts.append(f"<div class='field-value'>{_e(row['description_ru'])}</div>")
                    if row.get("tags_instagram"):
                        parts.append("<div class='field-label'>Instagram</div>")
                        parts.append(f"<div class='tags'>{_tags_html(row['tags_instagram'])}</div>")
                    if row.get("tags_telegram"):
                        parts.append("<div class='field-label'>Telegram</div>")
                        parts.append(f"<div class='tags'>{_tags_html(row['tags_telegram'])}</div>")
                    parts.append("</div>")
                parts.append("</div>")

            parts.append("</div>")

        parts.append("</div></div>")

    parts.append("</body></html>")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test all AI providers and models, save HTML report"
    )
    parser.add_argument(
        "--hint",
        dest="hints",
        action="append",
        required=True,
        metavar="HINT",
        help="Hint text (repeat for multiple hints)",
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=list(PROVIDER_MODELS),
        help="Limit to specific providers (default: all with API keys)",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        help="Limit to specific model IDs (default: all models for selected providers)",
    )
    parser.add_argument(
        "--out", default=None, help="Output HTML path (default: results_YYYYMMDD_HHMMSS.html)"
    )
    args = parser.parse_args()

    out_path = args.out or f"scripts/results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    settings = FakeSettings()

    work: list[tuple[str, str, str]] = []
    for provider, models in PROVIDER_MODELS.items():
        if args.providers and provider not in args.providers:
            continue
        key = _get_api_key(settings, provider)
        if not key:
            print(
                f"[skip] {provider}: no API key (set {provider.upper()}_API_KEY)", file=sys.stderr
            )
            continue
        for m in models:
            if args.models and m["id"] not in args.models:
                continue
            work.append((provider, m["id"], key))

    if not work:
        print("Nothing to run. Check API keys or --providers/--models filters.", file=sys.stderr)
        sys.exit(1)

    total = len(work) * len(args.hints)
    print(f"Running {total} combination(s): {len(work)} model(s) × {len(args.hints)} hint(s)")
    print(f"Output: {out_path}\n")

    rows: list[dict] = []
    t_start = time.perf_counter()

    for provider, model_id, key in work:
        try:
            p = get_provider(provider, key)
        except Exception as e:
            for hint in args.hints:
                rows.append(
                    {
                        "provider": provider,
                        "model": model_id,
                        "hint": hint,
                        "time_s": "",
                        "title": "",
                        "description_en": "",
                        "description_ru": "",
                        "tags_instagram": "",
                        "tags_telegram": "",
                        "error": str(e),
                    }
                )
            continue

        for hint in args.hints:
            print(f"  {provider}/{model_id}  hint={hint!r} ...", end=" ", flush=True)
            t0 = time.perf_counter()
            try:
                variants = p.generate_variants(images_b64=[], model=model_id, hint=hint)
                elapsed = round(time.perf_counter() - t0, 2)
                print(f"{elapsed}s")
                cost_str = (
                    f"${variants[0].cost_usd:.4f}" if variants and variants[0].cost_usd else ""
                )
                if cost_str:
                    print(f" cost: {cost_str}", end=" ")
                for v in variants:
                    rows.append(
                        {
                            "provider": provider,
                            "model": model_id,
                            "hint": hint,
                            "time_s": elapsed,
                            "cost_usd": v.cost_usd,
                            "title": v.title,
                            "description_en": v.description_en,
                            "description_ru": v.description_ru,
                            "tags_instagram": " ".join(v.tags_instagram),
                            "tags_telegram": " ".join(v.tags_telegram),
                            "error": "",
                        }
                    )
            except Exception as e:
                elapsed = round(time.perf_counter() - t0, 2)
                print(f"ERROR ({elapsed}s)")
                print(e)
                rows.append(
                    {
                        "provider": provider,
                        "model": model_id,
                        "hint": hint,
                        "time_s": elapsed,
                        "title": "",
                        "description_en": "",
                        "description_ru": "",
                        "tags_instagram": "",
                        "tags_telegram": "",
                        "error": str(e),
                    }
                )

    total_cost = sum(r.get("cost_usd") or 0 for r in rows if not r.get("error"))
    _write_html(
        out_path,
        rows,
        {
            "hints": args.hints,
            "total_combinations": total,
            "elapsed_total": time.perf_counter() - t_start,
            "total_cost_usd": total_cost,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    print(f"\nDone. Report saved to {out_path}")


if __name__ == "__main__":
    main()
