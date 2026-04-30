# Git Push to a New Remote (and Why Push/Merge Can Fail)

This guide documents the exact command flow we used to push this local repo to a new GitHub remote.

## 1) Detect existing remotes

```bash
git remote -v
```

You should see output like:

```text
origin  https://github.com/<owner>/<repo>.git (fetch)
origin  https://github.com/<owner>/<repo>.git (push)
```

---

## 2) Add or replace a remote

### Option A: Add a new remote name

```bash
git remote add aidplus https://github.com/AIDplus/InSAR-worms.git
```

### Option B: Replace URL for an existing remote name

```bash
git remote set-url aidplus https://github.com/AIDplus/InSAR-worms.git
```

### Option C: Remove and re-add

```bash
git remote remove aidplus
git remote add aidplus https://github.com/AIDplus/InSAR-worms.git
```

Verify:

```bash
git remote -v
```

---

## 3) Commit local changes before push

```bash
git add -A
git commit -m "Prepare repository for push"
```

---

## 4) Push safely to a new branch on remote

If remote `main` already has its own history, push to a new branch first:

```bash
git push -u aidplus main:mssjoud-main
```

This creates remote branch `mssjoud-main` from your local `main`.

Then open a Pull Request on GitHub from `mssjoud-main` -> `main`.

---

## 5) Why `git push ... main` failed

`git push -u aidplus main` was rejected (`non-fast-forward` / `fetch first`) because remote `main` already had commits not present in local `main`.

In Git, you cannot move remote `main` backward or sideways without integrating history first (merge/rebase) or forcing.

---

## 6) What blocked rebase/abort locally

During rebase/abort, these untracked files blocked reset:

- `PICKLE/geocode`
- `PICKLE/geocode.xml`

Error pattern:

```text
The following untracked working tree files would be overwritten by reset:
  PICKLE/geocode
  PICKLE/geocode.xml
```

These files were root-owned (likely created by container runs), so normal user operations could not move/remove them until ownership was fixed.

Typical fix:

```bash
sudo chown -R "$USER":"$USER" PICKLE
mv PICKLE/geocode PICKLE/geocode.xml /tmp/isce2-playbook-backup/
git rebase --abort
```

---

## 7) What “merge” means on GitHub (vs merging folders)

On GitHub, **Merge Pull Request** means:

- merge commit histories (branch tips)
- combine code changes by comparing commits/snapshots
- auto-merge non-overlapping edits
- raise conflicts when both branches changed the same lines differently

It does **not** mean “copy one folder into another folder.”

So GitHub merge is about integrating branch history and file diffs, not folder-level file transfer.

---

## 8) Two practical workflows

### Safe workflow (recommended)

1. Push local work to a new remote branch.
2. Open PR.
3. Review diffs/conflicts.
4. Merge PR into remote `main`.

### Destructive workflow (only if intentional)

Force local `main` to overwrite remote `main`:

```bash
git push --force-with-lease aidplus main:main
```

Use this only when you explicitly want to replace remote history.
