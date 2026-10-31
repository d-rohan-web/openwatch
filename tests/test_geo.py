from packages.common.geo import _districts, district


def test_district():
    assert district("Agra")["state"] == "Uttar Pradesh"
    assert district("BIJAPUR", "CHHATTISGARH")["state"] == "Chhattisgarh"      # same name, state picks
    assert district("Bijapur", "Karnataka")["state"] == "Karnataka"
    assert district("BIJAAPUR")["state"] == "Karnataka"                         # IMD spelling pinned to a state
    assert district("HYDERABAD", "TELANGANA")["name"] == "Hyderabad"            # post-2011 state → 2011 parent
    assert district("EAST DELHI")["state"] == "NCT of Delhi"
    assert district("GANGTOK")["name"] == "East" and district("GANGTOK")["state"] == "Sikkim"
    assert district("SIDDIPET")["name"] == "Medak"                              # new district → 2011 parent
    assert district("CHITTORGARH")["name"] == "Chittaurgarh"
    assert district("Nowhere") is None
    assert len(_districts()) == 641                                             # duplicate names no longer collapse
