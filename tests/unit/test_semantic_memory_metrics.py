from app.services.semantic_memory_metrics import SemanticMemoryMetrics


def test_metrics_accept_only_bounded_known_names_and_return_aggregates():
    metrics = SemanticMemoryMetrics()

    metrics.increment("semantic_memory_exact_hit")
    metrics.increment("semantic_memory_exact_hit", 2)
    metrics.observe_ms("normalization_ms", 1.5)
    metrics.observe_ms("normalization_ms", 3.5)
    metrics.increment("raw_alias_value_should_not_be_a_metric")

    snapshot = metrics.snapshot()

    assert snapshot["counters"]["semantic_memory_exact_hit"] == 3
    assert snapshot["timings"]["normalization_ms"]["count"] == 2
    assert snapshot["timings"]["normalization_ms"]["total_ms"] == 5.0
    assert "raw_alias_value_should_not_be_a_metric" not in snapshot["counters"]


def test_metrics_never_return_raw_alias_or_provider_identity():
    metrics = SemanticMemoryMetrics()
    metrics.increment("semantic_memory_confirmed_write")

    snapshot = metrics.snapshot()

    assert "Sad overlxrd" not in repr(snapshot)
    assert "artist123" not in repr(snapshot)
