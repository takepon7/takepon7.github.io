from gitai_phase0.share_card import top_percentile_label


def test_top_percentile_label_keeps_best_scores_readable() -> None:
    assert top_percentile_label(1.0) == "Top 1%"
    assert top_percentile_label(0.996) == "Top 1%"
    assert top_percentile_label(0.958) == "Top 4.2%"
    assert top_percentile_label(0.667) == "Top 33%"
    assert top_percentile_label(0.0) == "Top 100%"
