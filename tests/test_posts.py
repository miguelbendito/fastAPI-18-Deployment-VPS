import pytest
from httpx import AsyncClient

from tests.conftest import auth_header, create_test_user, login_user

@pytest.mark.anyio
async def test_get_post_empty(client: AsyncClient):
    response = await client.get("api/posts")

    assert response.status_code == 200
    data = response.json()
    assert data["posts"] == []
    assert data["total"] == 0
    assert data["has_more"] is False

@pytest.mark.anyio
async def test_create_post_success(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    response = await client.post(
        "/api/posts",
        json={"title": "My First Post", "content": "This is the content"},
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My First Post"
    assert data["content"] == "This is the content"
    assert data["user_id"] == user["id"]
    assert "id" in data
    assert "date_posted" in data
    assert data["author"]["username"] == "testuser"

@pytest.mark.anyio
async def test_create_post_unauthorized(client: AsyncClient):
    response = await client.post(
        "/api/posts",
        json={"title": "Test Post", "content": "Test content"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

@pytest.mark.anyio
async def test_update_post_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    response = await client.post(
        "/api/posts",
        json={"title": "Original Title", "content": "Original content"},
        headers=headers,
    )
    post_id = response.json()["id"]

    response = await client.patch(
        f"/api/posts/{post_id}",
        json={"title": "Updated Title"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["content"] == "Original content"

@pytest.mark.anyio
async def test_update_post_wrong_user(client: AsyncClient):
    await create_test_user(client, username="user1", email="user1@example.com")
    token1 = await login_user(client, email="user1@example.com")

    response = await client.post(
        "/api/posts",
        json={"title": "User 1's Post", "content": "Only user 1 can edit this"},
        headers=auth_header(token1),
    )
    post_id = response.json()["id"]

    await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")

    response = await client.patch(
        f"/api/posts/{post_id}",
        json={"title": "Hacked Title"},
        headers=auth_header(token2),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You are not the owner of this post"

@pytest.mark.anyio
async def test_get_posts_with_pagination(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    for i in range(5):
        response = await client.post(
            "/api/posts",
            json={"title": f"Post {i}", "content": f"Content for post {i}"},
            headers=headers,
        )
        assert response.status_code == 201

    response = await client.get("/api/posts")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["posts"]) == 5
    assert data["has_more"] is False

    response = await client.get("/api/posts?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["posts"]) == 2
    assert data["has_more"] is True

    response = await client.get("/api/posts?skip=2&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["posts"]) == 2
    assert data["skip"] == 2
    assert data["limit"] == 2


@pytest.mark.anyio
async def test_get_post_by_id_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.post(
        "/api/posts",
        json={"title": "My Post", "content": "Some content"},
        headers=auth_header(token),
    )
    post_id = response.json()["id"]

    response = await client.get(f"/api/posts/{post_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == post_id
    assert data["title"] == "My Post"
    assert data["content"] == "Some content"
    assert "author" in data


@pytest.mark.anyio
async def test_get_post_by_id_not_found(client: AsyncClient):
    response = await client.get("/api/posts/99999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Post not found"


@pytest.mark.anyio
async def test_full_update_post_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    response = await client.post(
        "/api/posts",
        json={"title": "Original Title", "content": "Original content"},
        headers=headers,
    )
    post_id = response.json()["id"]

    response = await client.put(
        f"/api/posts/{post_id}",
        json={"title": "New Title", "content": "New content"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Title"
    assert data["content"] == "New content"


@pytest.mark.anyio
async def test_full_update_post_unauthorized(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.post(
        "/api/posts",
        json={"title": "Original Title", "content": "Original content"},
        headers=auth_header(token),
    )
    post_id = response.json()["id"]

    response = await client.put(
        f"/api/posts/{post_id}",
        json={"title": "New Title", "content": "New content"},
    )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_full_update_post_not_owner(client: AsyncClient):
    await create_test_user(client, username="owner", email="owner@example.com")
    token_owner = await login_user(client, email="owner@example.com")

    response = await client.post(
        "/api/posts",
        json={"title": "Owner Post", "content": "Owner content"},
        headers=auth_header(token_owner),
    )
    post_id = response.json()["id"]

    await create_test_user(client, username="other", email="other@example.com")
    token_other = await login_user(client, email="other@example.com")

    response = await client.put(
        f"/api/posts/{post_id}",
        json={"title": "Hacked", "content": "Hacked content"},
        headers=auth_header(token_other),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You are not the owner of this post"


@pytest.mark.anyio
async def test_full_update_post_not_found(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.put(
        "/api/posts/99999",
        json={"title": "Title", "content": "Content"},
        headers=auth_header(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Post not found"


@pytest.mark.anyio
async def test_partial_update_post_unauthorized(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.post(
        "/api/posts",
        json={"title": "Original Title", "content": "Original content"},
        headers=auth_header(token),
    )
    post_id = response.json()["id"]

    response = await client.patch(
        f"/api/posts/{post_id}",
        json={"title": "New Title"},
    )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_partial_update_post_not_found(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        "/api/posts/99999",
        json={"title": "New Title"},
        headers=auth_header(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Post not found"


@pytest.mark.anyio
async def test_delete_post_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    response = await client.post(
        "/api/posts",
        json={"title": "Post to Delete", "content": "Will be deleted"},
        headers=headers,
    )
    post_id = response.json()["id"]

    response = await client.delete(f"/api/posts/{post_id}", headers=headers)
    assert response.status_code == 204

    response = await client.get(f"/api/posts/{post_id}")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_delete_post_unauthorized(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.post(
        "/api/posts",
        json={"title": "My Post", "content": "Content"},
        headers=auth_header(token),
    )
    post_id = response.json()["id"]

    response = await client.delete(f"/api/posts/{post_id}")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_delete_post_not_owner(client: AsyncClient):
    await create_test_user(client, username="owner", email="owner@example.com")
    token_owner = await login_user(client, email="owner@example.com")

    response = await client.post(
        "/api/posts",
        json={"title": "Owner Post", "content": "Content"},
        headers=auth_header(token_owner),
    )
    post_id = response.json()["id"]

    await create_test_user(client, username="other", email="other@example.com")
    token_other = await login_user(client, email="other@example.com")

    response = await client.delete(f"/api/posts/{post_id}", headers=auth_header(token_other))

    assert response.status_code == 403
    assert response.json()["detail"] == "You are not the owner of this post"


@pytest.mark.anyio
async def test_delete_post_not_found(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.delete("/api/posts/99999", headers=auth_header(token))

    assert response.status_code == 404
    assert response.json()["detail"] == "Post not found"
