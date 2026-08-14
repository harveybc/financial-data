# Security Policy

## Public repository boundary

This data and research repository is public. Only redistributable data,
reproducible acquisition code and sanitized research documentation belong in
Git. Never commit:

- provider usernames, passwords, API keys, access tokens or private keys;
- broker account identifiers or account fingerprints;
- personal identity, address, telephone or date-of-birth information;
- private-network addresses, SSH endpoints or machine-specific credentials;
- paid or licensed datasets whose terms prohibit redistribution.

Credentials must be supplied through ignored environment files under
`_metadata/` or through the process environment. Public examples use
placeholders and documentation-reserved network addresses only.

Treat any credential that reaches Git as compromised: revoke or rotate it and
remove it from every published branch, tag and historical commit. A local
deletion by itself is insufficient.

## Reporting

Do not quote suspected secrets in a public issue. Use GitHub's private
vulnerability-reporting channel when available, or contact the repository
owner privately through the GitHub profile.
