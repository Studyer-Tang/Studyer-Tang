# Keeping the public project list current

The two profile READMEs and the personal website share `scripts/sync_projects.py`.
It reads public GitHub repositories and their releases using the REST API, with
no third-party service or Python dependency. Repository **About / Description**
is the canonical summary; edit it on the project to update the profile and site.

- Every six hours, `.github/workflows/projects.yml` checks public owned repositories.
- Added projects appear automatically. Deleted, private, archived and forked projects
  are excluded. The profile and website repositories are also excluded.
- Latest means the most recently **published** release, including clearly labelled
  previews. It does not imply a stable release or guarantee downloadable binaries.
- Four featured projects have curated display names and ordering in `FEATURED`.
  All other eligible projects follow alphabetically. Descriptions retain the language
  used in the repository About field; they are not machine-translated.
- Only the text between `projects:start` and `projects:end` is replaced. Biography,
  education, reading lists, and other personal content remain manually maintained.
- An API failure stops the update before writing. Unchanged data makes no commit.
- The website checks out this generator at build time, refreshes its own static data,
  and deploys in the same workflow. It does not rely on a bot push triggering a second
  workflow, request data from visitors' browsers, or need a personal access token.

Run manually from **Actions → Sync public projects → Run workflow**, or locally:

```sh
python -m unittest discover -s tests -v
python scripts/sync_projects.py --profile
```

For a site snapshot: `python scripts/sync_projects.py --output /path/to/projects.json`.
`GH_TOKEN` is optional locally and provided by `github.token` in Actions. Never put a
token in source files. The profile workflow writes only to this repository; the site
workflow has read access plus Pages deployment permissions.

Schedules are best effort, not instant. GitHub can delay jobs and disables scheduled
workflows after 60 days without activity in a public repository. Re-enable the workflow
in Actions if needed. See [GitHub's scheduling documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
