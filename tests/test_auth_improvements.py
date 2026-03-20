import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import os
import sys

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock modules before importing auth.jwt_handler to avoid ModuleNotFoundError
class JWTError(Exception):
    pass

jose_mock = MagicMock()
jose_mock.JWTError = JWTError
sys.modules['jose'] = jose_mock
sys.modules['jose.jwt'] = jose_mock.jwt

sys.modules['passlib'] = MagicMock()
sys.modules['passlib.context'] = MagicMock()
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['sqlalchemy.orm'] = MagicMock()
sys.modules['database'] = MagicMock()
sys.modules['database.models'] = MagicMock()

# Pydantic is needed for the classes to be defined
class MockBaseModel:
    def __init__(self, **data):
        for key, value in data.items():
            setattr(self, key, value)
    @classmethod
    def model_validate(cls, data): return cls(**data)
    def model_dump(self): return self.__dict__

pydantic_mock = MagicMock()
pydantic_mock.BaseModel = MockBaseModel
sys.modules['pydantic'] = pydantic_mock

from auth.jwt_handler import AuthService, User, UserRole, TokenData

class TestAuthImprovements(unittest.TestCase):
    def setUp(self):
        self.secret_key = "test_secret_key"
        self.algorithm = "HS256"
        self.auth_service = AuthService(secret_key=self.secret_key, algorithm=self.algorithm)
        self.test_user = User(
            id="test-id",
            email="test@example.com",
            username="testuser",
            role=UserRole.USER,
            created_at=datetime.utcnow()
        )

    @patch('jose.jwt.decode')
    def test_verify_token_valid(self, mock_decode):
        # Setup mock to return a valid payload
        exp_time = datetime.utcnow() + timedelta(minutes=30)
        payload = {
            "user_id": self.test_user.id,
            "username": self.test_user.username,
            "role": self.test_user.role.value,
            "exp": exp_time.timestamp()
        }
        mock_decode.return_value = payload
        mock_decode.side_effect = None

        token_data = self.auth_service.verify_token("valid-token")

        self.assertIsNotNone(token_data)
        self.assertEqual(token_data.user_id, self.test_user.id)
        self.assertEqual(token_data.username, self.test_user.username)
        self.assertEqual(token_data.role, self.test_user.role)

    @patch('jose.jwt.decode')
    def test_verify_token_expired(self, mock_decode):
        # Jose raises JWTError for expired tokens usually
        mock_decode.side_effect = JWTError("Token expired")

        token_data = self.auth_service.verify_token("expired-token")
        self.assertIsNone(token_data)

    @patch('jose.jwt.decode')
    def test_verify_token_malformed(self, mock_decode):
        mock_decode.side_effect = JWTError("Malformed token")

        token_data = self.auth_service.verify_token("not-a-token")
        self.assertIsNone(token_data)

    @patch('jose.jwt.decode')
    def test_verify_token_missing_user_id(self, mock_decode):
        payload = {
            "username": self.test_user.username,
            "role": self.test_user.role.value,
            "exp": (datetime.utcnow() + timedelta(minutes=30)).timestamp()
        }
        mock_decode.return_value = payload
        mock_decode.side_effect = None

        token_data = self.auth_service.verify_token("missing-user-id-token")
        self.assertIsNone(token_data)

    @patch('jose.jwt.decode')
    def test_verify_token_missing_exp(self, mock_decode):
        payload = {
            "user_id": self.test_user.id,
            "username": self.test_user.username,
            "role": self.test_user.role.value
        }
        mock_decode.return_value = payload
        mock_decode.side_effect = None

        # Should handle TypeError gracefully and return None
        token_data = self.auth_service.verify_token("missing-exp-token")
        self.assertIsNone(token_data)

    @patch('jose.jwt.decode')
    def test_verify_token_invalid_role(self, mock_decode):
        payload = {
            "user_id": self.test_user.id,
            "username": self.test_user.username,
            "role": "invalid_role",
            "exp": (datetime.utcnow() + timedelta(minutes=30)).timestamp()
        }
        mock_decode.return_value = payload
        mock_decode.side_effect = None

        # Should handle ValueError gracefully and return None
        token_data = self.auth_service.verify_token("invalid-role-token")
        self.assertIsNone(token_data)

if __name__ == '__main__':
    unittest.main()
