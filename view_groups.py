from config.user_roles import pages_for_role, get_user_role

# Every page the app has, tagged with the role-permission key it needs (see
# config/user_roles.py ROLE_PAGES) and which sidebar group it's shown under.
PAGE_REGISTRY = [
    {
        "key": "monthly_intake",
        "group": "Submit KRI",
        "label": "Submit / Edit KRI Value",
        "page": "views/kri_monthly_intake.py",
        "icon": ":material/edit_note:",
    },
    {
        "key": "review_submissions",
        "group": "Review",
        "label": "Review Submitted KRIs",
        "page": "views/kri_review_submissions.py",
        "icon": ":material/fact_check:",
    },
    {
        "key": "dashboard",
        "group": "Dashboard",
        "label": "KRI Overview",
        "page": "views/kri_dashboard.py",
        "icon": ":material/dashboard:",
    },
    {
        "key": "catalog_add",
        "group": "Administration",
        "label": "Add a KRI",
        "page": "views/kri_catalog_add.py",
        "icon": ":material/add_circle:",
    },
    {
        "key": "catalog_manage",
        "group": "Administration",
        "label": "Manage Existing KRIs",
        "page": "views/kri_catalog_manage.py",
        "icon": ":material/folder_managed:",
    },
    {
        "key": "lookup_admin",
        "group": "Administration",
        "label": "Lookup Values",
        "page": "views/kri_lookup_admin.py",
        "icon": ":material/tune:",
    },
    {
        "key": "user_role_admin",
        "group": "Administration",
        "label": "User Role Manager",
        "page": "views/user_role_admin.py",
        "icon": ":material/manage_accounts:",
    },
]

ACCESS_DENIED_GROUPS = [
    {
        "title": "Access",
        "views": [
            {
                "label": "Access Denied",
                "page": "views/access_denied.py",
                "icon": ":material/lock:",
            }
        ],
    }
]


def get_groups_for_user(user_email: str) -> list[dict]:
    """Sidebar groups/pages for this user's role. See config/user_roles.py for the
    role -> page-key permission matrix."""
    allowed = pages_for_role(get_user_role(user_email))
    if not allowed:
        return ACCESS_DENIED_GROUPS

    groups: dict[str, list[dict]] = {}
    for entry in PAGE_REGISTRY:
        if entry["key"] in allowed:
            groups.setdefault(entry["group"], []).append(entry)

    return [{"title": title, "views": views} for title, views in groups.items()]
