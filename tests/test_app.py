import pytest
from app import app, db, User
from werkzeug.security import generate_password_hash


@pytest.fixture
def client():
    """
    Create a Flask test client with a temporary in-memory database.
    Everything created in this fixture is thrown away after the test finishes.
    """
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['PROMETHEUS_METRICS_DISABLED'] = True

    with app.test_client() as client:
        with app.app_context():
            db.create_all()      # create tables in the in-memory DB
            yield client         # run the test
            db.drop_all()        # wipe everything after test


@pytest.fixture
def registered_user(client):
    """Create a test user in the DB and return their credentials."""
    with app.app_context():
        user = User(
            username='testuser',
            email='test@example.com',
            password_hash=generate_password_hash('testpassword')
        )
        db.session.add(user)
        db.session.commit()
    return {'username': 'testuser', 'password': 'testpassword'}


class TestHealthEndpoint:
    """The /health endpoint must always return 200 — Kubernetes depends on it."""

    def test_health_returns_200(self, client):
        response = client.get('/health')
        assert response.status_code == 200

    def test_health_returns_ok_status(self, client):
        data = client.get('/health').get_json()
        assert data['status'] == 'ok'


class TestHomePage:
    """Unauthenticated users see the landing page."""

    def test_index_returns_200(self, client):
        response = client.get('/')
        assert response.status_code == 200

    def test_login_page_loads(self, client):
        response = client.get('/login')
        assert response.status_code == 200

    def test_register_page_loads(self, client):
        response = client.get('/register')
        assert response.status_code == 200


class TestAuthentication:
    """Registration and login flows."""

    def test_register_new_user(self, client):
        response = client.post('/register', data={
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'securepassword'
        }, follow_redirects=True)
        assert response.status_code == 200

    def test_register_duplicate_username(self, client, registered_user):
        response = client.post('/register', data={
            'username': 'testuser',      # already exists
            'email': 'other@example.com',
            'password': 'password'
        }, follow_redirects=True)
        assert b'Username already exists' in response.data

    def test_login_valid_credentials(self, client, registered_user):
        response = client.post('/login', data=registered_user,
                               follow_redirects=True)
        assert response.status_code == 200

    def test_login_invalid_password(self, client, registered_user):
        response = client.post('/login', data={
            'username': 'testuser',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        assert b'Invalid username or password' in response.data

    def test_protected_route_redirects_when_logged_out(self, client):
        # Dashboard requires login — should redirect to /login
        response = client.get('/dashboard')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']


class TestMetricsEndpoint:
    """The /metrics endpoint must exist — Prometheus depends on it."""

    def test_metrics_endpoint_returns_200(self, client):
        response = client.get('/metrics')
        assert response.status_code == 200

    def test_metrics_contains_flask_metrics(self, client):
        # Make a request first so there's something to measure
        client.get('/health')
        response = client.get('/metrics')
        # prometheus_flask_exporter should have instrumented the request
        assert b'flask_http_request_duration_seconds' in response.data

    def test_metrics_contains_custom_fintrack_metrics(self, client):
        response = client.get('/metrics')
        # Our custom metrics should always be present, even at 0
        assert b'fintrack_login_success_total' in response.data
        assert b'fintrack_login_failure_total' in response.data
        assert b'fintrack_db_query_duration_seconds' in response.data