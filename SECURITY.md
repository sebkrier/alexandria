# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Alexandria, please report it responsibly:

1. **Do not** open a public issue
2. Email the maintainers directly or use GitHub's private vulnerability reporting
3. Include a clear description of the vulnerability and steps to reproduce

We will acknowledge receipt within 48 hours and provide a timeline for resolution.

## Security Measures

Alexandria implements the following security practices:

### Database Security
- All SQL queries use parameterized statements via psycopg3
- SQLAlchemy ORM with proper escaping for all database operations
- No raw SQL string concatenation

### API Security
- Input validation via Pydantic schemas with strict typing
- UUID validation for all resource identifiers
- HttpUrl validation for URL inputs

### Secrets Management
- API keys encrypted at rest using Fernet symmetric encryption
- Environment variables for sensitive configuration
- No secrets committed to version control

### Dependencies
- Regular dependency audits via `npm audit` and `pip-audit`
- Dependabot enabled for automated security updates

## Environment Variables

The following environment variables contain sensitive data and must be protected:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string with credentials |
| `ENCRYPTION_KEY` | 32-byte hex key for encrypting stored API keys |
| `R2_*` | Cloudflare R2 credentials (if using PDF storage) |

Generate a secure encryption key with:
```bash
openssl rand -hex 32
```

## Best Practices for Self-Hosting

1. **Use HTTPS** in production (via reverse proxy like Caddy or nginx)
2. **Restrict network access** to the database
3. **Rotate secrets** periodically
4. **Keep dependencies updated** - run `npm audit` and check for Python CVEs regularly
5. **Backup your database** and test restoration procedures
