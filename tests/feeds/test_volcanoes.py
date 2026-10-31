from pathlib import Path

from apps.collector.feeds.volcanoes import parse


def test_parse():
    [r] = parse(Path("tests/fixtures/volcanoes.xml").read_bytes())  # Etna is outside the coverage region
    assert r["attrs"]["volcano"] == "Marapi" and r["severity"] == "advisory" and r["lat"] == -0.38
    assert r["attrs"]["report"].startswith("The Pusat") and "<p>" not in r["attrs"]["report"]
