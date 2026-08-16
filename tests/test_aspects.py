from astroengine.aspects import AspectPoint, find_aspects
from astroengine.models import DataConfidence
from astroengine.settings import AstrologySettings


def test_exact_square_detected_with_zero_orb():
    points = [
        AspectPoint(name="mars", longitude=10.0),
        AspectPoint(name="saturn", longitude=100.0),
    ]
    aspects = find_aspects(points, AstrologySettings())
    assert len(aspects) == 1
    assert aspects[0].aspect_type == "square"
    assert aspects[0].orb == 0.0


def test_aspect_outside_orb_is_not_detected():
    points = [
        AspectPoint(name="mars", longitude=10.0),
        AspectPoint(name="saturn", longitude=200.0),  # 190 -> 170 from mars, nowhere near any major aspect
    ]
    aspects = find_aspects(points, AstrologySettings())
    assert aspects == []


def test_trine_within_orb_reports_correct_orb():
    points = [
        AspectPoint(name="venus", longitude=0.0),
        AspectPoint(name="jupiter", longitude=125.0),  # 5 deg past exact 120 trine
    ]
    aspects = find_aspects(points, AstrologySettings())
    assert len(aspects) == 1
    assert aspects[0].aspect_type == "trine"
    assert aspects[0].orb == 5.0


def test_luminary_bonus_extends_orb_for_sun_or_moon():
    # sextile base orb is 4.0; 5.5 deg off exact sextile is outside a
    # non-luminary orb but inside sun's +1.0 luminary bonus (4.0+1.0=5.0)... use 4.5 to be inside.
    settings = AstrologySettings()
    non_luminary_points = [
        AspectPoint(name="mercury", longitude=0.0),
        AspectPoint(name="mars", longitude=64.5),  # 4.5 off exact sextile (60)
    ]
    assert find_aspects(non_luminary_points, settings) == []

    luminary_points = [
        AspectPoint(name="sun", longitude=0.0),
        AspectPoint(name="mars", longitude=64.5),
    ]
    aspects = find_aspects(luminary_points, settings)
    assert len(aspects) == 1
    assert aspects[0].aspect_type == "sextile"
    assert aspects[0].orb == 4.5


def test_applying_aspect_when_separation_is_closing():
    # b is behind a and catching up (faster), separation from an exact
    # square (90) is currently 5 deg and closing.
    a = AspectPoint(name="sun", longitude=95.0, speed_longitude=1.0)
    b = AspectPoint(name="moon", longitude=0.0, speed_longitude=13.0)
    aspects = find_aspects([a, b], AstrologySettings())
    assert len(aspects) == 1
    assert aspects[0].is_applying is True


def test_separating_aspect_when_separation_is_opening():
    a = AspectPoint(name="sun", longitude=95.0, speed_longitude=1.0)
    b = AspectPoint(name="moon", longitude=0.0, speed_longitude=-13.0)  # moving away
    aspects = find_aspects([a, b], AstrologySettings())
    assert len(aspects) == 1
    assert aspects[0].is_applying is False


def test_minor_aspects_disabled_by_default():
    points = [
        AspectPoint(name="venus", longitude=0.0),
        AspectPoint(name="mars", longitude=30.0),  # exact semisextile
    ]
    assert find_aspects(points, AstrologySettings()) == []

    settings = AstrologySettings()
    settings.aspect_set["semisextile"] = True
    aspects = find_aspects(points, settings)
    assert len(aspects) == 1
    assert aspects[0].aspect_type == "semisextile"


def test_aspect_confidence_takes_the_weaker_endpoint():
    a = AspectPoint(name="sun", longitude=0.0, confidence=DataConfidence(basis="exact_time"))
    b = AspectPoint(name="ascendant", longitude=90.0, confidence=DataConfidence(basis="unknown_time"))
    aspects = find_aspects([a, b], AstrologySettings())
    assert aspects[0].confidence.basis == "unknown_time"
