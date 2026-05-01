# Publish Agent Foundry MVP to GitHub

This project is prepared as a normal Git repository. The safest default is a private repository.

## One-command publish with GitHub CLI

```bash
cd agent_foundry_mvp
gh auth login
bash scripts/publish_to_github.sh agent-foundry-mvp private
```

For a public repository:

```bash
bash scripts/publish_to_github.sh agent-foundry-mvp public
```

## Manual publish

Create an empty GitHub repository, then run:

```bash
cd agent_foundry_mvp
git init -b main
git add .
git commit -m "Initial Agent Foundry MVP"
git remote add origin git@github.com:<owner>/agent-foundry-mvp.git
git push -u origin main
```

## Notes

- Do not commit `.env` or API keys.
- OpenAI-backed mode needs `OPENAI_API_KEY` at runtime only.
- Generated workspaces are ignored by `.gitignore`.
