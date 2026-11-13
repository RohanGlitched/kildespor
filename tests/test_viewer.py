"""The static viewer: a run folder opens from <out>/index.html, and the index row carries news, jobs and the headline."""
import json

from kildespor.viewer import _index_row, entry_paths, write_viewer


def _env(org="123456789", summary=None):
    return {
        "organisation_number": org, "legal_name": "TEST AS", "status": "available",
        "claims": [
            {"family": "identity", "field": "municipality", "value": "OSLO", "key": "identity:municipality:x", "evidence_ids": ["e1"]},
            {"family": "activity", "field": "company_news", "value": {"title": "Ny avtale med kommunen", "url": "https://test.no/nyheter/ny-avtale"},
             "effective_date": "2026-11-02", "key": "activity:company_news:ny", "evidence_ids": ["e1"]},
            {"family": "jobs", "field": "job_posting", "value": {"title": "Elektriker", "url": "https://test.no/jobb/1", "status": "open"},
             "key": "jobs:job_posting:1", "evidence_ids": ["e1"]},
            {"family": "social", "field": "company_profile", "value": "https://facebook.com/test",
             "details": {"platform": "facebook", "url": "https://facebook.com/test", "handle": "test"}, "key": "social:fb", "evidence_ids": ["e1"]},
        ],
        "evidence": [{"id": "e1", "source_url": "https://test.no/", "retrieved_at": "2026-11-13T10:00:00Z", "content_sha256": "ab" * 32}],
        "field_states": [{"family": "website", "state": "not_available"}],
        "summary": summary if summary is not None else {"headline": "TEST AS is hiring (NAV)", "sentences": []},
    }


def test_index_row_carries_news_jobs_social_and_headline():
    row = _index_row(_env())
    assert row["news"] == 1 and row["nd"] == "2026-11-02" and row["nt"] == "Ny avtale med kommunen"
    assert row["nu"] == "https://test.no/nyheter/ny-avtale"
    assert row["jobs"] == 1 and row["jt"] == "Elektriker"
    assert row["platforms"] == ["facebook"] and row["social"] == 1
    assert row["hl"] == "TEST AS is hiring (NAV)"


def test_headline_falls_back_to_profile_sentence_for_old_envelopes():
    row = _index_row(_env(summary={"sentences": [{"topic": "profile", "text": "In plain terms: a small business.", "claim_keys": []}]}))
    assert row["hl"] == "In plain terms: a small business."


def test_run_folder_gets_entry_page_readme_and_viewer(tmp_path):
    env = _env()
    viewer = tmp_path / "viewer"
    paths = write_viewer({env["organisation_number"]: env}, [env["organisation_number"]], {"run_id": "r1"}, viewer)
    assert paths["open"] == str(tmp_path / "index.html")
    root = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'window.KS_BASE="viewer/"' in root
    assert 'src="viewer/app.js"' in root and 'src="viewer/data/index.js"' in root and 'href="viewer/style.css"' in root
    assert "<noscript>" in root and "TEST AS" in root and "Ny avtale med kommunen" in root
    assert "open index.html" in (tmp_path / "README.txt").read_text(encoding="utf-8").lower()
    inner = (viewer / "index.html").read_text(encoding="utf-8")
    assert "KS_BASE" not in inner and 'src="app.js"' in inner
    assert (viewer / "data" / "c" / "123456789.js").exists()
    idx = (viewer / "data" / "index.js").read_text(encoding="utf-8")
    assert json.loads(idx[len("window.KS="):-2])["index"][0]["news"] == 1


def test_viewer_outside_a_run_folder_writes_no_entry_page(tmp_path):
    env = _env()
    out = tmp_path / "docs"
    paths = write_viewer({env["organisation_number"]: env}, [env["organisation_number"]], {}, out)
    assert "open" not in paths and not (tmp_path / "index.html").exists()
    assert entry_paths(tmp_path / "viewer")["open"].endswith("index.html")
