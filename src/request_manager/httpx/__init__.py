try:
    import httpx  # noqa: F401
except ImportError as exc:
    raise ImportError(
        "The httpx client requires the 'httpx' extra. "
        "Install it with: pip install request-manager[httpx]"
    ) from exc
