from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("build_site",ROOT/"build/site/build_site.py");bs=importlib.util.module_from_spec(spec);spec.loader.exec_module(bs)
def html(): return bs.render_all("dof")[Path("tools/dof.html")]
def en_html(): return bs.render_all("en/dof")[Path("en","tools","dof.html")]
def test_dof_page_registered_at_canonical_route():
    assert bs.PAGES["dof"]["output"]==Path("tools/dof.html");assert 'https://www.sidekick-lab.com/tools/dof' in html()
def test_dof_page_has_required_inputs_and_results():
    page=html()
    for value in ['id="dof-sensor"','id="dof-focal"','id="dof-aperture"','id="dof-focus"','id="dof-criterion"','id="dof-results"']:assert value in page
def test_dof_page_has_progressive_disclosures_and_accessibility():
    page=html();assert 'id="dof-curve-disclosure"' in page;assert 'id="dof-assumptions"' in page;assert 'aria-live="polite"' in page;assert page.count("<h1") == 1
def test_dof_page_links_scoped_assets():
    page=html();assert '/assets/css/dof-calculator.css?v=6' in page;assert 'type="module" src="/assets/js/dof/calculator-ui.mjs?v=6"' in page
def test_dof_page_separates_url_warning_and_form_validation():
    page=html();assert 'id="dof-url-warning" role="status"' in page;assert 'id="dof-form-error" role="alert"' in page;assert 'id="dof-sensor-error"' in page
def test_dof_page_explains_criterion_and_shows_effective_value():
    page=html();assert 'id="dof-criterion-explanation"' in page;assert 'id="dof-effective-criterion" aria-live="polite"' in page;assert '絶対的な視覚限界ではありません' in page
def test_dof_page_supports_standard_and_arbitrary_f_numbers():
    page=html();assert 'step="any"' in page;assert 'data-fnumber="1.4"' in page;assert 'data-fnumber="32"' in page;assert '任意の正の値を入力できます' in page
def test_dof_page_explains_curve_range_and_distance_approximation():
    page=html();assert '緑の基準線より下にある範囲' in page;assert '前側主点からの距離との差を0と近似' in page
def test_dof_curve_script_has_text_and_non_color_range_semantics():
    script=(ROOT/'assets/js/dof/blur-chart.mjs').read_text(encoding='utf-8');assert '計算上のボケ径' in script;assert '許容するボケの基準' in script;assert '被写界深度' in script;assert 'この先も許容範囲' in script
def test_dof_page_has_previous_input_and_result_delta_semantics():
    page=html();assert 'data-comparison-field="fNumber"' in page;assert 'id="dof-previous-aperture"' in page
    for value in ['id="dof-near-delta"','id="dof-focus-result-delta"','id="dof-far-delta"','id="dof-total-delta"','id="dof-front-delta"','id="dof-rear-delta"','id="dof-hyperfocal-delta"']:assert value in page
    assert 'aria-atomic="false"' in page
def test_dof_comparison_controller_preserves_invalid_history_and_auto_calculates():
    script=(ROOT/'assets/js/dof/calculator-ui.mjs').read_text(encoding='utf-8')
    assert 'history=advanceComparison(history,record(value,result))' in script
    assert 'catch(error){showError(error);updateInputComparison();return false;}' in script
    # F-numberプリセットは値更新と同時にその場でcalculate()する（「計算する」ボタンを介さない）
    assert 'button.dataset.fnumber;noteDraftChange();calculate();' in script
    # numeric input/selectはchangeで確定計算し、submitはpreventDefaultのみ（ページ遷移防止の保険）でcalculate()を呼ばない
    assert 'form.addEventListener("submit",e=>{e.preventDefault();});' in script
    assert 'toggleOptional();noteDraftChange();const ok=calculate();' in script
    # 同一値での再確定はhistoryを二重advanceしない（Enterとchangeの重複発火・同じpresetの連打を安全にする）
    assert 'changedInputKeys(history.current.inputSnapshot,inputSnapshot()).length===0' in script
def test_dof_page_has_no_explicit_calculate_button():
    page=html()
    assert 'dof-button' not in page
    assert '計算する' not in page
    assert 'type="submit"' not in page
    css=(ROOT/'assets/css/dof-calculator.css').read_text(encoding='utf-8')
    assert 'dof-button' not in css
def test_dof_sensor_explainer_dialog_present_and_worded_neutrally():
    page=html()
    assert '<dialog class="dof-explainer" id="dof-sensor-explainer" aria-labelledby="dof-sensor-explainer-title">' in page
    assert 'id="dof-sensor-explainer-title">センサーサイズを変更しました</h2>' in page
    assert 'Traditional 30 µm（固定値）' in page
    assert '被写界深度の計算結果は変わりません' in page
    assert 'センサー対角線 ÷ 1500' in page
    assert '<form method="dialog"><button autofocus>OK</button></form>' in page
    # 否定的・エラー的な表現をしないこと（既存仕様の明示的な禁止事項）
    for forbidden in ['計算されていません', 'エラーです', '不適切です']:
        assert forbidden not in page
def test_dof_sensor_explainer_shows_once_per_session_only_for_traditional_criterion():
    script=(ROOT/'assets/js/dof/calculator-ui.mjs').read_text(encoding='utf-8')
    assert 'let sensorExplainerShown=false;' in script
    assert 'function maybeShowSensorExplainer(){if(sensorExplainerShown||$("dof-criterion").value!=="traditional_ff_0030")return;sensorExplainerShown=true;$("dof-sensor-explainer").showModal();}' in script
    # sensor changeでcalculate()が成功した場合だけ判定する（invalid custom sensor等では出さない）
    assert 'const sensorChanged=e.target===$("dof-sensor");' in script
    assert 'if(sensorChanged&&ok)maybeShowSensorExplainer();' in script
    # localStorage/sessionStorage/cookieを使わず、in-memoryのみで保持する
    assert 'localStorage' not in script
    assert 'sessionStorage' not in script
    assert 'document.cookie' not in script
    # ダイアログを閉じたらsensor selectへフォーカスを戻す
    assert '$("dof-sensor-explainer").addEventListener("close",()=>{$("dof-sensor").focus();});' in script


# ---------------------------------------------------------------------------
# 英語版 DOF Calculator（2026-09-11追加、日本語版を正本としたlocalization）
# ---------------------------------------------------------------------------

def test_dof_en_page_registered_at_correct_url_and_lang():
    assert bs.PAGES["en/dof"]["output"]==Path("en","tools","dof.html")
    page=en_html()
    assert '<html lang="en">' in page
    assert 'https://www.sidekick-lab.com/en/tools/dof' in page
def test_dof_en_page_shares_calculation_assets_with_japanese_page():
    """計算ロジック（calculation-core等）を複製せず、同じ共有ファイルを参照すること。"""
    ja,en=html(),en_html()
    for marker in ['/assets/css/dof-calculator.css?v=6','type="module" src="/assets/js/dof/calculator-ui.mjs?v=6"']:
        assert marker in ja;assert marker in en
def test_dof_en_page_has_required_inputs_and_results():
    page=en_html()
    for value in ['id="dof-sensor"','id="dof-focal"','id="dof-aperture"','id="dof-focus"','id="dof-criterion"','id="dof-results"','id="dof-sensor-explainer"']:assert value in page
    assert page.count("<h1") == 1
def test_dof_en_page_translates_labels_and_result_names():
    page=en_html()
    for value in ['Sensor Format','Focal Length','Aperture (f-number)','Focus Distance','Circle of Confusion (CoC) / Criterion','Near Limit','Focus Position','Far Limit','Total DOF','Hyperfocal Distance']:assert value in page
def test_dof_en_page_translates_sensor_explainer_dialog_neutrally():
    page=en_html()
    assert 'id="dof-sensor-explainer-title">Sensor format changed</h2>' in page
    assert 'Traditional 30 µm' in page
    assert "doesn't change" in page
    assert 'Sensor diagonal ÷ 1500' in page
    for forbidden in ['not calculated','this is an error','not appropriate','human visual limit']:
        assert forbidden not in page.lower()
def test_dof_en_page_has_no_leftover_japanese_ui_text():
    """テンプレート側（可視文言）に日本語が紛れ込んでいないことを確認する。
    JS側（calculator-ui.mjs等）は共有ファイルでJA文字列を保持するのが正しい
    設計のため対象外（実行時にLANGで切り替わる、browser reviewで確認）。"""
    page=en_html()
    for leftover in ['センサーサイズ','焦点距離','被写界深度','許容錯乱円','前回','計算結果','ボケの変化を見る']:
        assert leftover not in page, f"未翻訳の日本語文字列が残っている: {leftover}"
def test_dof_ja_en_language_switch_links_are_reciprocal():
    ja,en=html(),en_html()
    assert 'href="/en/tools/dof"' in ja  # lang-banner + EN switch badge
    assert 'href="/tools/dof"' in en    # lang-banner + JA switch badge
    assert '<link rel="alternate" hreflang="ja" href="https://www.sidekick-lab.com/tools/dof">' in ja
    assert '<link rel="alternate" hreflang="en" href="https://www.sidekick-lab.com/en/tools/dof">' in ja
    assert '<link rel="alternate" hreflang="ja" href="https://www.sidekick-lab.com/tools/dof">' in en
    assert '<link rel="alternate" hreflang="en" href="https://www.sidekick-lab.com/en/tools/dof">' in en
def test_dof_ja_page_no_longer_suppresses_lang_banner_and_en_link():
    """英語版が存在するようになったため、JA /tools/dof は他のJA/ENページ対と同じく
    lang-banner・EN switchリンクを表示する（英語版が無かった間の一時Falseを解除）。"""
    page=html()
    assert 'lang-banner' in page
    assert '🇺🇸 EN' in page
def test_dof_en_error_messages_are_english():
    """バリデーションエラー文言はJSが動的に挿入するため（テンプレートの静的HTMLには
    出現しない）、calculator-ui.mjsのUI_STRINGS.en側で英語化されていることを確認する。"""
    script=(ROOT/'assets/js/dof/calculator-ui.mjs').read_text(encoding='utf-8')
    for value in ['Enter a width and height greater than 0.','Enter a focus distance greater than the focal length and greater than 0.','Enter a value greater than 0.','Enter a criterion value greater than 0.','Please check your input values.']:
        assert value in script
def test_formatters_and_comparison_state_default_to_japanese_for_existing_fixtures():
    """既存Golden Fixtures/既存.mjsテストは言語引数なしで呼んでおり、
    デフォルト"ja"の挙動を変更しないことをソースで固定する。"""
    formatters=(ROOT/'assets/js/dof/formatters.mjs').read_text(encoding='utf-8')
    comparison=(ROOT/'assets/js/dof/comparison-state.mjs').read_text(encoding='utf-8')
    assert 'export function formatDistanceDelta(deltaMm,lang="ja")' in formatters
    assert 'export function compareDistance(previousMm, currentMm, lang = "ja")' in comparison
def test_blur_chart_default_lang_and_existing_japanese_text_preserved():
    """blur-chart.mjsは既定"ja"を維持し、既存テスト（日本語文字列の存在確認）が
    参照する文言は物理的にこのファイル内に残る（strings.mjs等へ切り出していない）。"""
    script=(ROOT/'assets/js/dof/blur-chart.mjs').read_text(encoding='utf-8')
    assert 'export function renderBlurChart(container,input,result,lang="ja")' in script
    for value in ['Near','Focus','Far','Depth of field','Object distance vs. calculated blur diameter']:
        assert value in script
