# Reproducible deployment

- Each app owns its build/test/release commands and independent CI/CD. Use native GitHub/Vercel integration or narrowly trusted AWS OIDC roles where supported. Never copy the factory's execution credentials into generated repositories.
- Record runtime/tool versions, lockfiles, artifact provenance, source commit, environment, and redacted target identifiers. The same source and declared inputs should produce a reviewable build.
- Run checks before deployment. Verify authenticated identity, team/account/region, and resolved project immediately before action. For Vercel, use the intended app directory and `vercel project inspect --non-interactive`; stop on missing/mismatched context rather than auto-linking.
- Default to an authorized preview/sandbox. Production promotion requires explicit authorization and its own rollback/health criteria. Deployment and custom-domain/DNS changes are separate approvals.
- Verify the result through the user's real flow: deployment status, HTTPS response, expected behavior, relevant API/data path, and source commit. A successful CLI exit is insufficient.
- Keep a rollback reference and verify provider-specific rollback semantics, data compatibility, and retained artifacts. Plan migration/restore before irreversible data changes.
- Retry using known repository/project/deployment identities. Inspect unknown outcomes; do not create duplicate projects or redeploy blindly. Record a concise redacted result and cleanup responsibility.
