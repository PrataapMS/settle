# Security policy

Settle handles people's private decisions and runs model calls on the project's own keys, so security reports are welcome and taken seriously.

## Reporting a vulnerability

Please don't open a public issue. Report it privately through [GitHub private vulnerability reporting](https://github.com/PrataapMS/settle/security/advisories/new), with:

- what you found and where (URL, endpoint or file),
- steps to reproduce,
- the impact you think it has.

You'll get an acknowledgement within 3 working days and a plan within 10.

## In scope

- Exposure of any API key or secret
- Ways to make model calls without a valid session, or to get around rate limits, daily allowances or the global budget
- Using the `/api` gateway as a general-purpose model proxy
- Cross-site scripting, CSRF, or bypasses of the Content Security Policy
- Message text or IP addresses reaching server storage or logs
- Import files that execute code or corrupt other decisions

## Out of scope

- Denial of service by volume (the budget caps bound it by design)
- Missing headers on third-party hosts (Turnstile, OpenRouter)
- Findings that need a compromised device or browser

The controls and threat model are in [docs/10-security-and-privacy.md](docs/10-security-and-privacy.md).
