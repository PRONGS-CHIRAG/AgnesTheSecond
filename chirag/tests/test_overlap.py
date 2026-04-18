"""Tests for overlap metrics and Phase 1 report."""

from agnes.models.reports import EntityCounts
from agnes.services import overlap


def test_classify_concentration_edges() -> None:
    assert overlap.classify_concentration(1) == "single-sourced"
    assert overlap.classify_concentration(2) == "fragmented"
    assert overlap.classify_concentration(4) == "fragmented"
    assert overlap.classify_concentration(5) == "well-distributed"


def test_compute_repeated_materials_min_one(engine) -> None:
    """Challenge DB ties each raw to one company in BOMs; min_companies=1 lists all raws."""
    repeated = overlap.compute_repeated_materials(engine, min_companies=1)
    assert len(repeated) >= 100


def test_compute_supplier_fragmentation_non_empty(engine) -> None:
    frag = overlap.compute_supplier_fragmentation(engine, min_suppliers=2)
    assert frag
    assert frag[0].concentration_note == "fragmented"


def test_build_phase1_report(engine) -> None:
    report = overlap.build_phase1_report(engine)
    assert isinstance(report.entity_counts, EntityCounts)
    assert report.entity_counts.Company == 61
