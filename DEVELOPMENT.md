# Development notes

Internal notes for maintaining the `in-html` plugin. Claude Code never loads this file and it is of no interest to end users; it just rides along in the repo.

## Releasing an update

Pushing to `main` ships it. Installs track the branch, so the next `/plugin update` picks it up. When the change is meaningful, bump version in both plugin.json and marketplace.json (keep them equal).
