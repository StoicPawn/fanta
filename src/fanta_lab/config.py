from __future__ import annotations

import os


def get_secret(name: str, explicit: str | None = None) -> str | None:
    """Resolve a secret without ever persisting it in the repository.

    Priority: explicit UI/runtime value -> Streamlit secrets -> environment variable.
    Importing streamlit is optional so the core package remains usable in tests/CLI.
    """
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    try:
        import streamlit as st
        try:
            value = st.secrets.get(name)
            if value:
                return str(value).strip()
        except Exception:
            pass
    except Exception:
        pass
    value = os.getenv(name)
    return str(value).strip() if value else None


def secret_status(name: str, explicit: str | None = None) -> str:
    if explicit and str(explicit).strip():
        return "session"
    try:
        import streamlit as st
        try:
            if st.secrets.get(name):
                return "streamlit-secret"
        except Exception:
            pass
    except Exception:
        pass
    return "environment" if os.getenv(name) else "missing"
