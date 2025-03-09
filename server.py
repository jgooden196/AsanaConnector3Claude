import os
import logging
import sys
import hmac
import hashlib
import json
from flask import Flask, request, jsonify
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('webhook_events.log')
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Import the processing functions from repair_workflow
from repair_workflow import process_repair_request, is_repair_form_task, client, REPAIR_PROJECT_ID

# Webhook secret storage
WEBHOOK_SECRET = {}

@app.route('/webhook', methods=['POST', 'GET'])
def receive_webhook():
    """Handle incoming webhook requests from Asana"""
    # Log all incoming requests
    logger.info(f"Webhook request received - Method: {request.method}")
    
    # Handle webhook handshake
    if 'X-Hook-Secret' in request.headers:
        secret = request.headers['X-Hook-Secret']
        
        # Store the secret
        WEBHOOK_SECRET['secret'] = secret
        
        # Log the secret (be cautious with logging secrets in production)
        logger.info("Webhook handshake secret received")
        
        # Respond with the same secret
        response = jsonify({})
        response.headers['X-Hook-Secret'] = secret
        return response, 200
    
    # Verify webhook signatures for regular events
    if request.method == 'POST':
        # Verify signature if X-Hook-Signature is present
        if 'X-Hook-Signature' in request.headers:
            # Retrieve stored secret
            stored_secret = WEBHOOK_SECRET.get('secret', '')
            if not stored_secret:
                logger.error("No stored webhook secret")
                return '', 401
            
            # Compute HMAC signature
            payload = request.data
            computed_signature = hmac.new(
                key=stored_secret.encode(),
                msg=payload,
                digestmod=hashlib.sha256
            ).hexdigest()
            
            # Constant-time comparison
            if not hmac.compare_digest(request.headers['X-Hook-Signature'], computed_signature):
                logger.error("Signature verification failed")
                return '', 401
        
        # Process webhook events
        try:
            data = request.json
            events = data.get('events', [])
            
            # Log received events
            logger.info(f"Received {len(events)} events")
            
            for event in events:
                # Check for task-related events
                if (event.get('action') == 'added' and 
                    event.get('resource', {}).get('resource_type') == 'task'):
                    
                    task_gid = event.get('resource', {}).get('gid')
                    if task_gid:
                        # Get the complete task data with custom fields
                        task = client.tasks.find_by_id(
                            task_gid, 
                            {'opt_fields': 'custom_fields,custom_fields.enum_value,name,notes,projects'}
                        )
                        
                        if is_repair_form_task(task):
                            logger.info(f"Processing repair task {task_gid}")
                            process_repair_request(task)
            
            return '', 200
        
        except Exception as e:
            logger.error(f"Error processing webhook events: {e}")
            return '', 500
    
    # Catch-all for unsupported methods
    return 'Method Not Allowed', 405

@app.route('/setup', methods=['GET'])
def setup_webhook():
    """Set up a webhook for the Asana project"""
    try:
        # Get X-Hook-Secret from environment or generate one
        x_hook_secret = os.environ.get('X_HOOK_SECRET', '')
        if not x_hook_secret:
            import secrets
            x_hook_secret = secrets.token_hex(16)
            logger.info(f"Generated new webhook secret: {x_hook_secret}")
        
        # Store it globally
        WEBHOOK_SECRET['secret'] = x_hook_secret
        
        # Get the application URL from environment or request
        app_url = os.environ.get('APP_URL', '')
        if not app_url:
            # Try to construct from request
            if request.url_root:
                app_url = request.url_root.rstrip('/')
            else:
                return jsonify({
                    "error": "APP_URL environment variable not set and couldn't be determined"
                }), 500
        
        webhook_url = f"{app_url}/webhook"
        
        # Create a webhook for the repair project
        webhook = client.webhooks.create({
            'resource': REPAIR_PROJECT_ID,
            'target': webhook_url,
            'filters': [
                {
                    'resource_type': 'task',
                    'action': 'added'
                }
            ]
        })
        
        # Return success with webhook details
        return jsonify({
            "status": "success",
            "message": "Webhook created successfully",
            "webhook_gid": webhook.get('gid', ''),
            "target_url": webhook_url,
            "project_gid": REPAIR_PROJECT_ID
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to set up webhook: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Failed to set up webhook: {str(e)}"
        }), 500

# Import the routes from main.py
from main import manual_trigger, process_recent, test_email, health, process_specific_task

# Register the routes
app.route('/manual-trigger', methods=['GET'])(manual_trigger)
app.route('/process-recent', methods=['GET'])(process_recent)
app.route('/test-email', methods=['GET'])(test_email)
app.route('/health', methods=['GET'])(health)
app.route('/process-task/<task_gid>', methods=['GET'])(process_specific_task)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
