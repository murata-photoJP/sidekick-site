from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("build_site",ROOT/"build/site/build_site.py");bs=importlib.util.module_from_spec(spec);spec.loader.exec_module(bs)
def html(): return bs.render_all("dof")[Path("tools/dof.html")]
def test_dof_page_registered_at_canonical_route():
    assert bs.PAGES["dof"]["output"]==Path("tools/dof.html");assert 'https://www.sidekick-lab.com/tools/dof' in html()
def test_dof_page_has_required_inputs_and_results():
    page=html()
    for value in ['id="dof-sensor"','id="dof-focal"','id="dof-aperture"','id="dof-focus"','id="dof-criterion"','id="dof-results"']:assert value in page
def test_dof_page_has_progressive_disclosures_and_accessibility():
    page=html();assert 'id="dof-curve-disclosure"' in page;assert 'id="dof-assumptions"' in page;assert 'aria-live="polite"' in page;assert page.count("<h1") == 1
def test_dof_page_links_scoped_assets():
    page=html();assert '/assets/css/dof-calculator.css?v=4' in page;assert 'type="module" src="/assets/js/dof/calculator-ui.mjs?v=4"' in page
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
def test_dof_comparison_controller_preserves_invalid_history_and_defers_presets():
    script=(ROOT/'assets/js/dof/calculator-ui.mjs').read_text(encoding='utf-8')
    assert 'history=advanceComparison(history,record(value,result))' in script
    assert 'catch(error){showError(error);updateInputComparison();}' in script
    assert 'button.dataset.fnumber;noteDraftChange()' in script
    assert 'button.dataset.fnumber;calculate()' not in script
