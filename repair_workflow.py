import os
import logging
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asana
from datetime import datetime, timedelta

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

# CONFIGURATION VARIABLES
ASANA_TOKEN = os.environ.get('ASANA_TOKEN')
REPAIR_PROJECT_ID = os.environ.get('REPAIR_PROJECT_ID', '1209602262926911')
SUBTASKS_PROJECT_ID = os.environ.get('SUBTASKS_PROJECT_ID', REPAIR_PROJECT_ID)

# Email Configuration
EMAIL_CONFIG = {
    'user': os.environ.get('EMAIL_USER'),
    'password': os.environ.get('EMAIL_PASSWORD'),
    'server': os.environ.get('EMAIL_SERVER', 'smtp.gmail.com'),
    'port': int(os.environ.get('EMAIL_PORT', 587)),
    'distribution_list': os.environ.get('EMAIL_DISTRIBUTION_LIST', 'maintenance@yourcompany.com')
}

# Asana API setup - updated client initialization
client = asana.Client.access_token(ASANA_TOKEN)

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

def get_task_field_value(task, field_name):
    """Extract a field value from a task's custom fields"""
    if 'custom_fields' not in task:
        return None
    
    for field in task['custom_fields']:
        if field['name'] == field_name:
            if field['type'] == 'enum' and field.get('enum_value'):
                return field['enum_value']['name']
            elif field['type'] == 'text':
                return field['text_value']
            elif field['type'] == 'number':
                return field['number_value']
            else:
                return None
    return None

def is_repair_form_task(task):
    """Determine if a task is a repair form submission with a more flexible approach"""
    logger.info(f"Checking if task {task.get('gid', 'unknown')} is a repair form task")
    
    # Log the task name to help with debugging
    logger.info(f"Task name: {task.get('name', 'unknown')}")
    
    # First try to check for specific custom fields
    if 'custom_fields' in task:
        logger.info(f"Task has {len(task['custom_fields'])} custom fields")
        
        # Check if any field contains "category" or "urgency" in its name
        has_category = False
        has_urgency = False
        
        for field in task['custom_fields']:
            field_name = field.get('name', '').lower()
            logger.info(f"Field: {field.get('name')} - Type: {field.get('type')}")
            
            # Check for category field
            if 'category' in field_name or 'issue' in field_name:
                has_category = True
                logger.info(f"Found category field: {field.get('name')}")
            
            # Check for urgency field
            if 'urgency' in field_name or 'priority' in field_name:
                has_urgency = True
                logger.info(f"Found urgency field: {field.get('name')}")
        
        # If we found both category and urgency, it's likely a repair form
        if has_category and has_urgency:
            logger.info(f"Task {task.get('gid', 'unknown')} IS a repair form task (by field names)")
            return True
    
    # Fall back to checking task name and description
    task_name = task.get('name', '').lower()
    task_notes = task.get('notes', '').lower()
    
    # Keywords that suggest this is a repair request
    repair_keywords = ['repair', 'fix', 'broken', 'issue', 'not working', 'problem', 'maintenance']
    
    # Check if any repair keywords are in the task name or notes
    for keyword in repair_keywords:
        if keyword in task_name or keyword in task_notes:
            logger.info(f"Task {task.get('gid', 'unknown')} IS a repair form task (by keywords)")
            return True
    
    logger.info(f"Task {task.get('gid', 'unknown')} is NOT a repair form task")
    return False

def extract_repair_details(task):
    """Extract all relevant details from a repair request task with a more flexible approach"""
    details = {
        'first_name': None,
        'last_name': None,
        'email': None,
        'phone': None,
        'address': None,
        'unit_number': None,
        'urgency_level': None,
        'issue_category': None,
        'specific_issue': None,
        'description': task.get('notes', '')
    }
    
    # Extract from task name and notes if available
    task_name = task.get('name', '')
    task_notes = task.get('notes', '')
    
    # Try to find information in custom fields
    if 'custom_fields' in task:
        for field in task['custom_fields']:
            field_name = field.get('name', '').lower()
            
            # Extract category
            if 'category' in field_name or 'issue' in field_name:
                if field.get('type') == 'enum' and field.get('enum_value'):
                    details['issue_category'] = field.get('enum_value').get('name')
                elif field.get('type') == 'text':
                    details['issue_category'] = field.get('text_value')
            
            # Extract urgency
            elif 'urgency' in field_name or 'priority' in field_name:
                if field.get('type') == 'enum' and field.get('enum_value'):
                    details['urgency_level'] = field.get('enum_value').get('name')
                elif field.get('type') == 'text':
                    details['urgency_level'] = field.get('text_value')
            
            # Extract other fields
            elif 'name' in field_name and not details['first_name']:
                if field.get('type') == 'text':
                    name_parts = field.get('text_value', '').split()
                    if name_parts:
                        details['first_name'] = name_parts[0]
                        if len(name_parts) > 1:
                            details['last_name'] = ' '.join(name_parts[1:])
            
            elif 'email' in field_name and not details['email']:
                if field.get('type') == 'text':
                    details['email'] = field.get('text_value')
            
            elif 'phone' in field_name and not details['phone']:
                if field.get('type') == 'text':
                    details['phone'] = field.get('text_value')
            
            elif 'address' in field_name and not details['address']:
                if field.get('type') == 'text':
                    details['address'] = field.get('text_value')
            
            elif 'unit' in field_name and not details['unit_number']:
                if field.get('type') == 'text':
                    details['unit_number'] = field.get('text_value')
    
    # Set fallback values for missing fields
    if not details['issue_category']:
        # Try to determine category from task name or notes
        categories = ['Plumbing', 'Electrical', 'Appliance', 'HVAC', 'Structural']
        for category in categories:
            if category.lower() in task_name.lower() or category.lower() in task_notes.lower():
                details['issue_category'] = category
                break
        
        # If still no category, default to "Other"
        if not details['issue_category']:
            details['issue_category'] = 'Other'
    
    if not details['urgency_level']:
        details['urgency_level'] = 'Standard'
    
    # If no name was found, use "Tenant" as default
    if not details['first_name']:
        details['first_name'] = 'Tenant'
    
    # If no address was found, extract from task name or use "Property" as default
    if not details['address']:
        details['address'] = 'Property'
    
    return details

def create_subtasks(parent_task_gid, category):
    """Create category-specific subtasks for the repair request"""
    category_info = REPAIR_CATEGORIES.get(category, REPAIR_CATEGORIES['Other'])
    subtasks_created = 0
    
    for subtype in category_info.get('subtypes', []):
        try:
            # Create subtask with proper fields
            subtask = client.tasks.create_subtask_for_task(
                parent_task_gid,
                {'name': f"{category_info['emoji']} {subtype}",
                 'projects': [SUBTASKS_PROJECT_ID]}
            )
            subtasks_created += 1
        except Exception as e:
            logger.error(f"Failed to create subtask '{subtype}': {str(e)}")
    
    return subtasks_created > 0

def send_email_notification(repair_details, task_gid):
    """Send email notification about the new repair request"""
    if not all([EMAIL_CONFIG['user'], EMAIL_CONFIG['password']]):
        logger.warning("Email configuration incomplete. Skipping notification.")
        return False
    
    try:
        # Create message
        message = MIMEMultipart()
        message['From'] = EMAIL_CONFIG['user']
        message['To'] = EMAIL_CONFIG['distribution_list']
        message['Subject'] = f"New Repair Request: {repair_details.get('issue_category', 'Maintenance')} - {repair_details.get('address', 'Property')}"
        
        # Construct email body
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2>New Property Repair Request</h2>
            <p><strong>Tenant:</strong> {repair_details.get('first_name', '')} {repair_details.get('last_name', '')}</p>
            <p><strong>Contact:</strong> {repair_details.get('email', '')} | {repair_details.get('phone', '')}</p>
            <p><strong>Property:</strong> {repair_details.get('address', '')}, Unit {repair_details.get('unit_number', 'N/A')}</p>
            <p><strong>Urgency Level:</strong> {repair_details.get('urgency_level', 'Standard')}</p>
            <p><strong>Issue Category:</strong> {repair_details.get('issue_category', 'Other')}</p>
            <p><strong>Specific Issue:</strong> {repair_details.get('specific_issue', 'N/A')}</p>
            <p><strong>Description:</strong><br>{repair_details.get('description', 'No additional details provided.')}</p>
            <p><a href="https://app.asana.com/0/0/{task_gid}" style="background-color: #796eff; color: white; padding: 10px 15px; text-decoration: none; border-radius: 4px;">View Task in Asana</a></p>
        </body>
        </html>
        """
        
        message.attach(MIMEText(body, 'html'))
        
        # Connect to server and send
        server = smtplib.SMTP(EMAIL_CONFIG['server'], EMAIL_CONFIG['port'])
        server.starttls()
        server.login(EMAIL_CONFIG['user'], EMAIL_CONFIG['password'])
        server.send_message(message)
        server.quit()
        
        logger.info(f"Email notification sent for task {task_gid}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to send email notification: {str(e)}")
        return False

def process_repair_request(task):
    """Process a repair request task from start to finish"""
    task_gid = task['gid']
    logger.info(f"Processing repair request task: {task_gid}")
    
    try:
        # Check if task has already been processed
        for story in client.stories.find_by_task(task_gid):
            if "Repair request processed" in story.get('text', ''):
                logger.info(f"Task {task_gid} already processed. Skipping.")
                return True
        
        # Extract repair details
        repair_details = extract_repair_details(task)
        
        # Update task with formatting and category icon
        category = repair_details.get('issue_category', 'Other')
        category_info = REPAIR_CATEGORIES.get(category, REPAIR_CATEGORIES['Other'])
        
        # Update the task name with emoji and improve formatting
        updated_name = f"{category_info['emoji']} {repair_details.get('issue_category', 'Repair')} - {repair_details.get('address', 'Property')}"
        
        client.tasks.update(task_gid, {
            'name': updated_name
        })
        
        # Create subtasks based on category
        subtask_result = create_subtasks(task_gid, category)
        
        # Send email notification
        email_result = send_email_notification(repair_details, task_gid)
        
        # Add comment to track processing
        client.stories.create_on_task(task_gid, {
            'text': "Repair request processed by system:\n"
                    f"✅ Task formatted\n"
                    f"{'✅' if subtask_result else '❌'} Category-specific subtasks created\n"
                    f"{'✅' if email_result else '❌'} Notification email sent"
        })
        
        logger.info(f"Successfully processed repair request {task_gid}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to process repair task {task_gid}: {str(e)}")
        # Try to add error note to task
        try:
            client.stories.create_on_task(task_gid, {
                'text': f"⚠️ Error processing repair request: {str(e)}"
            })
        except:
            pass
        return False
