import os
import logging
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify
from asana import Client
from datetime import datetime, timedelta

# Create Flask app BEFORE defining routes
app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('repair_workflow.log')
    ]
)
logger = logging.getLogger(__name__)

# CONFIGURATION VARIABLES TO CONFIRM/SET
# =====================================
# 1. Asana Configuration
ASANA_TOKEN = os.environ.get('ASANA_TOKEN')  # REQUIRED: Your Asana Personal Access Token
REPAIR_PROJECT_ID = os.environ.get('REPAIR_PROJECT_ID', '1209602262926911')  # REQUIRED: Your Repair Requests Project ID
SUBTASKS_PROJECT_ID = os.environ.get('SUBTASKS_PROJECT_ID', REPAIR_PROJECT_ID)  # Optional: Can be same as repair project

# 2. Email Configuration
EMAIL_CONFIG = {
    'user': os.environ.get('EMAIL_USER'),  # REQUIRED: Email address for sending notifications
    'password': os.environ.get('EMAIL_PASSWORD'),  # REQUIRED: Email password or app-specific password
    'server': os.environ.get('EMAIL_SERVER', 'smtp.gmail.com'),  # Default to Gmail, change if using different provider
    'port': int(os.environ.get('EMAIL_PORT', 587)),  # Default SMTP port
    'distribution_list': os.environ.get('EMAIL_DISTRIBUTION_LIST', 'maintenance@yourcompany.com')  # REQUIRED: Where repair notifications go
}

# Asana API setup
client = Client.access_token(ASANA_TOKEN)

# Repair Categories Configuration
REPAIR_CATEGORIES = {
    'Appliance': {
        'emoji': '🔌',
        'subtypes': [
            'Washer not working',
            'Dryer not working', 
            'Dishwasher not working',
            'Stove/Oven issues',
            'Refrigerator problems'
        ]
    },
    'Electrical': {
        'emoji': '⚡',
        'subtypes': [
            'Broken electrical outlet',
            'Light switch not working',
            'Flickering lights',
            'Electrical panel issue'
        ]
    },
    'Plumbing': {
        'emoji': '🚿',
        'subtypes': [
            'Leaky faucet',
            'Clogged drain',
            'Toilet issues',
            'Pipe leak'
        ]
    },
    'HVAC': {
        'emoji': '❄️',
        'subtypes': [
            'No heat',
            'No cooling',
            'Thermostat issues',
            'Strange noises'
        ]
    },
    'Structural': {
        'emoji': '🏠',
        'subtypes': [
            'Wall damage',
            'Floor issues',
            'Door/window problems',
            'Ceiling leak'
        ]
    },
    'Other': {
        'emoji': '🔧',
        'subtypes': ['Other maintenance issue']
    }
}

# Webhook secret storage
WEBHOOK_SECRET = {}

def get_task_field_value(task, field_name):
    """
    Enhanced field value extraction with more robust handling
    
    Args:
        task (dict): Asana task dictionary
        field_name (str): Name of the field to extract
    
    Returns:
        str or None: Extracted field value
    """
    try:
        # Normalize field name to handle variations
        field_name = field_name.lower().strip()
        
        # Check if custom fields exist
        if 'custom_fields' not in task:
            return None
        
        for field in task.get('custom_fields', []):
            # Try matching field names more flexibly
            field_label = field.get('name', '').lower().strip()
            
            # Matching logic for different field types
            if field_label == field_name:
                if field['type'] == 'text':
                    return field.get('text_value', '').strip()
                elif field['type'] == 'enum':
                    if field.get('enum_value'):
                        return field['enum_value'].get('name', '').strip()
                elif field['type'] == 'multi_enum':
                    # Handle multi-select fields
                    if field.get('enum_values'):
                        return ', '.join([
                            val.get('name', '').strip() 
                            for val in field['enum_values']
                        ])
                elif field['type'] == 'number':
                    return str(field.get('number_value', '')).strip()
        
        return None
    except Exception as e:
        logger.error(f"Error extracting field {field_name}: {e}")
        return None

def create_category_subtasks(task_gid, issue_category, urgency='Standard'):
    """Create appropriate subtasks based on the repair category and urgency"""
    try:
        # Define base subtasks for all repair requests
        base_subtasks = [
            "Initial assessment",
            "Contact tenant to confirm details",
            "Schedule inspection"
        ]
        
        # Urgency-specific modifications
        if urgency == 'Emergency':
            base_subtasks.insert(1, "Immediate safety check")
            base_subtasks.insert(2, "Expedite emergency response")
        
        # Category-specific subtasks
        category_subtasks = REPAIR_CATEGORIES.get(issue_category, {}).get('subtypes', [])
        
        # Combine subtasks
        all_subtasks = base_subtasks + category_subtasks + [
            "Procure necessary resources",
            "Execute repair",
            "Verify repair completion",
            "Follow up with tenant"
        ]
        
        # Create subtasks in Asana
        for subtask_name in all_subtasks:
            client.tasks.create_subtask_for_task(task_gid, {'name': subtask_name})
            
        logger.info(f"Created {len(all_subtasks)} subtasks for task {task_gid}")
        return True
    except Exception as e:
        logger.error(f"Error creating subtasks: {e}")
        return False

def send_email_notification(request_details, task_gid):
    """
    Send a comprehensive email notification about the repair request
    
    Args:
        request_details (dict): Comprehensive details of the repair request
        task_gid (str): Asana task ID
    
    Returns:
        bool: Success of email sending
    """
    try:
        # Determine appropriate emojis based on urgency and category
        urgency_emojis = {
            'Emergency': '🚨',
            'Urgent': '⚠️',
            'Standard': '📝'
        }
        
        category_emojis = {
            'Appliance': '🔌',
            'Electrical': '⚡',
            'Plumbing': '🚿',
            'HVAC': '❄️',
            'Structural': '🏠',
            'Other': '🔧'
        }
        
        # Get emojis, default to generic if not found
        urgency_emoji = urgency_emojis.get(request_details.get('urgency_level', 'Standard'), '📝')
        category_emoji = category_emojis.get(request_details.get('issue_category', 'Other'), '🔧')
        
        # Construct full tenant name
        full_name = f"{request_details.get('first_name', '')} {request_details.get('last_name', '')}".strip()
        
        # Create email subject
        subject = f"{urgency_emoji} {category_emoji} Repair Request - {request_details.get('issue_category', 'Maintenance')} Issue"
        
        # Create email body with enhanced formatting
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; line-height: 1.6;">
            <div style="background-color: #f4f4f4; padding: 20px; border-radius: 10px;">
                <h2 style="color: #333; border-bottom: 2px solid #0073ea; padding-bottom: 10px;">
                    {urgency_emoji} Repair Request Notification {category_emoji}
                </h2>
                
                <div style="background-color: white; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
                    <h3 style="margin-bottom: 10px; color: #0073ea;">Tenant Details</h3>
                    <p><strong>Name:</strong> {full_name}</p>
                    <p><strong>Email:</strong> {request_details.get('email', 'N/A')}</p>
                    <p><strong>Phone:</strong> {request_details.get('phone', 'N/A')}</p>
                </div>
                
                <div style="background-color: white; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
                    <h3 style="margin-bottom: 10px; color: #0073ea;">Property Information</h3>
                    <p><strong>Address:</strong> {request_details.get('address', 'Unknown')}</p>
                    <p><strong>Unit Number:</strong> {request_details.get('unit_number', 'N/A')}</p>
                </div>
                
                <div style="background-color: white; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
                    <h3 style="margin-bottom: 10px; color: #0073ea;">Issue Details</h3>
                    <p><strong>Category:</strong> {category_emoji} {request_details.get('issue_category', 'Other')}</p>
                    <p><strong>Specific Issue:</strong> {request_details.get('specific_issue', 'Not Specified')}</p>
                    <p><strong>Urgency:</strong> {urgency_emoji} {request_details.get('urgency_level', 'Standard')}</p>
                </div>
                
                <div style="background-color: #fffae6; padding: 15px; border-left: 4px solid #ffc107; margin-bottom: 15px;">
                    <h3 style="margin-bottom: 10px; color: #856404;">Detailed Description</h3>
                    <p style="font-style: italic;">{request_details.get('description', 'No description provided')}</p>
                </div>
                
                <div style="background-color: #e6f3ff; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
                    <h3 style="margin-bottom: 10px; color: #0056b3;">📸 Additional Images</h3>
                    <p>If you have additional photos or documents related to this repair request, please email them to <strong>maintenance@yourcompany.com</strong>.</p>
                    <p style="font-size: 0.9em; color: #666;">Please include the property address and unit number in the email subject line.</p>
                </div>
                
                <p style="text-align: center; margin-top: 20px;">
                    <a href="https://app.asana.com/0/{REPAIR_PROJECT_ID}/{task_gid}" 
                       style="background-color: #0073ea; color: white; padding: 10px 20px; 
                              text-decoration: none; border-radius: 5px;">
                        View Task in Asana
                    </a>
                </p>
                
                <p style="color: #666; font-size: 0.8em; text-align: center; margin-top: 20px;">
                    This is an automated notification from the Property Management Repair System.
                </p>
            </div>
        </body>
        </html>
        """
        
        # Setup and send email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = EMAIL_CONFIG['user']
        msg['To'] = EMAIL_CONFIG['distribution_list']
        
        html_part = MIMEText(body, 'html')
        msg.attach(html_part)
        
        # Send email
        server = smtplib.SMTP(EMAIL_CONFIG['server'], EMAIL_CONFIG['port'])
        server.starttls()
        server.login(EMAIL_CONFIG['user'], EMAIL_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email notification sent for task {task_gid}")
        return True
    except Exception as e:
        logger.error(f"Error sending email notification: {e}")
        return False

def process_repair_request(task):
    """
    Process a new repair request task with enhanced field extraction
    
    Args:
        task (dict): Asana task dictionary
    
    Returns:
        bool: Success of processing
    """
    try:
        # Get full task details
        task_gid = task['gid']
        task_details = client.tasks.find_by_id(task_gid)
        
        # Extract form field values with more comprehensive mapping
        tenant_info = {
            'first_name': get_task_field_value(task_details, 'First Name') or 'Unknown',
            'last_name': get_task_field_value(task_details, 'Last Name') or '',
            'email': get_task_field_value(task_details, 'Email Address') or 'N/A',
            'phone': get_task_field_value(task_details, 'Phone Number') or 'N/A'
        }
        
        property_info = {
            'address': get_task_field_value(task_details, 'Property Address') or 'Unknown',
            'unit_number': get_task_field_value(task_details, 'Unit Number') or 'N/A'
        }
        
        # Urgency and issue details
        issue_details = {
            'urgency_level': get_task_field_value(task_details, 'Urgency Level') or 'Standard',
            'issue_category': get_task_field_value(task_details, 'Issue Category') or 'Other',
            'specific_issue': (
                get_task_field_value(task_details, 'What kind of standard issue') or 
                get_task_field_value(task_details, 'What kind of emergency issue') or 
                'Unspecified'
            ),
            'description': task_details.get('notes', 'No additional description provided')
        }
        
        # Combine all information for comprehensive logging and processing
        full_request_details = {
            **tenant_info,
            **property_info,
            **issue_details
        }
        
        # Log the full request details for debugging
        logger.info(f"Repair Request Details: {full_request_details}")
        
        # Create subtasks based on the issue category and urgency
        create_category_subtasks(
            task_gid, 
            issue_details['issue_category'],
