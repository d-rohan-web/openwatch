from apps.collector.main import next_poll


def test_failing_feeds_retry_soon_and_back_off():
    assert next_poll(604800, 0) == 604800                                    # healthy weekly feed: weekly
    assert [next_poll(604800, n) for n in (1, 2, 3, 7, 20)] == [60, 120, 240, 3600, 3600]  # failing: minutes, then hourly
    assert next_poll(30, 0) == 30 and next_poll(30, 1) == 60                 # fast feeds still slow down when failing
