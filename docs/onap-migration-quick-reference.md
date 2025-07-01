# ONAP Migration Quick Reference

## Quick Start

```bash
# 1. Set environment variables
export JENKINS_SERVER="https://jenkins.onap.org"  # Update with actual URL
export JENKINS_USER="your-username"
export JENKINS_PASSWORD="your-api-token"

# 2. Login to 1Password
op account add --address lfnetworking.1password.com
op signin

# 3. Dry run to preview migration
lftools-ng migrate repository \
  --project "ONAP" \
  --vault "ONAP" \
  --account "lfnetworking.1password.com" \
  --dry-run

# 4. Actual migration
lftools-ng migrate repository \
  --project "ONAP" \
  --vault "ONAP" \
  --account "lfnetworking.1password.com"
```

## Key Details

- **Source**: ONAP (ECOMP) Jenkins server
- **Target**: LF Networking 1Password vault "ONAP"
- **Account**: lfnetworking.1password.com
- **Expected**: 200+ repository credentials
- **Pattern**: Credentials containing "deployment"
- **Origin Field**: "Migrated from Jenkins" (automatically added)

## Verification Checklist

After migration, each 1Password item should have:
- ✅ Repository name as title
- ✅ Username from Jenkins
- ✅ Password from Jenkins (concealed)
- ✅ GitHub repository URL
- ✅ "origin/source" field = "Migrated from Jenkins"

## Troubleshooting

- **No credentials found**: Try `--filter-pattern "nexus"` or `--filter-pattern "artifact"`
- **Connection issues**: Verify Jenkins URL and credentials
- **1Password errors**: Re-run `op signin`
