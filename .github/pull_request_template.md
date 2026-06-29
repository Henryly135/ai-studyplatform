<!--
PR title must use the same format as commit titles:
type(scope): summary

Examples:
feat(ai): add provider settings
fix(auth): handle expired reset tokens
ci(workflow): enforce commit and PR templates
docs(testing): document PR workflow
-->

## Summary

- 

## Change Type

- [ ] `feat` - user-facing feature
- [ ] `fix` - bug fix
- [ ] `refactor` - internal structure change
- [ ] `test` - test-only change
- [ ] `docs` - documentation-only change
- [ ] `ci` - workflow or automation change
- [ ] `chore` - maintenance change

## Tests

- [ ] Added or updated backend tests in the relevant service `tests/` directory, or this change does not affect backend behavior.
- [ ] Added or updated frontend tests when a frontend test runner exists, or covered the change with `npm run lint` and `npm run build`.
- [ ] AI-related behavior uses mocked providers in tests and does not require real API keys in CI.
- [ ] Ran the relevant local checks:
  - [ ] `./scripts/check-git-conventions.sh`
  - [ ] `./scripts/run-backend-tests.sh`
  - [ ] `npm --prefix frontend run lint`
  - [ ] `npm --prefix frontend run build`
  - [ ] `docker compose --env-file .env.example -f infra/docker-compose.yml config --quiet`

## Checklist

- [ ] This PR targets `develop`, or it is a release PR from `develop` to `main`.
- [ ] The branch contains one module or one focused maintenance change.
- [ ] Commit titles follow `type(scope): summary`.
- [ ] Documentation is updated in Chinese and English when behavior or setup changes.

## Notes

- 
