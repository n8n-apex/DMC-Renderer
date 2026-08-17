"""TDD for the PROCESS viz family (components/viz_process.jinja): step_cascade
+ phase_timeline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from templating import get_env  # noqa: E402


def _r(macro, v):
    return get_env().from_string(
        "{%% from 'viz_process.jinja' import %s %%}{{ %s(v) }}" % (macro, macro)
    ).render(v=v)


def test_step_cascade_renders_titles_and_nodes():
    out = _r("step_cascade", {"preset": "step_cascade", "steps": [
        {"title": "Kunden-Onboarding"}, {"title": "Copy-Generierung"},
        {"title": "Check-in-Vorbereitung"}]})
    assert "Kunden-Onboarding" in out and "Check-in-Vorbereitung" in out
    assert "c-viz-cascade" in out
    assert out.count("c-viz-cascade__node") == 3
    assert ">1<" in out and ">3<" in out   # auto-numbered nodes


def test_step_cascade_empty_renders_nothing():
    assert _r("step_cascade", {"preset": "step_cascade", "steps": []}).strip() == ""


def test_phase_timeline_renders_titles_durations_nodes():
    out = _r("phase_timeline", {"preset": "phase_timeline", "phases": [
        {"title": "Audit", "duration": "Woche 1"},
        {"title": "Bereinigung"},
        {"title": "Implementierung", "duration": "Woche 3-4"}]})
    assert "Audit" in out and "Implementierung" in out
    assert "Woche 1" in out and "Woche 3-4" in out
    assert "c-viz-phase" in out
    assert out.count("c-viz-phase__node") == 3
    assert ">1<" in out and ">3<" in out   # auto-numbered nodes


def test_phase_timeline_empty_renders_nothing():
    assert _r("phase_timeline", {"preset": "phase_timeline", "phases": []}).strip() == ""
