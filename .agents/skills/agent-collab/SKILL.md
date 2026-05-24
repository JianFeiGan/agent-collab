```markdown
# agent-collab Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the core development patterns and conventions used in the `agent-collab` TypeScript codebase. You'll learn about file naming, import/export styles, commit message conventions, and how to write and organize tests. While no explicit workflows or frameworks are detected, this guide will help you maintain consistency and quality in your contributions.

## Coding Conventions

### File Naming
- **Style:** kebab-case  
  Example:  
  ```
  agent-handler.ts
  user-profile.test.ts
  ```

### Import Style
- **Relative imports** are used for referencing local files.  
  Example:
  ```typescript
  import { Agent } from './agent';
  import { getUserProfile } from '../utils/user-profile';
  ```

### Export Style
- **Named exports** are preferred over default exports.  
  Example:
  ```typescript
  // In agent.ts
  export function createAgent() { ... }
  export const AGENT_VERSION = '1.0.0';

  // In another file
  import { createAgent, AGENT_VERSION } from './agent';
  ```

### Commit Messages
- **Conventional commits** are used, with prefixes like `docs` and `chore`.
- **Format:** `<type>(optional scope): <description>`
- **Average length:** ~64 characters  
  Example:
  ```
  docs(readme): update usage instructions for agent setup
  chore: upgrade TypeScript to v4.8.3
  ```

## Workflows

### Commit Workflow
**Trigger:** When making any code or documentation change  
**Command:** `/commit`

1. Make your code or documentation changes.
2. Stage your changes with `git add`.
3. Write a conventional commit message, e.g.,  
   ```
   docs(api): add usage example for createAgent
   ```
4. Commit your changes.

### Testing Workflow
**Trigger:** Before pushing or merging code  
**Command:** `/test`

1. Identify test files matching the `*.test.*` pattern.
2. Run your test runner (framework is unknown; use your project's standard).
   ```
   # Example with Jest (if used)
   npx jest
   ```
3. Ensure all tests pass before pushing.

## Testing Patterns

- **File naming:** Test files use the `*.test.*` pattern, e.g., `agent-handler.test.ts`.
- **Framework:** Not explicitly detected. Use your project's standard test runner.
- **Organization:** Place tests alongside implementation files or in a dedicated `tests` directory.

**Example test file:**
```typescript
// agent-handler.test.ts
import { createAgent } from './agent-handler';

describe('createAgent', () => {
  it('should create an agent with default config', () => {
    const agent = createAgent();
    expect(agent).toBeDefined();
  });
});
```

## Commands
| Command   | Purpose                                      |
|-----------|----------------------------------------------|
| /commit   | Guide for making conventional commits        |
| /test     | Steps to run and verify tests                |
```
