from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "index.html"


def _index_html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def test_frontend_uses_shared_model_tier_helper():
    html = _index_html()

    assert "function modelTierBuckets(models, freeModels)" in html
    assert "function appendModelTierOptions(select, models, freeModels)" in html
    assert "function setVisibleModelSelection(select, preferredModel, fallbackModel)" in html
    assert "freeModelsSet.has(model)" in html


def test_frontend_lists_openrouter_as_system_provider():
    html = _index_html()

    assert "{ id: 'openrouter', name: 'OpenRouter', system: true }" in html
    assert "openrouter: 'OpenRouter'" in html
    assert "provider === 'openrouter'" in html


def test_frontend_does_not_select_hidden_paid_defaults():
    html = _index_html()

    assert "setVisibleModelSelection(modelSelect, data.default, data.models && data.models[0]);" in html
    assert "setVisibleModelSelection(modelSel, data.default, data.models && data.models[0]);" in html


def test_override_model_dropdown_uses_current_override_variable():
    html = _index_html()
    start = html.index("async function onOverrideProviderChange(feature)")
    end = html.index("function onOverrideModelChange(feature)", start)
    function_body = html[start:end]

    assert "const currentOv = _featureOverridesState[feature];" in function_body
    assert "setVisibleModelSelection(modelSel, currentOv.model" in function_body
    assert "if (current && current.model)" not in function_body
