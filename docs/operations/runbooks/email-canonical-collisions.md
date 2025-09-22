# Email canonical collision remediation

## Purpose

Handle failures raised by migration `8b0c1d2e3f45_add_user_email_canonical` when multiple
users collapse to the same canonical email address.

## When to run

- Alembic upgrade stops with `Cannot add users.email_canonical unique constraint`. The
  error message includes the canonical address and the conflicting user IDs.
- Operators report missing or misrouted logins immediately after deploying the
  migration.

## Steps

1. **Inspect the conflicts**
   - Review the migration error message to identify the canonical email and affected
     `user_id` values.
   - Query the database for the original `users.email` values:

     ```sql
     SELECT user_id, email
     FROM users
     WHERE user_id IN ('01H...', '01J...')
     ORDER BY user_id;
     ```

2. **Choose a remediation path**
   - Prefer merging duplicate accounts into the record that owns production data
     (jobs, documents, configuration history).
   - If the duplicates represent test data, delete the unused records.
   - When both accounts must remain, change one email to a unique, valid address and
     communicate the update to the owner. Avoid inventing provider-specific rewrites
     (`+tags`, dot removal) because those can still collide later.

3. **Apply the fix**
   - Use the ADE CLI (`python -m backend.app auth set-password ...`) or a SQL UPDATE to
     change the secondary account's email.
   - Re-run `alembic upgrade head`. The migration recomputes `email_canonical` values and
     enforces the new uniqueness constraint.

4. **Audit and document**
   - Record the actions taken in your change log or incident tracker, including the
     affected accounts and any credential resets performed.
   - Notify the impacted operators so they know which email address to use going
     forward.

## Validation

- `SELECT COUNT(*) FROM users WHERE email_canonical IS NULL;` returns `0`.
- Duplicate canonical emails are no longer present:

  ```sql
  SELECT email_canonical, COUNT(*)
  FROM users
  GROUP BY email_canonical
  HAVING COUNT(*) > 1;
  ```

  The query should return zero rows.
- Manual sign-ins succeed with either original casing.

