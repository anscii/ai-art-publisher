from app import models
from tests.conftest import TestingSessionLocal


def test_series_defaults():
    db = TestingSessionLocal()
    s = models.Series(title="Test")
    db.add(s)
    db.commit()
    db.refresh(s)
    assert s.id is not None
    assert s.status == "new"
    assert s.tags_instagram == "[]"
    assert s.tags_telegram == "[]"
    assert s.scheduled_targets == "[]"
    db.close()


def test_image_belongs_to_series():
    db = TestingSessionLocal()
    s = models.Series(title="S")
    db.add(s)
    db.commit()
    img = models.Image(
        series_id=s.id,
        r2_key="images/test.jpg",
        original_filename="1680030203290_out.jpg",
    )
    db.add(img)
    db.commit()
    db.refresh(img)
    assert img.id is not None
    assert img.series_id == s.id
    db.close()


def test_cascade_delete_images():
    db = TestingSessionLocal()
    s = models.Series(title="S")
    db.add(s)
    db.commit()
    img = models.Image(series_id=s.id, r2_key="images/x.jpg", original_filename="x.jpg")
    db.add(img)
    db.commit()
    img_id = img.id
    db.delete(s)
    db.commit()
    assert db.get(models.Image, img_id) is None
    db.close()
