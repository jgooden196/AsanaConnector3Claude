def is_repair_form_task(task):
    """Check if a task was created from the repair request form"""
    try:
        # Check if the task is in the repair project
        for project in task.get('projects', []):
            if project['gid'] == 1209602262926911:
                return True
        return False
    except Exception as e:
        logger.error(f"Error checking if task is from repair form: {e}")
        return False

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Handles incoming webhook requests from Asana"""
    # Check if this is the webhook handshake request
    if 'X-Hook-Secret' in request.headers:
        secret = request.headers['X-Hook-Secret']
        WEBHOOK_SECRET['secret'] = secret  # Store secret dynamically
        
        response = jsonify({})
        response.headers['X-Hook-Secret'] = secret  # Send back the secret
         
        logger.info(f"Webhook Handshake Successful. Secret: {secret}")
        return response, 200
    
    # If it's not a handshake, it's an event
    try:
        data = request.json
        logger.info(f"Received Asana Event: {data}")
        
        # Process events
        events = data.get('events', [])
        
        for event in events:
            # Check if this is a new task added to the repair project
            if event.get('action') == 'added' and event.get('resource', {}).get('resource_type') == 'task':
                # Get the task details
                task_gid = event.get('resource', {}).get('gid')
                if not task_gid:
                    continue
                    
                task = client.tasks.find_by_id(task_gid)
                
                # Check if this task was created from the repair form
                if is_repair_form_task(task):
                    # Process this new repair request
                    process_repair_request(task)
        
        return jsonify({"status": "received"}), 200
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/setup', methods=['GET'])
def setup():
    """Setup endpoint to initialize the webhook"""
    try:
        # Register the webhook for the repair project
        webhook_url = request.url_root.rstrip('/') + "/webhook"
        
        # Register the webhook
        webhook = client.webhooks.create({
            'resource': REPAIR_PROJECT_ID,
            'target': webhook_url
        })
        
        logger.info(f"Webhook registered: {webhook['gid']}")
        return jsonify({
            "status": "success", 
            "message": f"Webhook registered for repair project",
            "webhook_gid": webhook['gid'],
            "target_url": webhook_url
        }), 200
    except Exception as e:
        logger.error(f"Error setting up: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Failed to setup: {str(e)}"
        }), 500

@app.route('/test-email', methods=['GET'])
def test_email():
    """Test the email notification system"""
    try:
        # Create a sample repair request details dictionary
        test_details = {
            'first_name': 'Test',
            'last_name': 'Tenant',
            'email': 'test@example.com',
            'phone': '(555) 123-4567',
            'address': '123 Test Street',
            'unit_number': 'Apt 4B',
            'urgency_level': 'Standard',
            'issue_category': 'Plumbing',
            'specific_issue': 'Leaky faucet',
            'description': 'This is a test description for the repair request system.'
        }
        
        # Simulate a fake task GID for testing
        test_task_gid = 'test_task_12345'
        
        # Send test email
        send_email_notification(test_details, test_task_gid)
        
        return jsonify({
            "status": "success", 
            "message": "Test email sent successfully"
        }), 200
    except Exception as e:
        logger.error(f"Error sending test email: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Failed to send test email: {str(e)}"
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy", 
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route('/process-task/<task_gid>', methods=['GET'])
def process_specific_task(task_gid):
    """Manually process a specific task"""
    try:
        task = client.tasks.find_by_id(task_gid)
        if is_repair_form_task(task):
            success = process_repair_request(task)
            if success:
                return jsonify({
                    "status": "success", 
                    "message": f"Task {task_gid} processed successfully"
                }), 200
            else:
                return jsonify({
                    "status": "error", 
                    "message": f"Failed to process task {task_gid}"
                }), 500
        else:
            return jsonify({
                "status": "error", 
                "message": f"Task {task_gid} is not a repair request task"
            }), 400
    except Exception as e:
        logger.error(f"Error processing task: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Error: {str(e)}"
        }), 500

@app.route('/manual-trigger', methods=['GET'])
def manual_trigger():
    """User-friendly endpoint to manually trigger processing of recent tasks"""
    try:
        html_response = """
        <html>
        <head>
            <title>Property Repair Management</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
                .container { max-width: 600px; margin: 0 auto; }
                h1 { color: #333; }
                .button { 
                    display: inline-block; 
                    background: #4CAF50; 
                    color: white; 
                    padding: 10px 20px; 
                    text-decoration: none; 
                    border-radius: 4px; 
                    margin: 10px; 
                    text-align: center;
                }
                .grid { 
                    display: flex; 
                    flex-wrap: wrap; 
                    justify-content: center; 
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔧 Property Repair Management</h1>
                <p>Use this page to manually trigger actions for the repair management system.</p>
                
                <div class="grid">
                    <a href="/process-recent" class="button">Process Recent Repair Requests</a>
                    <a href="/test-email" class="button">Send Test Email</a>
                    <a href="/setup" class="button">Setup/Reset Webhook</a>
                </div>
                
                <hr>
                <p>Current time: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
            </div>
        </body>
        </html>
        """
        return html_response
    except Exception as e:
        logger.error(f"Error in manual trigger page: {e}")
        return f"Error: {str(e)}", 500

@app.route('/process-recent', methods=['GET'])
def process_recent():
    """Process recent tasks from the repair project"""
    try:
        # Get tasks created in the last 24 hours
        tasks = client.tasks.find_all({
            'project': REPAIR_PROJECT_ID,
            'modified_since': (datetime.now() - timedelta(days=1)).isoformat()
        })
        
        processed_count = 0
        for task in tasks:
            if is_repair_form_task(task):
                if process_repair_request(task):
                    processed_count += 1
        
        html_response = f"""
        <html>
        <head>
            <title>Recent Tasks Processed</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                .success {{ color: green; font-weight: bold; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                h1 {{ color: #333; }}
                .button {{ 
                    display: inline-block; 
                    background: #4CAF50; 
                    color: white; 
                    padding: 10px 20px; 
                    text-decoration: none; 
                    border-radius: 4px; 
                    margin-top: 20px; 
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Recent Tasks Processed</h1>
                <p class="success">✅ Processed {processed_count} recent repair request tasks</p>
                <p>The system has checked for recent repair requests and processed them.</p>
                <p>Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                <a href="/manual-trigger" class="button">Back to Main Menu</a>
            </div>
        </body>
        </html>
        """
        return html_response
    except Exception as e:
        logger.error(f"Error processing recent tasks: {e}")
        return f"Error processing recent tasks: {str(e)}", 500

# Main application runner
if __name__ == '__main__':
    app.run(debug=True)
