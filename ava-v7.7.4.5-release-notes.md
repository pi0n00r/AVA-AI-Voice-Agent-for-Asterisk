## Ava v7.7.4.5

This maintenance release aligns the maintained fork with upstream and hardens remote-PBX operation and update recovery.

### Changed

- Uses one entitlement-aware Compose build path for fresh installs, preflight, CLI updates, Admin rebuilds, updater bootstrap, and rollback recovery.
- Preserves explicit builder and Compose selection, validates selected targets, and starts services only after a successful build.
- Restores the installation, CLI, build, and troubleshooting guidance required by the unified build policy.

### Fixed

- Retains live ARI, module, and application evidence when Asterisk runs on a remote PBX.
- Distinguishes skipped Ava-host Asterisk audits, missing manifests, and empty audit results instead of reporting a false green checklist.
- Preserves rootless Docker socket selection and avoids recreating an already-running Engine during an ordinary Admin start.
- Prevents update failures from exposing credential-bearing repository URLs.

### Qualification

- GitHub container builds passed for Engine, Admin, Local AI, and starter Asterisk.
- Focused backend/install regressions: 242 passed.
- CLI Go tests, remote-PBX frontend tests, and production frontend build passed.
- CodeRabbit review findings were addressed; the final release-identity-only commit was verified directly after the review quota was exhausted.

This is a source/package release. It does not claim a completed human PSTN call acceptance test.
