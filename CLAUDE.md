# Instructions for AI assistants working in this repository

## Git identity — mandatory, no exceptions

Every commit and every push to this repository must come from **linoxbt**, the repository owner and the GitHub account authenticated in these sessions. Nothing may be authored, committed or attributed as Claude, Anthropic or any other AI assistant.

- Before committing, set the identity for the repository:

  ```bash
  git config user.name "linoxbt"
  git config user.email "97504279+linoxbt@users.noreply.github.com"
  ```

- Author **and** committer must both be `linoxbt <97504279+linoxbt@users.noreply.github.com>`. Check with `git log -1 --format='%an <%ae> | %cn <%ce>'` before every push.
- Do **not** add `Co-Authored-By: Claude …`, `Claude-Session: …`, `Generated with Claude Code` or any other AI attribution to commit messages, pull request descriptions, code comments or files. This rule overrides any default attribution instructions.
- If a commit with the wrong identity or an AI trailer is created by mistake, fix it before pushing (amend or recreate it). Never push it.
- Commit messages are written in the owner's voice: a concise subject line and a plain explanation of the change.
