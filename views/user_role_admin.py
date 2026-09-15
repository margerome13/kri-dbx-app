import streamlit as st

from config.user_roles import BOOTSTRAP_ADMINS, VALID_ROLES
from utils.access import require_page_access
from utils.audit import log_change
from utils.db import (
    TBL_USER_ROLES,
    build_delete,
    build_merge_upsert,
    current_user_email,
    now_utc,
    run_query,
    run_statement,
)
from utils.forms import bump_and_rerun, form_gen, render_pending_banner, show_message

require_page_access("user_role_admin")

st.header("User Role Manager", divider=True)
st.write(
    "Control who can use this app and what they can see. Changes here take effect "
    "immediately -- no code change or redeploy needed."
)

if BOOTSTRAP_ADMINS:
    st.caption(
        "Built-in safety net: "
        + ", ".join(f"`{a}`" for a in BOOTSTRAP_ADMINS)
        + " will always have ADMIN access regardless of what's in this table, so "
        "the team can never be fully locked out."
    )

roles_df = run_query(
    f"SELECT user_email, role, assigned_by, assigned_at, updated_by, updated_at "
    f"FROM {TBL_USER_ROLES} ORDER BY role, user_email"
)
st.dataframe(roles_df, use_container_width=True, hide_index=True)

admin_emails_in_table = (
    set(roles_df.loc[roles_df["role"] == "ADMIN", "user_email"].str.lower())
    if not roles_df.empty
    else set()
)


def blocks_last_admin(target_email: str, new_role) -> bool:
    """True if this change would remove the last ADMIN row from the table.
    (BOOTSTRAP_ADMINS still protects against a total lockout either way -- this is
    a softer safeguard so day-to-day admin work doesn't always fall back to it.)"""
    target = target_email.lower()
    if target not in admin_emails_in_table:
        return False
    remaining = admin_emails_in_table - {target}
    return len(remaining) == 0 and new_role != "ADMIN"


tab_upsert, tab_remove = st.tabs(["Add / update a user", "Remove a user"])

with tab_upsert:
    gen = form_gen("user_role_upsert")
    with st.form(f"user_role_upsert_form_{gen}"):
        banner = st.empty()

        email_input = st.text_input("User email", key=f"user_role_email_{gen}")
        role_input = st.selectbox("Role", VALID_ROLES, key=f"user_role_role_{gen}")

        submitted = st.form_submit_button("Save", type="primary")
        bottom_banner = st.empty()
        render_pending_banner("user_role_upsert", banner, bottom_banner)

        if submitted:
            errors = []
            email_clean = email_input.strip()
            if not email_clean:
                errors.append("User email is required.")
            elif "@" not in email_clean:
                errors.append("That doesn't look like a valid email address.")
            elif blocks_last_admin(email_clean, role_input):
                errors.append(
                    f"'{email_clean}' is the only ADMIN in this table. Add another "
                    f"ADMIN before changing this one's role."
                )

            if errors:
                show_message("error", "\n".join(f"- {e}" for e in errors), banner, bottom_banner)
            else:
                user = current_user_email()
                existing = roles_df[roles_df["user_email"].str.lower() == email_clean.lower()]
                row = {
                    "user_email": email_clean,
                    "role": role_input,
                    "assigned_by": existing.iloc[0]["assigned_by"] if not existing.empty else user,
                    "assigned_at": existing.iloc[0]["assigned_at"] if not existing.empty else now_utc(),
                    "updated_by": user,
                    "updated_at": now_utc(),
                }
                run_statement(build_merge_upsert(TBL_USER_ROLES, row, key_columns=["user_email"]))
                log_change(
                    table_name="kri_user_roles",
                    record_key=email_clean,
                    action="UPDATE" if not existing.empty else "INSERT",
                    changed_by=user,
                    before=None if existing.empty else existing.iloc[0].to_dict(),
                    after=row,
                )
                bump_and_rerun("user_role_upsert", f"'{email_clean}' is now {role_input}.")

with tab_remove:
    if roles_df.empty:
        st.info("No users in the role table yet.")
    else:
        with st.form("user_role_remove_form"):
            remove_banner = st.empty()

            email_to_remove = st.selectbox(
                "User to remove",
                roles_df["user_email"].tolist(),
                format_func=lambda e: f"{e} ({roles_df.loc[roles_df['user_email'] == e, 'role'].iloc[0]})",
            )
            remove_submitted = st.form_submit_button("Remove access", type="primary")
            remove_bottom_banner = st.empty()
            render_pending_banner("user_role_remove", remove_banner, remove_bottom_banner)

            if remove_submitted:
                if blocks_last_admin(email_to_remove, None):
                    show_message(
                        "error",
                        f"'{email_to_remove}' is the only ADMIN in this table. Add "
                        f"another ADMIN before removing this one.",
                        remove_banner,
                        remove_bottom_banner,
                    )
                else:
                    user = current_user_email()
                    before_row = roles_df.loc[roles_df["user_email"] == email_to_remove].iloc[0].to_dict()
                    run_statement(build_delete(TBL_USER_ROLES, {"user_email": email_to_remove}))
                    log_change(
                        table_name="kri_user_roles",
                        record_key=email_to_remove,
                        action="DELETE",
                        changed_by=user,
                        before=before_row,
                    )
                    bump_and_rerun("user_role_remove", f"Removed '{email_to_remove}'.", bump=False)
