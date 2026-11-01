from apps.collector.main import next_poll


def test_failing_feeds_retry_soon_and_back_off():
    assert next_poll(604800, 0) == 604800                                    # healthy weekly feed: weekly
    assert [next_poll(604800, n) for n in (1, 2, 3, 7, 20)] == [60, 120, 240, 3600, 3600]  # failing: minutes, then hourly
    assert next_poll(30, 0) == 30 and next_poll(30, 1) == 60                 # fast feeds still slow down when failing


def test_records_go_to_browsers_only_when_changed():
    from apps.collector.main import should_push, signature
    a = [{"id": "1", "title": "M4.1", "fetched_at": "2026-11-01T10:00:00Z"}]
    same = [{"id": "1", "title": "M4.1", "fetched_at": "2026-11-01T10:02:00Z"}]  # only restamped by the poll
    assert signature(a) == signature(same) and signature(a) != signature([{**a[0], "title": "M4.3"}])
    assert should_push(None, signature(a), 0, 0)                          # first time: send
    assert not should_push((signature(a), 0), signature(same), 120, 0)    # unchanged: health only
    assert should_push((signature(a), 0), 1, 120, 0)                      # changed: send
    assert not should_push((signature(a), 0), 1, 120, 600)                # changed but throttled (satellites)
    assert should_push((signature(a), 0), 1, 600, 600)
