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
    page=html();assert '/assets/css/dof-calculator.css?v=2' in page;assert 'type="module" src="/assets/js/dof/calculator-ui.mjs?v=2"' in page
def test_dof_page_separates_url_warning_and_form_validation():
    page=html();assert 'id="dof-url-warning" role="status"' in page;assert 'id="dof-form-error" role="alert"' in page;assert 'id="dof-sensor-error"' in page
