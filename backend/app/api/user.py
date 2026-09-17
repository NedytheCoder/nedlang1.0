"""Saving a learner's own row. The only route that writes to `users` today.

Rule 10 step 1 — "a user can exist". Clerk knows who signed up; this is what
puts them in our database, together with the two onboarding answers from
product.md M2. It is the answer to the question the rest of the backend has been
waiting on: how does a `users` row ever get created?

Nothing else lives in this module on purpose. Reading a profile, changing an
email, deleting an account — none of those exist yet, and none of them belong
here merely because they would also touch this table (Rule 2).

The part worth reading twice is how this gets past row-level security. Every
other write announces who it is first; a signup has nobody to announce. But
`users_self` in schema.sql permits a row whose id equals app.current_user_id,
for writes as well as reads — so we mint the id, announce that, and then insert
it. The policy is satisfied, not bypassed: the row being created really is the
caller's own. Measured 2026-09-16 — with the identity set to any *other* id the
identical INSERT is refused, which is what makes this safe. No bootstrap policy,
no second session variable, no SECURITY DEFINER.
"""

from __future__ import annotations 

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import clerk_email, current_clerk_id
from app.db import cursor

router = APIRouter()


class UserInfo(BaseModel):
    """The two onboarding answers and the reminder opt-in. Nothing else.

    id, clerk_id and email are absent from this model deliberately. They are
    identity, and identity comes from the verified token and from Clerk — never
    from the request body (Rule 7). A learner can say what they want to practise;
    they cannot say who they are.

    The lengths are bounds, not validation: these are free-text answers, and a
    text column with no ceiling accepts a megabyte.
    """

    goal: str = Field(min_length=1, max_length=500)       # "order food on holiday"
    comfort: str = Field(min_length=1, max_length=500)    # "I freeze up"
    email_reminders: bool = False                         # opt-in, default off (Rule 6)


@router.post("/api/user")
def save_user(info: UserInfo, clerk_id: str = Depends(current_clerk_id)) -> dict:
    """Create this learner's row, or update it if they already have one.

    Calling it twice is fine and expected — onboarding can be resubmitted, and
    the second call updates instead of duplicating.

    One case is knowingly not handled: two of these arriving at the same instant
    for a learner who has no row yet. Both would find none, both would insert,
    and the loser gets a unique violation on clerk_id. Recovering inside the
    request needs a second transaction, which is more machinery than a
    double-click is worth — the retry finds the row and takes the update path
    (Rule 1).
    """ 
    with cursor() as cur:
        cur.execute("SELECT app_resolve_user(%s)", (clerk_id,))
        row = cur.fetchone()
        existing = row[0] if row else None

        if existing:
            # set_config(..., true) is SET LOCAL as a function call: psycopg3
            # binds parameters server-side and SET accepts no bound parameter.
            cur.execute("SELECT set_config('app.current_user_id', %s, true)", (existing,))
            cur.execute(
                "UPDATE users SET goal = %s, comfort = %s, email_reminders = %s WHERE id = %s",
                (info.goal, info.comfort, info.email_reminders, existing),
            )
            return {"created": False}

        # Ids are minted here, not by the database, so the row can be named
        # before it exists — which is exactly what the policy needs.
        user_id = "u_" + uuid.uuid4().hex[:10]
        cur.execute("SELECT set_config('app.current_user_id', %s, true)", (user_id,))
        cur.execute(
            "INSERT INTO users (id, clerk_id, email, goal, comfort, email_reminders)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, clerk_id, clerk_email(clerk_id), info.goal, info.comfort,
             info.email_reminders),
        )
        return {"created": True}
