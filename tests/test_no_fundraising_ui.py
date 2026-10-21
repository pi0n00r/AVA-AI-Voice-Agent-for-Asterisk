from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "admin_ui" / "frontend" / "src"


def test_fork_has_no_fundraising_ui_or_metadata() -> None:
    removed = (
        FRONTEND / "components" / "DonationBanner.tsx",
        FRONTEND / "config" / "donation.ts",
        FRONTEND / "hooks" / "useDonationReminder.ts",
        FRONTEND / "utils" / "donationReminder.ts",
        ROOT / ".github" / "FUNDING.yml",
    )
    assert all(not path.exists() for path in removed)

    source = "\n".join(
        path.read_text(encoding="utf-8")
        for pattern in ("*.ts", "*.tsx")
        for path in FRONTEND.rglob(pattern)
    ).lower()
    prohibited = (
        "donationbanner",
        "usedonationreminder",
        "ko-fi.com/asteriskaivoiceagent",
        "github.com/sponsors/hkjarral",
    )
    assert all(value not in source for value in prohibited)
