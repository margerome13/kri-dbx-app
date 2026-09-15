"""Keeps every form in the app behaving the same way:

- A failed submission never loses what the user typed: validation errors are
  written directly into a banner placeholder pinned to the TOP of the form (before
  any of its fields), with no rerun and no widget key change -- Streamlit keeps
  every field exactly as the user left it.
- A successful "add a new record" form blanks itself for the next entry: its
  widgets are keyed with a per-form generation counter that gets bumped on
  success, forcing Streamlit to re-mount them with blank defaults. The
  confirmation message survives the resulting rerun via a one-shot session_state
  entry, shown in that same top-of-form banner.
"""
import streamlit as st


def form_gen(namespace: str) -> int:
    """Current generation for this form's widget keys. Bump via bump_and_rerun()."""
    return st.session_state.get(f"_{namespace}_gen", 0)


def bump_and_rerun(namespace: str, message: str, bump: bool = True) -> None:
    """Call right after a successful write.

    Reruns the page so anything queried earlier in the script (dropdown options,
    tables) reflects the change, and shows `message` once at the top of this
    form/section via render_pending_banner(). Set bump=False for a form that
    should keep showing its current values after saving (e.g. editing an existing
    record) rather than blanking itself.
    """
    if bump:
        st.session_state[f"_{namespace}_gen"] = form_gen(namespace) + 1
    st.session_state[f"_{namespace}_pending_msg"] = message
    st.rerun()


def render_pending_banner(namespace: str, placeholder) -> None:
    """Call once near the top of the form/section, right after creating its
    st.empty() placeholder, to show a message left by bump_and_rerun()."""
    message = st.session_state.pop(f"_{namespace}_pending_msg", None)
    if message:
        placeholder.success(message)
