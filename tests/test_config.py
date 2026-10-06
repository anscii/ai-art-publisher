from app.config import AppConfig


def test_google_oauth_config_defaults():
    assert AppConfig.google_client_id == ""
    assert AppConfig.google_client_secret == ""
    assert AppConfig.google_oauth_redirect_uri == ""
    assert AppConfig.owner_email == ""
