from config import config


def test_api_key_is_configured():
    """Cheapest possible signal: every Claude call fails immediately if this is empty."""
    assert config.ANTHROPIC_API_KEY, (
        "ANTHROPIC_API_KEY is empty -- no .env file (or empty value) found. "
        "Copy .env.example to a repo-root .env and set a real key."
    )
