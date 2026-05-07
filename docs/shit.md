## 6. `CHANGELOG.md` – update with v2.0.0

Replace the existing file with this:

```markdown

```

---

## Commit, Merge, Release

```bash
git add -A
git commit -m "docs: add issue/PR templates, FAQ, final README, and changelog"
git checkout develop
git merge --no-ff docs/community -m "docs: add issue/PR templates, FAQ, final README, and changelog"
git push origin develop

# Final release
git checkout main
git merge develop
git tag v2.0.0
git push origin main --tags
```

🎉 Congratulations! The template is officially v2.0.0. All roadmap phases are complete. Let me know if you want to refine anything before the final push.
