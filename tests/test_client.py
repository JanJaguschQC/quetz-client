import re

import pytest
from dacite import from_dict

from quetz_client.client import Channel, ChannelMember, QuetzClient

from .conftest import temporary_package_file


def test_yield_channels(client: QuetzClient, expected_channels):
    channels = list(client.yield_channels(limit=2))
    assert len(channels) == 4
    assert isinstance(channels[0], Channel)
    assert {from_dict(Channel, c) for c in expected_channels} == set(channels)


def test_yield_channel_members(client: QuetzClient, expected_channel_members):
    channel = "a"
    channel_members = set(client.yield_channel_members(channel=channel))
    assert {
        from_dict(ChannelMember, ecm) for ecm in expected_channel_members
    } == channel_members


def test_yield_users(client: QuetzClient, expected_users):
    users = list(client.yield_users())
    user_set = {(user.id, user.username) for user in users}
    expected_set = {(user["id"], user["username"]) for user in expected_users["result"]}
    assert user_set == expected_set


@pytest.mark.parametrize(
    "role",
    [
        None,
        "member",
        "maintainer",
        "owner",
    ],
)
def test_mock_get_role(
    mock_client: QuetzClient,
    role,
    requests_mock,
    mock_server: str,
):
    username = "user"
    url = f"{mock_server}/api/users/{username}/role"
    requests_mock.get(url, json={"role": role})
    actual_role = mock_client.get_role(username)
    assert next(actual_role).role == role


def test_live_get_role(
    live_client: QuetzClient,
    live_alice_role,
):
    actual_role = live_client.get_role("alice")
    assert actual_role.role == live_alice_role


@pytest.mark.parametrize(
    "role",
    [
        None,
        "member",
        "maintainer",
        "owner",
    ],
)
def test_set_channel_member(
    mock_client: QuetzClient,
    role,
    requests_mock,
    mock_server: str,
):
    channel = "a"
    username = "user"

    url = f"{mock_server}/api/channels/{channel}/members"
    requests_mock.post(url, json=None)

    mock_client.set_channel_member(username, role, channel)

    last_request = requests_mock.request_history[0]
    assert last_request.method == "POST"
    assert last_request.json()["username"] == username
    assert last_request.json()["role"] == role


def test_mock_delete_channel_member(
    mock_client: QuetzClient,
    requests_mock,
    mock_server: str,
):
    channel = "a"
    username = "a"

    url = f"{mock_server}/api/channels/{channel}/members"
    requests_mock.delete(url, json=None)

    mock_client.delete_channel_member(username, channel)

    last_request = requests_mock.request_history[0]
    assert last_request.method == "DELETE"
    assert last_request.qs["username"] == [username]
    assert len(last_request.qs) == 1


def test_live_delete_channel_member(
    authed_session,
    live_client: QuetzClient,
    live_post_channel_members,
):
    # Check that alice is a member of channel a
    channel = "a"
    username = "alice"

    response = authed_session.get(
        f"{live_client.url}/api/channels/{channel}/members",
    )
    assert {u["user"]["username"] for u in response.json()} == {"alice", "bob"}

    live_client.delete_channel_member(username, channel)

    # Check that alice is no longer a member of channel a
    response = authed_session.get(
        f"{live_client.url}/api/channels/{channel}/members",
    )
    assert {u["user"]["username"] for u in response.json()} == {"bob"}


@pytest.mark.parametrize(
    "role",
    [
        None,
        "member",
        "maintainer",
        "owner",
    ],
)
def test_set_role(
    mock_client: QuetzClient,
    role,
    requests_mock,
    mock_server: str,
):
    username = "user"

    url = f"{mock_server}/api/users/{username}/role"
    requests_mock.put(url, json=None)

    mock_client.set_role(username, role)

    last_request = requests_mock.request_history[0]
    assert last_request.method == "PUT"
    assert last_request.json()["role"] == role
    assert len(last_request.json()) == 1


def test_from_token():
    token = "abc"
    quetz_client = QuetzClient.from_token("", token)
    assert quetz_client.session.headers.get("X-API-Key") == token


def test_set_channel(
    mock_client: QuetzClient,
    requests_mock,
    mock_server: str,
):
    channel = "a"

    url = f"{mock_server}/api/channels"
    requests_mock.post(url, json=None)

    mock_client.set_channel(channel)

    last_request = requests_mock.request_history[0]
    assert last_request.method == "POST"
    assert last_request.json()["name"] == channel


def test_delete_channel(
    mock_client: QuetzClient,
    requests_mock,
    mock_server: str,
):
    channel = "a"

    url = f"{mock_server}/api/channels/{channel}"
    requests_mock.delete(url, json=None)

    mock_client.delete_channel(channel)

    last_request = requests_mock.request_history[0]
    assert last_request.method == "DELETE"


def test_yield_packages(mock_client: QuetzClient, expected_packages):
    channel = "channel1"
    package_set = {
        (p.name, p.url, p.current_version) for p in mock_client.yield_packages(channel)
    }
    assert {
        (ep["name"], ep["url"], ep["current_version"])
        for ep in expected_packages["result"]
    } == package_set


def test_post_file_to_channel(
    mock_client: QuetzClient,
    requests_mock,
    mock_server: str,
):
    channel = "a"

    url_matcher = re.compile(
        f"{mock_server}/api/channels/{channel}/upload/\\w*\\?force=False&sha256=\\w*"
    )
    requests_mock.register_uri("POST", url_matcher, json=None)

    requests_mock.register_uri(
        "GET",
        "https://conda.anaconda.org/conda-forge/linux-64/xtensor-0.16.1-0.tar.bz2",
        real_http=True,
    )

    # breakpoint()

    with temporary_package_file() as file:
        mock_client.post_file_to_channel(channel, file)

    # the last request here is the download of the test package file, thus we need to access the second-to-last request
    last_request = requests_mock.request_history[1]
    assert last_request.method == "POST"
