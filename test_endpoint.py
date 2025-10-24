import requests
import json

def test_loan_application(data):
    try:
        response = requests.post(
            "http://127.0.0.1:8000/apply-loan-frontend",
            headers={"Content-Type": "application/json"},
            json=data
        )
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

# Test Case 1: High-risk application (should be rejected)
high_risk_data = {
    "name": "Test User",
    "age": 25,
    "college": "Test University",
    "college_id": "",
    "loan_amount": 300000,
    "income": 50000,
    "income_proof": "No",
    "email": "test@example.com",
    "phone": "1234567890",
    "purpose": "Education"
}

print("Testing high-risk application:")
test_loan_application(high_risk_data)