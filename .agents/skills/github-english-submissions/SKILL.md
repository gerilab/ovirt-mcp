---
name: github-english-submissions
description: >-
  Enforces a strict English-only policy for all content submitted to Git and GitHub,
  including commit messages, pull request titles and descriptions, code comments, docstrings,
  documentation files, issue discussions, and release notes. Use whenever authoring,
  editing, or committing content destined for Git repositories or GitHub.
---

# GitHub English-Only Submission Standard

## 1. Overview & Policy Scope

All content committed to Git repositories or submitted to GitHub MUST be authored exclusively in **English**.

This policy applies to all project artifacts and Git metadata, regardless of the conversational language used between the developer and AI agents in the chat interface.

### In Scope (Must Be in English):
- **Git Commit Messages:** Subject lines, detailed bodies, and footers.
- **Git Branches & Tags:** Branch names (`feature/...`, `fix/...`, `docs/...`) and release tags (`v1.2.0`).
- **Pull Requests (PRs):** PR titles, summaries, walkthroughs, review comments, and merge summaries.
- **Issues & Discussions:** Bug reports, feature proposals, task lists, and comment threads.
- **Documentation:** `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `ARCHITECTURE.md`, inline code guides, and doc files.
- **Source Code:** Function/class/variable names, type annotations, docstrings, and inline code comments.
- **Configuration & Scripts:** Comments in Dockerfiles, GitHub Actions workflows, YAML configs, shell scripts, and Makefiles.
- **Release Notes:** GitHub Releases, changelog entries, and package distribution metadata.

---

## 2. Language Separation: Native Chat Freedom vs. English Repository

### Golden Rule: Never Force the User to Speak English in Chat
Developers who clone and use this repository are 100% free to converse with AI agents in whatever natural language they prefer (e.g., Hungarian, German, French, Spanish, Japanese, etc.).

- **In the Chat Interface:** The AI agent MUST converse, explain, reason, and answer in the developer's language of choice. The agent must **NEVER** demand, require, or ask the user to switch to English in the dialogue.
- **In Repository Files & Git Metadata:** The AI agent acts as a seamless bilingual bridge: it understands instructions in the user's language, but authors/updates code, comments, docstrings, documentation, and Git commits strictly in English.

| Context | Permitted Language | Examples & Rules |
|---|---|---|
| **User Chat / Dialogue** | **User's Choice (Any)** | User asks questions or issues tasks in Hungarian; Agent answers in Hungarian. |
| **Agent Chat Responses** | **User's Choice (Any)** | Agent explains architecture, reports test results, and guides in the user's language. |
| **Git Commits & History** | **English ONLY** | Commit subject & body: `docs: expand remote linux jumpbox ssh guide`. |
| **Source Code & Comments** | **English ONLY** | Variable names, function definitions, docstrings, and comments in English. |
| **Documentation & Skills** | **English ONLY** | `README.md`, `AGENTS.md`, and `.agents/skills/...` files in English. |
| **GitHub PRs & Issues** | **English ONLY** | PR titles, descriptions, and issue tickets in English for global collaboration. |

> [!CRITICAL]
> **Summary for AI Agents:**
> 1. Do NOT force the user to speak English. If the user prompts in Hungarian, respond in Hungarian.
> 2. Do NOT write non-English text into git commits, code comments, docstrings, or repository markdown files. Translate behind the scenes into English.

---

## 3. Git Commit Message Standards

All commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification in English.

### Format:
```text
<type>(<optional scope>): <imperative summary in present tense>

[optional body explaining WHY and WHAT changed, in English]

[optional footer(s), e.g. Closes #123]
```

### Allowed Types:
- `feat`: A new user-facing feature or tool.
- `fix`: A bug fix.
- `docs`: Documentation changes only.
- `style`: Changes that do not affect the meaning of the code (formatting, white-space).
- `refactor`: A code change that neither fixes a bug nor adds a feature.
- `perf`: A code change that improves performance.
- `test`: Adding missing tests or correcting existing tests.
- `build`: Changes that affect the build system or external dependencies.
- `ci`: Changes to CI configuration files and scripts.
- `chore`: Routine maintenance tasks, repo tooling, or administrative updates.

### Grammatical Rules:
1. **Imperative Mood, Present Tense:**
   - ✅ `add safe mode check for vm stop`
   - ❌ `added safe mode check for vm stop` (past tense)
   - ❌ `vm leállítás jóváhagyás hozzáadva` (non-English)
2. **No Trailing Period in Subject Line:** Keep subject lines clean and concise (under 72 characters).
3. **Multi-line Bodies:** Use paragraph breaks to explain the rationale, context, and edge cases addressed.

---

## 4. Pre-Commit / Pre-Submission Checklist

Before staging, committing, or pushing to GitHub, execute this checklist:

1. **Diff Inspection:**
   ```bash
   git diff
   ```
   Scan all modified lines for accidental non-English comments, docstrings, or debug prints.

2. **Commit Message Validation:**
   Ensure the commit message:
   - Is 100% in English.
   - Follows `<type>(<scope>): <summary>` format.
   - Does not contain typos or informal slang.

3. **Code Quality Gates:**
   Ensure the repository quality gates pass before committing:
   ```bash
   ruff check .
   ruff format --check .
   mypy src tests
   pytest
   ```

4. **Pull Request Verification:**
   When generating PR templates or descriptions, provide:
   - English title matching the primary commit or feature.
   - Clear markdown sections: `## Description`, `## Motivation & Context`, `## How Has This Been Tested?`, and `## Checklist`.
