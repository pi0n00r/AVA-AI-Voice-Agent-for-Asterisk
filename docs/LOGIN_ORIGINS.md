# Admin login origins

The packaged dual-stack Admin listener accepts IPv4 and IPv6 on one socket. Set
`AAVA_TRUSTED_PROXIES` to the exact proxy addresses or CIDRs that supply
`X-Forwarded-For`; `FORWARDED_ALLOW_IPS` is the legacy fallback. Both the HTTP
forwarding layer and login throttling use this same setting. IPv4 proxies
accepted through the IPv6 socket are treated as their IPv4 identity. Do not
trust arbitrary clients or all forwarded headers.

An unknown login origin has a separate attempt budget from an origin that
successfully signed in within the past 30 days. A successful login does not
erase every account or address budget. If login returns HTTP 429, honor its
`Retry-After` value and inspect the effective proxy setting and socket peer.
Correct an incorrectly trusted proxy before retrying. Repeated attempts during
the lockout do not help. Keep the Admin endpoint restricted to your management
route during recovery; do not delete `users.json` or `login_origins.db` to
clear a lockout. If the password itself is lost, use the host password recovery
procedure in the [Admin UI setup guide](../admin_ui/UI_Setup_Guide.md#password-management).
