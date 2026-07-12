# GitHub pull-request comments

Witness can publish the evidence-backed contents of `result.json` or
`campaign-result.json` as a pull-request comment.

```bash
witness post-github-comment witness-output/result.json \
  --repository "$GITHUB_REPOSITORY" \
  --pr-number "$PR_NUMBER"
```

The command requires `GITHUB_TOKEN`. It never includes typed secrets from the
session trace; it renders only the already-redacted result contract. Use
`--dry-run` to review the Markdown without making a network request.

## GitHub Actions example

```yaml
name: Witness PR QA

on:
  pull_request:

permissions:
  contents: read
  issues: write
  pull-requests: write

jobs:
  witness:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install .
      - run: witness install-browser
      - name: Run Witness
        run: |
          witness run --project . --provider scripted \
            --decision-file validation/decisions/web_signup.json \
            --output witness-output --json
      - name: Comment on the pull request
        if: always()
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
        run: witness post-github-comment witness-output/result.json
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: witness-output
          path: witness-output/
```

For real provider runs, keep provider credentials in Actions secrets and use a
cost budget such as `--max-cost 0.50`. Codex OAuth is intended for local Codex
CLI sessions; GitHub-hosted runners normally use a dedicated provider secret or
a deterministic scripted benchmark.
