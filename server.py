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
            payload = r
