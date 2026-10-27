# PayTrack — Payment Tracking Application

A learning/demo multi-container app with Nginx frontend, Flask API, PostgreSQL, Redis, and a Python worker.

**Demo only:** This does not process payments or move money. Use fake data only.

## Run locally
1. Install Docker Engine and Docker Compose v2.
2. Copy `.env.example` to `.env`.
3. Change the example password in `.env`.
4. Run `docker compose up --build -d`.
5. Open `http://localhost:8080`.
6. Inspect with `docker compose ps` and `docker compose logs -f api worker`.
7. Stop with `docker compose down`. This keeps database volumes. `docker compose down -v` deletes persisted data.

## API
- `GET /api/health/live`
- `GET /api/health/ready`
- `GET /api/payments`
- `POST /api/payments`
- `GET /api/payments/<id>`
- `PATCH /api/payments/<id>/status`

Example:
```bash
curl -X POST http://localhost:8080/api/payments -H "Content-Type: application/json" -d '{"customer_name":"Ada Demo","amount":12500,"currency":"NGN","reference":"PAY-DEMO-001"}'
```

## Cloud engineer notes
- CI workflow tests and builds images; it does not deploy automatically.
- `.github/workflows/deploy.yml.example` is a template, not an active workflow. Review and configure it before use.
- The AWS template assumes EC2 has Docker, Git, SSM Agent, an appropriate instance role, and a checkout at `/opt/paytrack`. Its deployment process needs review and testing.
- No authentication, TLS, production secrets handling, or payment gateway is included. Do not expose this starter publicly with real or sensitive data.
