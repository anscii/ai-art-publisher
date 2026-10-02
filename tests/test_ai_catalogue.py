import pytest

from app.services.ai.catalogue import (
    PROVIDER_DEFAULT_MODELS,
    PROVIDER_MODEL_PRICING,
    PROVIDER_MODELS,
    calc_cost,
)


@pytest.mark.parametrize(
    "model,inp,out",
    [
        ("claude-opus-5-5", 4.00, 20.00),
        ("claude-sonnet-5-5", 2.00, 10.00),
        ("gpt-6-astra", 10.00, 50.00),
        ("gpt-6-luna", 0.10, 0.50),
        ("gemini-3.8-flash", 0.75, 3.75),
        ("deepseek-flash", 0.30, 1.20),
        ("deepseek-v4-pro", 1.32, 3.96),
    ],
)
def test_pricing(model, inp, out):
    assert PROVIDER_MODEL_PRICING[model] == (inp, out)


def test_every_listed_model_has_pricing():
    for models in PROVIDER_MODELS.values():
        for m in models:
            assert m["id"] in PROVIDER_MODEL_PRICING, m["id"]


def test_every_default_model_is_listed():
    for provider, default in PROVIDER_DEFAULT_MODELS.items():
        ids = [m["id"] for m in PROVIDER_MODELS[provider]]
        assert default in ids, (provider, default)


def test_calc_cost_gpt6_astra():
    assert calc_cost("gpt-6-astra", 1_000_000, 1_000_000) == 60.00


def test_calc_cost_unknown_model_returns_zero():
    assert calc_cost("unknown-model", 1_000_000, 1_000_000) == 0.0


def test_legacy_deepseek_id_still_priced():
    assert calc_cost("deepseek-v4-flash", 1_000_000, 1_000_000) == pytest.approx(1.50)
