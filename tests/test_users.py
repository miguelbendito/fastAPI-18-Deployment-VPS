from datetime import datetime, UTC
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header, create_test_user, login_user

@pytest.mark.anyio
async def test_create_user_validation_error(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={
            "username": "testuser",
        },
    )

    assert response.status_code == 422
    assert "email" in response.text
    assert "password" in response.text



## Test Create User Duplicate Email
@pytest.mark.anyio
async def test_create_user_duplicate_email(client: AsyncClient):
    await create_test_user(client)

    response = await client.post(
        "/api/users",
        json={
            "username": "different_user",
            "email": "test@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"



## Test Create User Success
@pytest.mark.anyio
async def test_create_user_success(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "securepassword123",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert "image_path" in data
    assert "password" not in data
    assert "password_hash" not in data



## Test Upload Profile Picture
@pytest.mark.anyio
async def test_upload_profile_picture(client: AsyncClient, mocked_aws):
    user = await create_test_user(client)
    token = await login_user(client)

    test_image_path = Path(__file__).parent / "test_image.jpg"
    image_bytes = test_image_path.read_bytes()

    response = await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("profile.jpg", BytesIO(image_bytes), "image/jpeg")},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["image_file"] is not None
    assert data["image_file"].endswith(".jpg")
    assert "s3" in data["image_path"]

    s3_objects = mocked_aws.list_objects_v2(Bucket="test-bucket")
    assert "Contents" in s3_objects
    assert len(s3_objects["Contents"]) == 1
    assert s3_objects["Contents"][0]["Key"].endswith(data["image_file"])



## Test Forgot Password Sends Email
@pytest.mark.anyio
async def test_forgot_password_sends_email(client: AsyncClient):
    await create_test_user(client)

    with patch(
        "routers.users.send_password_reset_email",
        new_callable=AsyncMock,
    ) as mock_send:
        response = await client.post(
            "/api/users/forgot-password",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 202
        mock_send.assert_awaited_once()
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["to_email"] == "test@example.com"
        assert call_kwargs["username"] == "testuser"
        assert "token" in call_kwargs


## Test Create User Duplicate Username
@pytest.mark.anyio
async def test_create_user_duplicate_username(client: AsyncClient):
    await create_test_user(client)

    response = await client.post(
        "/api/users",
        json={
            "username": "testuser",
            "email": "different@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Username already exists"


## Test Login Success
@pytest.mark.anyio
async def test_login_success(client: AsyncClient):
    await create_test_user(client)

    response = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": "testpassword123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


## Test Login Wrong Password
@pytest.mark.anyio
async def test_login_wrong_password(client: AsyncClient):
    await create_test_user(client)

    response = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": "wrongpassword"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


## Test Login Wrong Email
@pytest.mark.anyio
async def test_login_wrong_email(client: AsyncClient):
    response = await client.post(
        "/api/users/token",
        data={"username": "nobody@example.com", "password": "testpassword123"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


## Test Get Current User
@pytest.mark.anyio
async def test_get_current_user(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.get("/api/users/me", headers=auth_header(token))

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"


## Test Get Current User Unauthenticated
@pytest.mark.anyio
async def test_get_current_user_unauthorized(client: AsyncClient):
    response = await client.get("/api/users/me")

    assert response.status_code == 401


## Test Forgot Password Nonexistent Email
@pytest.mark.anyio
async def test_forgot_password_nonexistent_email(client: AsyncClient):
    with patch(
        "routers.users.send_password_reset_email",
        new_callable=AsyncMock,
    ) as mock_send:
        response = await client.post(
            "/api/users/forgot-password",
            json={"email": "nobody@example.com"},
        )

        assert response.status_code == 202
        mock_send.assert_not_awaited()


## Test Reset Password Success
@pytest.mark.anyio
async def test_reset_password_success(client: AsyncClient):
    await create_test_user(client)

    with patch(
        "routers.users.send_password_reset_email",
        new_callable=AsyncMock,
    ) as mock_send:
        await client.post(
            "/api/users/forgot-password",
            json={"email": "test@example.com"},
        )
        token = mock_send.call_args.kwargs["token"]

    response = await client.post(
        "/api/users/reset-password",
        json={"token": token, "new_password": "newpassword123"},
    )

    assert response.status_code == 200
    assert "successfully" in response.json()["message"].lower()

    login_response = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": "newpassword123"},
    )
    assert login_response.status_code == 200


## Test Reset Password Invalid Token
@pytest.mark.anyio
async def test_reset_password_invalid_token(client: AsyncClient):
    response = await client.post(
        "/api/users/reset-password",
        json={"token": "completelyinvalidtoken", "new_password": "newpassword123"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired reset token"


## Test Reset Password Expired Token
@pytest.mark.anyio
async def test_reset_password_expired_token(client: AsyncClient):
    await create_test_user(client)

    with patch(
        "routers.users.send_password_reset_email",
        new_callable=AsyncMock,
    ) as mock_send:
        await client.post(
            "/api/users/forgot-password",
            json={"email": "test@example.com"},
        )
        token = mock_send.call_args.kwargs["token"]

    with patch("routers.users.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2030, 1, 1, tzinfo=UTC)
        response = await client.post(
            "/api/users/reset-password",
            json={"token": token, "new_password": "newpassword123"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired reset token"


## Test Change Password Success
@pytest.mark.anyio
async def test_change_password_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        "/api/users/me/password",
        json={"current_password": "testpassword123", "new_password": "newpassword123"},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert "successfully" in response.json()["message"].lower()

    login_response = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": "newpassword123"},
    )
    assert login_response.status_code == 200


## Test Change Password Wrong Current Password
@pytest.mark.anyio
async def test_change_password_wrong_current(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        "/api/users/me/password",
        json={"current_password": "wrongpassword", "new_password": "newpassword123"},
        headers=auth_header(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect"


## Test Change Password Unauthenticated
@pytest.mark.anyio
async def test_change_password_unauthorized(client: AsyncClient):
    response = await client.patch(
        "/api/users/me/password",
        json={"current_password": "testpassword123", "new_password": "newpassword123"},
    )

    assert response.status_code == 401


## Test Get User By ID Success
@pytest.mark.anyio
async def test_get_user_success(client: AsyncClient):
    user = await create_test_user(client)

    response = await client.get(f"/api/users/{user['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user["id"]
    assert data["username"] == "testuser"
    assert "email" not in data


## Test Get User By ID Not Found
@pytest.mark.anyio
async def test_get_user_not_found(client: AsyncClient):
    response = await client.get("/api/users/99999")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


## Test Get User Posts Success
@pytest.mark.anyio
async def test_get_user_posts_success(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    for i in range(3):
        await client.post(
            "/api/posts",
            json={"title": f"Post {i}", "content": f"Content {i}"},
            headers=headers,
        )

    response = await client.get(f"/api/users/{user['id']}/posts")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["posts"]) == 3


## Test Get User Posts User Not Found
@pytest.mark.anyio
async def test_get_user_posts_not_found(client: AsyncClient):
    response = await client.get("/api/users/99999/posts")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


## Test Update User Success
@pytest.mark.anyio
async def test_update_user_success(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        f"/api/users/{user['id']}",
        json={"username": "updateduser"},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json()["username"] == "updateduser"


## Test Update User Unauthorized (different user)
@pytest.mark.anyio
async def test_update_user_unauthorized(client: AsyncClient):
    user1 = await create_test_user(client, username="user1", email="user1@example.com")
    await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")

    response = await client.patch(
        f"/api/users/{user1['id']}",
        json={"username": "hacked"},
        headers=auth_header(token2),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You are not the owner of this user profile"


## Test Update User Duplicate Username
@pytest.mark.anyio
async def test_update_user_duplicate_username(client: AsyncClient):
    await create_test_user(client, username="user1", email="user1@example.com")
    user2 = await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")

    response = await client.patch(
        f"/api/users/{user2['id']}",
        json={"username": "user1"},
        headers=auth_header(token2),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Username already exists"


## Test Update User Duplicate Email
@pytest.mark.anyio
async def test_update_user_duplicate_email(client: AsyncClient):
    await create_test_user(client, username="user1", email="user1@example.com")
    user2 = await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")

    response = await client.patch(
        f"/api/users/{user2['id']}",
        json={"email": "user1@example.com"},
        headers=auth_header(token2),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


## Test Delete User Success
@pytest.mark.anyio
async def test_delete_user_success(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)

    response = await client.delete(f"/api/users/{user['id']}", headers=auth_header(token))
    assert response.status_code == 204

    response = await client.get(f"/api/users/{user['id']}")
    assert response.status_code == 404


## Test Delete User Unauthorized (different user)
@pytest.mark.anyio
async def test_delete_user_unauthorized(client: AsyncClient):
    user1 = await create_test_user(client, username="user1", email="user1@example.com")
    await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")

    response = await client.delete(f"/api/users/{user1['id']}", headers=auth_header(token2))

    assert response.status_code == 403
    assert response.json()["detail"] == "You are not the owner of this user profile"


## Test Upload Profile Picture Unauthorized
@pytest.mark.anyio
async def test_upload_profile_picture_unauthorized(client: AsyncClient, mocked_aws):
    user = await create_test_user(client)

    test_image_path = Path(__file__).parent / "test_image.jpg"
    image_bytes = test_image_path.read_bytes()

    response = await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("profile.jpg", BytesIO(image_bytes), "image/jpeg")},
    )

    assert response.status_code == 401


## Test Upload Profile Picture Invalid File
@pytest.mark.anyio
async def test_upload_profile_picture_invalid_file(client: AsyncClient, mocked_aws):
    user = await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("file.txt", BytesIO(b"not an image"), "text/plain")},
        headers=auth_header(token),
    )

    assert response.status_code == 400
    assert "invalid image" in response.json()["detail"].lower()


## Test Upload Profile Picture File Too Large
@pytest.mark.anyio
async def test_upload_profile_picture_file_too_large(client: AsyncClient, mocked_aws):
    user = await create_test_user(client)
    token = await login_user(client)

    oversized = b"x" * (5 * 1024 * 1024 + 1)

    response = await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("big.jpg", BytesIO(oversized), "image/jpeg")},
        headers=auth_header(token),
    )

    assert response.status_code == 400
    assert "too large" in response.json()["detail"].lower()


## Test Delete Profile Picture Success
@pytest.mark.anyio
async def test_delete_profile_picture_success(client: AsyncClient, mocked_aws):
    user = await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    test_image_path = Path(__file__).parent / "test_image.jpg"
    image_bytes = test_image_path.read_bytes()

    await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("profile.jpg", BytesIO(image_bytes), "image/jpeg")},
        headers=headers,
    )

    response = await client.delete(f"/api/users/{user['id']}/picture", headers=headers)

    assert response.status_code == 200
    assert response.json()["image_file"] is None


## Test Delete Profile Picture When None Exists
@pytest.mark.anyio
async def test_delete_profile_picture_no_picture(client: AsyncClient, mocked_aws):
    user = await create_test_user(client)
    token = await login_user(client)

    response = await client.delete(
        f"/api/users/{user['id']}/picture",
        headers=auth_header(token),
    )

    assert response.status_code == 400
    assert "no profile picture" in response.json()["detail"].lower()


## Test Delete Profile Picture Unauthorized
@pytest.mark.anyio
async def test_delete_profile_picture_unauthorized(client: AsyncClient, mocked_aws):
    user1 = await create_test_user(client, username="user1", email="user1@example.com")
    token1 = await login_user(client, email="user1@example.com")

    test_image_path = Path(__file__).parent / "test_image.jpg"
    image_bytes = test_image_path.read_bytes()

    await client.patch(
        f"/api/users/{user1['id']}/picture",
        files={"file": ("profile.jpg", BytesIO(image_bytes), "image/jpeg")},
        headers=auth_header(token1),
    )

    await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")

    response = await client.delete(
        f"/api/users/{user1['id']}/picture",
        headers=auth_header(token2),
    )

    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()
