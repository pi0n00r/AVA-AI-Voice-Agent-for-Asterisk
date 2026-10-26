"""Release-facing documentation and the Admin documentation allowlist agree."""
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]


def anchors(text: str) -> set[str]:
    """Return GitHub-style Markdown anchors without importing removed README tests."""
    result = set(re.findall(r'<a\s+(?:id|name)="([^"]+)"', text))
    seen: dict[str, int] = {}
    for heading in re.findall(r'^#{1,6}\s+(.+)$', text, flags=re.MULTILINE):
        heading = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', heading)
        slug = re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-')
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(slug if not count else f'{slug}-{count}')
    return result


@pytest.mark.parametrize("relative", [
    "docs/INTEGRATION_BACKUPS.md",
    "docs/baselines/golden/v7.7.0-validation-matrix.md",
])
def test_new_release_guides_have_resolvable_local_links(relative):
    source = ROOT / relative
    for target in re.findall(r'\]\(([^\s)]+)', source.read_text()):
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue
        path = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source
        assert path.is_file(), target
        if parsed.fragment:
            assert unquote(parsed.fragment) in anchors(path.read_text()), target


def test_new_contributors_have_matching_credit():
    credits = (ROOT / "CONTRIBUTORS.md").read_text()
    for login in ("pcbeingused333", "lucamancusodev"):
        assert f'src="https://github.com/{login}.png"' in credits
        assert f"(https://github.com/{login})" in credits
    contributor_table = credits.split("| Avatar |", 1)[1].split("<!-- markdownlint-restore -->", 1)[0]
    assert "\n\n|" not in contributor_table
    assert "Reports and Requirements" in credits


def test_release_matrix_keeps_explicit_waiver():
    matrix = (ROOT / "docs/baselines/golden/v7.7.0-validation-matrix.md").read_text()
    assert "WAIVED explicitly for v7.7.0" in matrix
    assert "Merge approval | APPROVED" in matrix
    assert "Tag/date | APPROVED" in matrix
    assert "Authorization is not a claim that publication completed" in matrix
    assert "8c3369511f20e7b378a2c1a5c0ba710ada88d5b3" in matrix


def test_publication_metadata_keeps_one_security_section_and_maintained_policy():
    changelog = (ROOT / "CHANGELOG.md").read_text()
    release = changelog.split("## [7.7.0]", 1)[1].split("\n## [", 1)[0]
    assert release.count("### Security") == 1
    security = (ROOT / "SECURITY.md").read_text()
    assert "current `bajaj/maintained` branch" in security
    assert "Historical tags, archives, deployment kits" in security
