"""
Working with APIs using Requests
=================================
HTTP requests and API consumption patterns.
"""

# Note: Install requests with: pip install requests
# For demo, we'll show patterns without actual HTTP calls

import json
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

# ================================
# BASIC HTTP PATTERNS
# ================================

print("--- HTTP Request Patterns ---")
print("""
# GET Request
response = requests.get('https://api.example.com/users')
data = response.json()

# POST Request
response = requests.post(
    'https://api.example.com/users',
    json={'name': 'Alice', 'email': 'alice@example.com'}
)

# With headers
headers = {'Authorization': 'Bearer token123'}
response = requests.get(url, headers=headers)

# With query parameters
params = {'page': 1, 'limit': 10}
response = requests.get(url, params=params)
""")

# ================================
# API CLIENT CLASS
# ================================

class APIClient:
    """Reusable API client with common patterns."""

    def __init__(self, base_url, api_key=None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

    def _get_headers(self):
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers

    def get(self, endpoint, params=None):
        """Simulated GET request."""
        url = f"{self.base_url}/{endpoint}"
        print(f"GET {url} params={params}")
        # In real code: return requests.get(url, headers=self._get_headers(), params=params)
        return {'status': 'ok', 'data': []}

    def post(self, endpoint, data):
        """Simulated POST request."""
        url = f"{self.base_url}/{endpoint}"
        print(f"POST {url} data={data}")
        return {'status': 'created', 'id': 123}

    def put(self, endpoint, data):
        """Simulated PUT request."""
        url = f"{self.base_url}/{endpoint}"
        print(f"PUT {url} data={data}")
        return {'status': 'updated'}

    def delete(self, endpoint):
        """Simulated DELETE request."""
        url = f"{self.base_url}/{endpoint}"
        print(f"DELETE {url}")
        return {'status': 'deleted'}

# Usage
client = APIClient('https://api.example.com', api_key='secret')
client.get('users', params={'active': True})
client.post('users', {'name': 'Bob'})

# ================================
# ERROR HANDLING
# ================================

print("\n--- Error Handling Pattern ---")

class APIError(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error {status_code}: {message}")

def make_request(url):
    """Request with proper error handling."""
    try:
        # response = requests.get(url, timeout=10)
        # response.raise_for_status()  # Raises for 4xx/5xx
        # return response.json()
        return {'data': 'mock'}
    except Exception as e:
        # Handle different errors:
        # requests.exceptions.Timeout - timeout
        # requests.exceptions.ConnectionError - network issue
        # requests.exceptions.HTTPError - bad status code
        raise APIError(500, str(e))

# ================================
# RETRY LOGIC
# ================================

print("\n--- Retry Pattern ---")

import time

def retry_request(func, max_retries=3, backoff=1.0):
    """Retry a request with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = backoff * (2 ** attempt)
            print(f"Retry {attempt + 1} after {wait}s: {e}")
            time.sleep(wait)

# ================================
# PAGINATION
# ================================

print("\n--- Pagination Pattern ---")

def fetch_all_pages(client, endpoint, page_size=100):
    """Fetch all pages from a paginated API."""
    all_data = []
    page = 1

    while True:
        response = client.get(endpoint, params={'page': page, 'limit': page_size})
        data = response.get('data', [])

        if not data:
            break

        all_data.extend(data)
        page += 1

        # Safety limit
        if page > 100:
            break

    return all_data

# ================================
# RATE LIMITING
# ================================

print("\n--- Rate Limiting ---")

import threading

class RateLimiter:
    """Simple rate limiter."""

    def __init__(self, calls_per_second):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_call = time.time()

limiter = RateLimiter(calls_per_second=2)
for i in range(3):
    limiter.wait()
    print(f"Request {i} at {time.time():.2f}")

print("\n✅ API patterns complete!")
