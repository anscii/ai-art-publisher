from app import models
from tests.conftest import _TestingSessionLocal


def test_series_defaults():
    db = _TestingSessionLocal()
    s = models.Series(title="Test")
    db.add(s)
    db.commit()
    db.refresh(s)
    assert s.id is not None
    assert s.status == "new"
    assert s.tags_instagram == "[]"
    assert s.tags_telegram == "[]"
    assert s.name == ""
    assert s.collection_id is None
    db.close()


def test_collection_model():
    db = _TestingSessionLocal()
    c = models.Collection(name="Cycle One")
    db.add(c)
    db.commit()
    db.refresh(c)
    assert c.id is not None
    assert c.name == "Cycle One"
    assert c.deleted_at is None
    db.close()


def test_post_model():
    db = _TestingSessionLocal()
    s = models.Series(title="S")
    db.add(s)
    db.commit()
    img = models.Image(series_id=s.id, r2_key="images/x.jpg", original_filename="x.jpg")
    db.add(img)
    db.commit()
    p = models.Post(series_id=s.id, platform="telegram", title="T", description="D", tags="[]")
    db.add(p)
    db.flush()
    db.add(models.PostImage(post_id=p.id, image_id=img.id, order_index=0))
    db.commit()
    db.refresh(p)
    assert p.id is not None
    assert p.status == "draft"
    assert len(p.post_images) == 1
    db.close()


def test_image_belongs_to_series():
    db = _TestingSessionLocal()
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
    db = _TestingSessionLocal()
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
