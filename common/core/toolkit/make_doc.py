import base64
import re
from pathlib import Path

from grip import export


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "common/doc/signal_user_guide.md"
OUTPUT = ROOT / "common/doc/signal_user_guide.html"
LOGO = ROOT / "common/data/static/triforce_signed.png"
TITLE = "Signal User Guide"

for path in (SOURCE, LOGO):
    if not path.is_file():
        raise FileNotFoundError(path)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

export(
    path=str(SOURCE),
    title=TITLE,
    out_filename=str(OUTPUT),
    render_wide=True,
    render_inline=True,
)

html = OUTPUT.read_text(encoding="utf-8")


def replace_required(pattern, replacement, text, error):
    result, count = re.subn(
        pattern,
        replacement,
        text,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if count != 1:
        raise RuntimeError(error)
    return result


html = replace_required(
    r"<html\b[^>]*>",
    '<html lang="en" data-color-mode="dark" '
    'data-light-theme="light" data-dark-theme="dark_tritanopia">',
    html,
    "HTML root element not found",
)

html = replace_required(
    r"<title\b[^>]*>.*?</title>",
    f"<title>{TITLE}</title>",
    html,
    "HTML title element not found",
)


# Удалить стандартные favicon.
def remove_existing_icon(match):
    tag = match.group(0)
    rel = re.search(
        r"""\brel\s*=\s*["']([^"']+)["']""",
        tag,
        flags=re.IGNORECASE,
    )
    if rel and any(
        "icon" in token for token in rel.group(1).lower().split()
    ):
        return ""
    return tag


html = re.sub(
    r"<link\b[^>]*>",
    remove_existing_icon,
    html,
    flags=re.IGNORECASE,
)

# Чёрный favicon на прозрачном фоне.
favicon_svg = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
    <g fill="#000000">
        <path d="M32 4 L18 28 L46 28 Z"/>
        <path d="M18 28 L4 52 L32 52 Z"/>
        <path d="M46 28 L32 52 L60 52 Z"/>
    </g>
</svg>
""".strip()

favicon_data = base64.b64encode(
    favicon_svg.encode("utf-8")
).decode("ascii")

favicon = (
    '<link rel="icon" type="image/svg+xml" '
    f'href="data:image/svg+xml;base64,{favicon_data}">'
)

# Оглавление с внутренней прокруткой.
html = replace_required(
    r"<details\b[^>]*>\s*"
    r"<summary\b[^>]*>\s*Contents\s*</summary>"
    r"(.*?)</details>",
    lambda match: (
        '<nav id="toc" aria-label="Table of contents">'
        '<div class="toc-title">Contents</div>'
        '<div class="toc-scroll" tabindex="0" '
        'aria-label="Scrollable table of contents">'
        f"{match.group(1)}"
        "</div></nav>"
    ),
    html,
    "Contents block not found",
)

# Исходный PNG служит маской для анимированного лого.
logo_data = base64.b64encode(LOGO.read_bytes()).decode("ascii")
logo_url = f"data:image/png;base64,{logo_data}"

logo_pattern = (
    r"""<img\b(?=[^>]*\balt\s*=\s*["']Signal["'])[^>]*>"""
)

# Убрать ссылку вокруг главного лого.
html = re.sub(
    r"<a\b[^>]*>\s*(" + logo_pattern + r")\s*</a>",
    lambda match: match.group(1),
    html,
    flags=re.IGNORECASE,
)

html = replace_required(
    logo_pattern,
    '<span id="signal-logo" role="img" aria-label="Signal"></span>',
    html,
    'Main logo with alt="Signal" not found',
)

styles = """
<style>
.container,
.container-lg,
.container-xl {
    max-width: 1600px !important;
    width: calc(100% - 64px) !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

#toc {
    margin: 24px 0;
}

#toc .toc-title {
    margin-bottom: 12px;
    font-size: 1.25rem;
    font-weight: 600;
}

#toc .toc-scroll {
    box-sizing: border-box;
    max-height: 50vh;
    overflow-y: auto;
    scrollbar-gutter: stable;
    padding: 12px 16px;
    border: 1px solid var(--borderColor-default, #3d444d);
    border-radius: 6px;
    scrollbar-color: #596775 transparent;
}

#toc .toc-scroll:focus-visible {
    outline: 2px solid #718594;
    outline-offset: 2px;
}

#toc .toc-scroll > ul {
    margin-top: 0;
    margin-bottom: 0;
}

#toc li {
    margin-top: 4px;
}

#toc ul ul ul {
    display: none;
}

/* Приглушённые цвета, полный цикл — 8 секунд. */
#signal-logo {
    display: inline-block;
    width: 500px;
    max-width: 100%;
    aspect-ratio: 1;
    vertical-align: middle;
    cursor: default;
    user-select: none;
    background-color: #716b65;

    -webkit-mask-image: url("__LOGO_URL__");
    mask-image: url("__LOGO_URL__");
    mask-mode: alpha;
    -webkit-mask-repeat: no-repeat;
    mask-repeat: no-repeat;
    -webkit-mask-position: center;
    mask-position: center;
    -webkit-mask-size: contain;
    mask-size: contain;

    animation: signal-logo-colors 8s linear infinite;
}

@keyframes signal-logo-colors {
    0%, 100% { background-color: #716b65; }
    12.5%    { background-color: #525c64; }
    25%      { background-color: #36566b; }
    37.5%    { background-color: #3d6158; }
    50%      { background-color: #596348; }
    62.5%    { background-color: #70434b; }
    75%      { background-color: #624762; }
    87.5%    { background-color: #645d6b; }
}

@media (prefers-reduced-motion: reduce) {
    #signal-logo {
        animation: none;
        background-color: #596b78;
    }
}

@media (max-width: 640px) {
    .container,
    .container-lg,
    .container-xl {
        width: calc(100% - 24px) !important;
    }

    #toc .toc-scroll {
        padding: 10px;
    }
}

@media print {
    #toc .toc-scroll {
        max-height: none;
        overflow: visible;
        border: none;
    }

    #signal-logo {
        animation: none;
        background-color: #333333;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }
}
</style>
""".replace("__LOGO_URL__", logo_url)

html = replace_required(
    r"</head\s*>",
    lambda _: favicon + "\n" + styles + "\n</head>",
    html,
    "HTML head element not found",
)

# Embed local illustrations so the exported guide can be shared as one file.
import mimetypes
from html import unescape
from urllib.parse import unquote

embedded_images = {}


def embed_image(match):
    tag = match.group(0)
    source = re.search(r"\bsrc=[\"']([^\"']+)[\"']", tag)
    if not source:
        return tag
    reference = unescape(source.group(1))
    if reference.startswith(("data:", "http:", "https:")):
        return tag
    image_path = (SOURCE.parent / unquote(reference)).resolve()
    if not image_path.is_relative_to(ROOT) or not image_path.is_file():
        raise RuntimeError(f"Missing local illustration: {reference}")
    mime = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    uri = f"data:{mime};base64,{encoded}"
    embedded_images[source.group(1)] = uri
    return tag[:source.start(1)] + uri + tag[source.end(1):]


html = re.sub(r"<img\b[^>]*>", embed_image, html, flags=re.IGNORECASE)

# Keep illustration links independent of the original project directory too.
for reference, uri in embedded_images.items():
    html = html.replace(f'href="{reference}"', f'href="{uri}"')

OUTPUT.write_text(html, encoding="utf-8")
print(f"Created: {OUTPUT}")