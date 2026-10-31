# Security Policy

## Supported versions

Security fixes are applied to the latest release on the default branch. Older releases are not maintained.

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability.

Use the repository's **Security** tab and choose **Report a vulnerability** to open a private security advisory. Include:

- A description of the issue and the security boundary it crosses.
- Reproduction steps, affected endpoint or component, and the version or commit tested.
- The impact you believe is possible.
- Any suggested remediation.

Do not attach real customer documents, identity numbers, addresses, passports, or other personal data. Reproduce with a synthetic PDF and describe the document structure instead.

Reports are reviewed on a best-effort basis. Please allow time for a fix and coordinated disclosure before publishing details.

## Deployment assumptions

This application is a local, single-user tool. Its default configuration is not hardened for direct exposure to the internet:

- No authentication or user accounts are implemented.
- Every document uploaded to a running backend is accessible to anyone who can reach that backend and knows its document ID. IDs are random, but they are not an authorization boundary.
- Documents are stored in the operating system's temporary directory; metadata is held in process memory.
- CORS defaults to local development origins. Configure `PDF_EDITOR_CORS_ORIGINS` for your deployment.
- The backend must run with one worker while document storage remains in memory.

If you deploy this project for others, terminate TLS at a reverse proxy, add authentication, restrict request sizes, isolate tenants, and provide a cleanup policy for temporary files.

## Out of scope

- Vulnerabilities in third-party dependencies that are already fixed upstream (report them upstream as well, but a notification is welcome).
- Vulnerabilities in PyMuPDF/MuPDF itself. Report those to Artifex.
- The absence of digital-signature functionality. Signature fields are unsigned placeholders by design.
- Findings that require the attacker to already control the server process, the temporary directory, or the operator's browser profile.
- Social engineering and denial-of-service reports that rely on sending enormous or malformed PDFs beyond the documented 80 MB upload limit and 3,000-field save limit.

## Handling documents safely

- Run the editor on a trusted machine and keep the backend bound to localhost unless you have added authentication.
- Treat saved PDFs as sensitive: they may contain personal data and remain in the browser download folder and the operating system's temporary directory.
- Do not commit PDFs, generated copies, or `test-data/` to version control. The provided `.gitignore` excludes them.
