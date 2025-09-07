# Security Policy

Thank you for helping keep this project and its users safe.

## Supported Versions

We provide security fixes for:
- main (default) branch
- the latest tagged release

We generally do not backport fixes to older releases unless there is a critical, widely exploitable issue.

## Reporting a Vulnerability

Please use GitHub Security Advisories to report vulnerabilities:
- Go to the repository’s Security tab
- Click “Report a vulnerability” to open a private advisory

We do not accept reports via email.

Please avoid sharing sensitive details in public issues or pull requests.

## Disclosure Policy

- Acknowledge receipt within 48 hours and begin triage
- Initial assessment within 5 business days
- Coordinate on a fix and disclosure timeline
- Default public disclosure window: 90 days after triage (or sooner once a fix is available and users have time to update)

## Our Commitments

- Handle reports responsibly and confidentially
- Credit reporters upon public disclosure (with consent)
- Communicate status and timelines as we progress

## Scope

In scope:
- This repository’s source code and released artifacts
- Configuration and documentation within this repository

Out of scope (non-exhaustive):
- Third-party services and dependencies (report to their maintainers)
- Social engineering, physical attacks, or privileged local-attacker scenarios
- Volumetric Denial of Service
- Issues requiring non-default, discouraged configurations

## Safe Harbor

Good-faith security research is welcomed. If you follow this policy, we will not pursue legal action. Please avoid privacy violations, data loss, or service disruption, and stop testing and notify us if you encounter sensitive data.

## Secrets and Sensitive Data

- Do not commit secrets (tokens, API keys, private keys)
- If you discover a secret, do not disclose it; report its location through Security Advisories so it can be rotated

## Dependencies

- Prefer reporting dependency vulnerabilities upstream
- If a dependency becomes exploitable only due to our usage, report via Security Advisories with details of the usage pattern

## Bug Bounty

We don’t operate a bug bounty. High-impact, well-documented reports are appreciated and credited (with consent) upon disclosure.

