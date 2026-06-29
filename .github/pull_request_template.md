## Summary

- 

## Tests

- [ ] Added or updated backend tests in the relevant service `tests/` directory, or this change does not affect backend behavior.
- [ ] Added or updated frontend tests when a frontend test runner exists, or covered the change with `npm run lint` and `npm run build`.
- [ ] AI-related behavior uses mocked providers in tests and does not require real API keys in CI.
- [ ] Ran the relevant local checks:
  - `./scripts/run-backend-tests.sh`
  - `npm --prefix frontend run lint`
  - `npm --prefix frontend run build`
  - `docker compose --env-file .env.example -f infra/docker-compose.yml config --quiet`

## Notes

- 
