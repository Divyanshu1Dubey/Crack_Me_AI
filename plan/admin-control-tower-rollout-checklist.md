# Admin Control Tower Rollout and Rollback Checklist

## Pre-Deployment

- Confirm backend migrations are generated and applied in staging.
- Run backend validation: `python manage.py check`.
- Run backend tests: `python manage.py test accounts questions`.
- Run frontend quality gates: `npm run lint` and `npm run build` from `frontend/`.
- Validate admin roles and permissions with at least one admin and one student account.
- Confirm environment throttles are configured:
  - `DRF_THROTTLE_ANON`
  - `DRF_THROTTLE_USER`
  - `DRF_THROTTLE_ADMIN_CONTROL_TOWER`

## Rollout Steps

1. Deploy backend release with new migrations and admin APIs.
2. Apply migrations: `python manage.py migrate`.
3. Smoke-check critical admin APIs:
   - `/api/analytics/admin/weak-area-control/`
   - `/api/analytics/admin/campaigns/`
   - `/api/questions/feedback/admin-queue/`
   - `/api/questions/<id>/revisions/`
4. Deploy frontend release with control tower tab implementations.
5. Validate admin page tabs in production:
   - Analytics
   - Moderation
   - Broadcast
   - Audit
   - AI (revision diff/undo)
6. Monitor logs and error rate for 30 minutes after deployment.

## Rollback Steps

1. Freeze admin writes (temporary maintenance banner or access restriction).
2. Revert frontend deployment to previous known-good build.
3. Revert backend deployment to previous image/release.
4. If required, roll back schema only for newly introduced nullable-safe fields.
5. Re-run smoke checks on legacy admin endpoints.
6. Post incident summary with:
   - failure trigger
   - user impact
   - corrective actions

## Operational Watchpoints

- Queue growth for extraction jobs in `QuestionImportJob`.
- Audit log continuity for admin actions.
- Campaign send-now execution and delivery counts.
- Moderation queue status transitions (`new -> in_progress -> resolved`).
