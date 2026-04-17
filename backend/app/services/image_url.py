from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def build_versioned_image_url(url: str, version: int) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["v"] = str(version)

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )