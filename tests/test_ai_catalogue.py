from app.services.ai.catalogue import (
    PROVIDER_DEFAULT_MODELS,
    PROVIDER_MODEL_PRICING,
    PROVIDER_MODELS,
    calc_cost,
)


def test_gpt55_in_pricing():
    assert "gpt-5.5" in PROVIDER_MODEL_PRICING
    inp, out = PROVIDER_MODEL_PRICING["gpt-5.5"]
    assert inp == 5.00
    assert out == 30.00


def test_gpt55_in_openai_model_list():
    ids = [m["id"] for m in PROVIDER_MODELS["openai"]]
    assert "gpt-5.5" in ids


def test_calc_cost_gpt55():
    cost = calc_cost("gpt-5.5", 1_000_000, 1_000_000)
    assert cost == 35.00


def test_calc_cost_unknown_model_returns_zero():
    assert calc_cost("unknown-model", 1_000_000, 1_000_000) == 0.0


def test_deepseek_v4_flash_in_pricing():
    assert "deepseek-v4-flash" in PROVIDER_MODEL_PRICING
    inp, out = PROVIDER_MODEL_PRICING["deepseek-v4-flash"]
    assert inp == 0.14
    assert out == 0.28


def test_deepseek_in_model_list():
    ids = [m["id"] for m in PROVIDER_MODELS["deepseek"]]
    assert "deepseek-v4-flash" in ids


def test_deepseek_default_model():
    assert PROVIDER_DEFAULT_MODELS["deepseek"] == "deepseek-v4-flash"


def test_calc_cost_deepseek_v4_flash():
    cost = calc_cost("deepseek-v4-flash", 1_000_000, 1_000_000)
    assert abs(cost - 0.42) < 1e-9
