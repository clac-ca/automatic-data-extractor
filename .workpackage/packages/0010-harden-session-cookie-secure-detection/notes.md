# Harden session cookie secure detection

Owner: jkropp
Status: done
Created: 2025-10-22T04:50:21.161Z

---
- 2025-10-22T04:50:35.771Z • jkropp: Reviewing cookie issuance flow to enforce Secure flag when behind proxies.
- 2025-10-22T04:57:17.737Z • jkropp: Hardened secure-cookie detection to ignore spoofed downgrade headers and added targeted unit tests.
