import pytest

from humanapi_api import house
from humanapi_api.pricing import NOT_US, parse_task


@pytest.mark.parametrize("text", ["Is this shop in Pune open today?", "Price in rupees", "Pay with UPI", "Call +91 98765 43210", "Cost is ₹500", "Check the listing on Flipkart"])
def test_tasks_naming_india_are_refused(text):
    with pytest.raises(ValueError, match="United States only"):
        parse_task({"type": "answer", "payload": {"question": text}})


def test_us_task_is_accepted_and_location_must_be_a_us_state():
    assert parse_task({"type": "answer", "payload": {"question": "Is the Austin public library open on Sundays?"}, "location": "Austin, TX"}).location == "Austin, TX"
    with pytest.raises(ValueError):
        parse_task({"type": "answer", "payload": {"question": "Is the library open on Sundays?"}, "location": "Mumbai, MH"})


def test_whole_catalogue_is_us_only():
    for item in house.catalogue():
        assert not NOT_US.search(str(item))


def test_no_link_depends_on_where_the_visitor_is():
    from humanapi_api.catalogue import STARTER_TASKS

    text = str(house.catalogue()) + str(STARTER_TASKS)
    assert "craigslist.org/\"" not in text.replace("'", "\"")  # that address forwards each visitor to their own nearest city
