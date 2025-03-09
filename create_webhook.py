import os
import requests
import json

# Your Asana Personal Access Token from environment variable
ASANA_TOKEN = os.environ.get('ASANA_TOKEN')
# Your project ID from environment variable
REPAIR_PROJECT_ID = os.environ.get('REPAIR_PROJECT_ID')
# Your Railway app URL
APP_URL = os.environ.get('APP_URL') 

def create_webhook():
    # Endpoint URL
    url = "https://app.asana.com/api/1.0/webhooks"
    
    # Headers
    headers = {
        "Authorization": f"Bearer {ASANA_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Webhook data
    webhook_data = {
        "data": {
            "resource": REPAIR_PROJECT_ID,
            "target": f"{APP_URL}/webhook",
            "filters": [
                {
                    "resource_type": "task",
                    "action": "added"
                }
            ]
        }
    }
    
    # Make the request
    response = requests.post(url, headers=headers, json=webhook_data)
    
    # Print the response
    print(f"Status code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    return response.json()

if __name__ == "__main__":
    print(f"Creating webhook for project {REPAIR_PROJECT_ID}")
    print(f"Target URL: {APP_URL}/webhook")
    create_webhook()
