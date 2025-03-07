import os
import logging
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify
from asana import Client
from datetime import datetime

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger()

# Asana API setup
asana_token = os.environ.get('ASANA_TOKEN')
client = Client.access_token(asana_token)

# Email setup (add these environment variables in Railway)
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
EMAIL_SERVER = os.environ.get('EMAIL_SERVER', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))

# Project IDs and constants
REPAIR_PROJECT_ID = '1209602262926911'  # The ID of your Repair Requests project
SUBTASKS_PROJECT_ID = REPAIR_PROJECT_ID  # By default, create subtasks in the same project
EMAIL_DISTRIBUTION_LIST = 'jgooden@sulton.co'  # Replace with your actual email or comma-separated list

# Dictionary to store webhook secret dynamically
WEBHOOK_SECRET = {}

def create_category_subtasks(task_gid, issue_category):
    """Create appropriate subtasks based on the repair category"""
    try:
        # Define subtasks based on category
        subtasks = []
        
        # Common subtasks for all categories
        common_subtasks = [
            "Schedule inspection",
            "Contact tenant to confirm repair details",
            "Assign maintenance personnel",
            "Follow up with tenant after repair",
            "Mark as resolved and update records"
        ]
        
        # Add category-specific subtasks
        if issue_category == "Plumbing":
            subtasks = ["Assess plumbing issue", "Contact plumber if needed"] + common_subtasks
        elif issue_category == "Electrical":
            subtasks = ["Safety assessment", "Contact electrician if needed"] + common_subtasks
        elif issue_category == "Appliance":
            subtasks = ["Identify appliance make/model", "Check warranty status", "Contact repair service"] + common_subtasks
        elif issue_category == "HVAC":
            subtasks = ["Verify system status", "Contact HVAC technician"] + common_subtasks
        elif issue_category == "Structural":
            subtasks = ["Assess urgency and safety impact", "Document with photos", "Get contractor estimates"] + common_subtasks
        else:  # Default/Other
            subtasks = ["Determine repair category", "Assess issue"] + common_subtasks
        
        # Create each subtask
        for subtask_name in subtasks:
            client.tasks.create_subtask_for_task(task_gid, {'name': subtask_name})
            
        logger.info(f"Created {len(subtasks)} subtasks for task {task_gid}")
        return True
    except Exception as e:
        logger.error(f"Error creating subtasks: {e}")
        return False

def is_repair_form_task(task):
    """Check if a task was created from the repair request form"""
    try:
        # Check if the task is in the repair project
        for project in task.get('projects', []):
            if project['gid'] == REPAIR_PROJECT_ID:
                return True
        return False
    except Exception as e:
        logger.error(f"Error checking if task is from repair form: {e}")
        return False

def get_task_field_value(task, field_name):
    """Extract a custom field value from a task"""
    try:
        if 'custom_fields' not in task:
            return None
            
        for field in task['custom_fields']:
            if field['name'] == field_name:
                if field['type'] == 'text':
                    return field.get('text_value')
                elif field['type'] == 'enum':
                    if field.get('enum_value'):
                        return field['enum_value']['name']
                elif field['type'] == 'number':
                    return field.get('number_value')
                else:
                    return None
        return None
    except Exception as e:
        logger.error(f"Error getting field value: {e}")
        return None

def process_repair_request(task):
    """Process a new repair request task"""
    try:
        # Get full task details
        task_gid = task['gid']
        task_details = client.tasks.find_by_id(task_gid)
        
        # Extract form field values
        tenant_name = get_task_field_value(task_details, 'Tenant Name') or 'Unknown Tenant'
        property_address = get_task_field_value(task_details, 'Property/Unit Address') or 'Unknown Address'
        issue_category = get_task_field_value(task_details, 'Issue Category') or 'Other'
        urgency = get_task_field_value(task_details, 'Urgency Level') or 'Standard'
        description = task_details.get('notes', 'No description provided')
        
        # Create subtasks based on the issue category
        create_category_subtasks(task_gid, issue_category)
        
        # Send email notification
        send_email_notification(tenant_name, property_address, issue_category, urgency, description, task_gid)
        
        logger.info(f"Successfully processed repair request: {task_gid}")
        return True
    except Exception as e:
        logger.error(f"Error processing repair request: {e}")
        return False

def send_email_notification(tenant_name, property_address, issue_category, urgency, description, task_gid):
    """Send a formatted email notification about the repair request"""
    try:
        # Get emoji for issue category
        category_emoji = {
            'Plumbing': '🚿',
            'Electrical': '⚡',
            'Appliance': '🔌',
            'HVAC': '❄️',
            'Structural': '🏠',
            'Other': '🔧'
        }.get(issue_category, '🔧')
        
        # Get emoji for urgency
        urgency_emoji = {
            'Emergency': '🚨',
            'Urgent': '⚠️',
            'Standard': '📝'
        }.get(urgency, '📝')
        
        # Create email subject
        subject = f"{urgency_emoji} {issue_category} Repair Needed at {property_address}"
        
        # Create email body
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>{category_emoji} New Repair Request {category_emoji}</h2>
            
            <p><strong>Property:</strong> {property_address}</p>
            <p><strong>Tenant:</strong> {tenant_name}</p>
            <p><strong>Issue Type:</strong> {category_emoji} {issue_category}</p>
            <p><strong>Urgency:</strong> {urgency_emoji} {urgency}</p>
            
            <div style="background-color: #f5f5f5; padding: 15px; border-left: 4px solid #0073ea;">
                <h3>Description:</h3>
                <p>{description}</p>
            </div>
            
            <p style="margin-top: 20px;">Please log into Asana to view and manage this task.</p>
            <p>Task Link: <a href="https://app.asana.com/0/{REPAIR_PROJECT_ID}/{task_gid}">View Task in Asana</a></p>
            
            <p style="color: #666; font-size: 12px;">This email was automatically generated by the Property Management Repair System.</p>
        </body>
        </html>
        """
        
        # Skip actual email sending if credentials not set (for testing)
        if not EMAIL_USER or not EMAIL_PASSWORD:
            logger.warning("Email credentials not set, skipping email send")
            return True
        
        # Setup email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_DISTRIBUTION_LIST
        
        html_part = MIMEText(body, 'html')
        msg.attach(html_part)
        
        # Send email
        server = smtplib.SMTP(EMAIL_SERVER, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email notification sent for task {task_gid}")
        return True
    except Exception as e:
        logger.error(f"Error sending email notification: {e}")
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
        webhook_url = "https://asanaconnector3claude-production.up.railway.app/webhook"
        
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
        send_email_notification(
            "Test Tenant", 
            "123 Test Street", 
            "Plumbing", 
            "Standard", 
            "This is a test description for the repair request.",
            "12345"
        )
        return jsonify({
            "status": "success", 
            "message": "Test email sent"
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
    return jsonify({"status": "healthy"}), 200

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
                    margin-top: 20px; 
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔧 Property Repair Management</h1>
                <p>Use this page to manually trigger actions for the repair management system.</p>
                
                <h2>Manual Actions:</h2>
                
                <p>
                    <a href="/process-recent" class="button">Process Recent Repair Requests</a>
                </p>
                
                <p>
                    <a href="/test-email" class="button">Send Test Email</a>
                </p>
                
                <p>
                    <a href="/setup" class="button">Setup/Reset Webhook</a>
                </p>
                
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
            'modified_since': (datetime.now() - datetime.timedelta(days=1)).isoformat()
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

if __name__ == '__main__':
    app.run(debug=True)
