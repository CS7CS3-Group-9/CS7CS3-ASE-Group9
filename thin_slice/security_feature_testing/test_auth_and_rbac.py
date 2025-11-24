import pytest
from flask import Flask
from flask_login import login_user, LoginManager, UserMixin, current_user


# ---- Example user model ----
class User(UserMixin):
    def __init__(self, id, role):
        self.id = id
        self.role = role


# ---- Flask app fixture ----
@pytest.fixture
def app():
    app = Flask(__name__)
    app.secret_key = "testing"

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        # For thin-slice test, just return a dummy admin user
        return User(user_id, "admin")

    @app.route("/admin")
    def admin_page():
        # Simple RBAC check
        if getattr(current_user, "role", None) != "admin":
            return "Access Denied", 403
        return "Welcome Admin"

    return app


# ---- Thin-slice RBAC tests ----
@pytest.mark.parametrize(
    "user_id, role, expected_status",
    [
        ("u1", "admin", 200),
        ("u2", "editor", 403),
        ("u3", "viewer", 403),
        ("u4", "admin", 200),
    ],
)
def test_rbac_various_roles(app, user_id, role, expected_status):
    with app.test_request_context():
        u = User(user_id, role)
        login_user(u)
        response = app.test_client().get("/admin")
        assert response.status_code == expected_status
