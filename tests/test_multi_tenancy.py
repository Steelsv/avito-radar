import pytest
import os
from avito_radar.storage.db import (
    SearchRecord,
    save_search,
    load_search,
    list_searches,
    delete_search,
)


def test_multi_tenancy_storage_isolation():
    u1 = "test_user_111"
    u2 = "test_user_222"

    s1 = SearchRecord(
        name=f"u{u1}_iphone15_chelyabinsk",
        title="iPhone 15",
        category_type="goods",
        catalog_url="https://www.avito.ru/chelyabinsk?q=iphone+15",
        city="Челябинск",
        params={"q": "iphone 15"},
        user_id=u1,
    )
    s2 = SearchRecord(
        name=f"u{u2}_rtx4070_chelyabinsk",
        title="RTX 4070",
        category_type="goods",
        catalog_url="https://www.avito.ru/chelyabinsk?q=rtx+4070",
        city="Челябинск",
        params={"q": "rtx 4070"},
        user_id=u2,
    )

    save_search(s1)
    save_search(s2)

    try:
        u1_searches = list_searches(user_id=u1)
        u2_searches = list_searches(user_id=u2)

        assert any(s.name == s1.name for s in u1_searches)
        assert not any(s.name == s2.name for s in u1_searches)

        assert any(s.name == s2.name for s in u2_searches)
        assert not any(s.name == s1.name for s in u2_searches)

        # Deletion cross-user protection
        assert delete_search(s1.name, user_id=u2) is False
        assert load_search(s1.name) is not None

        # Author can delete
        assert delete_search(s1.name, user_id=u1) is True
        assert load_search(s1.name) is None

    finally:
        delete_search(s1.name, user_id=u1)
        delete_search(s2.name, user_id=u2)
