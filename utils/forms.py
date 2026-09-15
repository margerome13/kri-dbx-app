"""Keeps every form in the app behaving the same way:

- A failed submission never loses what the user typed: validation errors are
  written directly into banner placeholders pinned to the TOP and BOTTOM of the form
  (one right before its first field, one right after its submit button), with no
  rerun and no widget key change -- Streamlit keeps every field exactly as the user
  left it. Two banners so the message is visible whether the user is looking at the
  top of a long form or has scrolled down to the submit button.
- A successful "add a new record" form blanks itself for the next entry: its
  widgets are keyed with a per-form generation counter that gets bumped on
  success, forcing Streamlit to re-mount them with blank defaults. The
  confirmation message survives the resulting rerun via a one-shot session_state
  entry, shown in those same top/bottom banners.

Usage in a view:
    with st.form(...):
        banner = st.empty()                    # reserves the TOP slot
        ... fields ...
        st.form_submit_button(...)
        bottom_banner = st.empty()              # reserves the BOTTOM slot
        render_pending_banner(namespace, banner, bottom_banner)
        if submitted:
            if errors:
                show_message("error", "...", banner, bottom_banner)
            else:
                bump_and_rerun(namespace, "Saved.")
Both st.empty() calls must happen before render_pending_banner()/show_message() so
both slots exist -- but the content can be written into them at any later point in
the script; Streamlit renders each slot in the position it was reserved, not the
position it was last written from.
"""
import streamlit as st


def form_gen(namespace: str) -> int:
    """Current generation for this form's widget keys. Bump via bump_and_rerun()."""
    return st.session_state.get(f"_{namespace}_gen", 0)


def bump_and_rerun(namespace: str, message: str, bump: bool = True) -> None:
    """Call right after a successful write.

    Reruns the page so anything queried earlier in the script (dropdown options,
    tables) reflects the change, and shows `message` once in this form/section's
    banners via render_pending_banner(). Set bump=False for a form that should keep
    showing its current values after saving (e.g. editing an existing record)
    rather than blanking itself.
    """
    if bump:
        st.session_state[f"_{namespace}_gen"] = form_gen(namespace) + 1
    st.session_state[f"_{namespace}_pending_msg"] = message
    st.rerun()


def render_pending_banner(namespace: str, *placeholders) -> None:
    """Call once all of this form's banner placeholder(s) have been created (e.g.
    one at the top, one at the bottom), to show a message left by bump_and_rerun()
    in every one of them."""
    message = st.session_state.pop(f"_{namespace}_pending_msg", None)
    if message:
        show_message("success", message, *placeholders)


def show_message(kind: str, message: str, *placeholders) -> None:
    """Write `message` into every placeholder given (kind: 'error', 'success',
    'info', 'warning'), so it shows up regardless of where the user has scrolled."""
    for placeholder in placeholders:
        getattr(placeholder, kind)(message)
