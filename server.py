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
from repair_workflow import process_repair_request, is_repair_form_task, client

# Webhook secret storage
WEBHOOK_SECRET = {}

@app.route('/webhook', methods=['POST', 'GET'])
def receive_webhook():
    """Handle incoming webhook requests from Asana"""
    # Log all incoming requests
    logger.info(f"Webhook request received - Method: {request.method}")
    logger.info(f"Headers: {dict(request.headers)}")
    
    # GET request handling (for debugging)
    if request.method == 'GET':
        return "Webhook Endpoint is Accessible", 200
    
    # Handshake handling
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
    
    # Event verification for regular webhook events
    if request.method == 'POST':
        # Verify signature if X-Hook-Signature is present
        if 'X-Hook-Signature' in request.headers:
            # Retrieve stored secret
            stored_secret = WEBHOOK_SECRET.get('secret', '')
            if not stored_secret:
                logger.error("No stored webhook secret")
                return '', 401
            
            # Compute HMAC signature
            computed_signature = hmac.new(
                key=stored_secret.encode(),
                msg=request.data,
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
                        task = client.tasks.find_by_id(task_gid)
                        
                        if is_repair_form_task(task):
                            process_repair_request(task)
            
            return '', 200
        
        except Exception as e:
            logger.error(f"Error processing webhook events: {e}")
            return '', 500
    
    # Catch-all for unsupported methods
    return 'Method Not Allowed', 405

if __name__ == '__main__':
    app.run(port=8080)
