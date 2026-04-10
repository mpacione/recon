# Release process

How to cut a new version of `recon-cli` and (optionally) publish it
to PyPI. This is a maintainer document.

## 0. Prerequisites

- Commit access to <https://github.com/mpacione/recon>
- A PyPI account with owner rights on the `recon-cli` project
  (once registered) — <https://pypi.org/manage/account/>
- `build` and `twine` installed in the local venv:

  ```bash
  pip install --upgrade build twine
  ```

## 1. Finalise the branch

```bash
git checkout main
git pull
```

Run the full test suite and lint:

```bash
.venv/bin/python3 -m pytest tests/ -q
.venv/bin/python3 -m ruff check src/ tests/
```

Both must be clean before you tag.

## 2. Bump the version

Edit `pyproject.toml` and set `[project].version` to the new
number. recon follows [Semantic Versioning](https://semver.org/):

- **MAJOR** — breaking changes to the CLI surface, schema format, or
  on-disk workspace layout
- **MINOR** — new features, new commands, new stages
- **PATCH** — bug fixes and internal cleanups

## 3. Update the changelog

In `CHANGELOG.md`, replace the top `## [Unreleased]` header with
the new version number and today's date:

```markdown
## [0.2.0] -- 2026-04-10
```

Then add a fresh empty `## [Unreleased]` section above it for the
next cycle.

## 4. Commit the release

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "release: 0.2.0"
```

## 5. Build the artifacts

```bash
rm -rf dist/
python3 -m build
```

This produces `dist/recon_cli-<version>-py3-none-any.whl` and
`dist/recon_cli-<version>.tar.gz`. Inspect the wheel contents to
make sure nothing important was left out:

```bash
python3 -c "import zipfile; z = zipfile.ZipFile('dist/recon_cli-<version>-py3-none-any.whl'); print('\n'.join(sorted(z.namelist())))"
```

You should see every module under `recon/` and `recon/tui/`, plus
`recon/tui/models/` and `recon/tui/screens/`.

## 6. Smoke test the wheel

Install the built wheel into a disposable venv and run the binary:

```bash
TMP=$(mktemp -d)
python3 -m venv "$TMP/venv"
"$TMP/venv/bin/pip" install "dist/recon_cli-<version>-py3-none-any.whl"

"$TMP/venv/bin/recon" --version
"$TMP/venv/bin/recon" --help

mkdir "$TMP/ws" && cd "$TMP/ws"
"$TMP/venv/bin/recon" init --headless --domain Test --company Me --products foo
"$TMP/venv/bin/recon" status

rm -rf "$TMP"
```

At minimum, `recon --version` must print the version you just bumped,
and `recon init` + `recon status` must work end-to-end with no
`ModuleNotFoundError` or missing-dependency traceback.

## 7. Tag and push

```bash
git tag -a "v<version>" -m "release: <version>"
git push origin main --tags
```

## 8. (Optional) Publish to PyPI

### TestPyPI first (recommended for major releases)

```bash
twine upload --repository testpypi dist/*
```

Then verify in a clean venv:

```bash
pip install --index-url https://test.pypi.org/simple/ recon-cli==<version>
```

### PyPI

```bash
twine upload dist/*
```

Verify the project page at <https://pypi.org/project/recon-cli/>.

## 9. GitHub release

Create a release at
<https://github.com/mpacione/recon/releases/new>:

- **Tag**: `v<version>` (the one you just pushed)
- **Title**: `recon-cli <version>`
- **Notes**: paste the matching section from `CHANGELOG.md`
- **Assets**: upload both files from `dist/`

## 10. Announce

- Update the README "Status" table if the release changed any
  component's state
- Tweet / post wherever you announce recon updates
- Close any issues that the release fixed

## Rolling back

If something goes wrong after publishing:

1. Do **not** re-upload a wheel with the same version. PyPI refuses
   re-uploads; you have to bump to a patch version.
2. For PyPI publications, you can `twine upload --repository pypi
   dist/<next-patch>.whl` after bumping again.
3. Delete the bad GitHub release if needed.
4. Delete the bad git tag:

   ```bash
   git tag -d v<bad-version>
   git push origin :refs/tags/v<bad-version>
   ```

## FAQ

**Why is the distribution named `recon-cli` but the import `recon`?**
Because `recon` is already taken on PyPI. The CLI binary is still
`recon`, driven by the `[project.scripts]` entry in `pyproject.toml`.
`click.version_option` is configured with `package_name="recon-cli"`
so `recon --version` resolves the installed distribution correctly.
