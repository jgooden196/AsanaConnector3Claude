import os
import logging
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asana
from asana.rest import ApiException
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

# Asana API setup
client = asana.Client.access_token(ASANA_TOKEN)

# Repair Categories Configuration
REPAIR_CATEGORIES = {
    'Appliance': {
        'emoji': '🔌',
        'subtypes': [
            'Washer not working', 'Dryer not working', 
            'Dishwasher not working', 'Stove/Oven issues',
            'Refrigerator problems'
        ]
    },
    'Electrical': {
        'emoji': '⚡',
        'subtypes': [
            'Broken electrical outlet', 'Light switch not working',
            'Flickering lights', 'Electrical panel issue'
        ]
    },
    # (Rest of the REPAIR_CATEGORIES remains the same)
    'Other': {
        'emoji': '🔧',
        'subtypes': ['Other maintenance issue']
    }
}

def get_task_field_value(task, field_name):
    """Enhanced field value extraction with robust handling"""
    # (Your existing get_task_field_value function)
    try:
        field_name = field_name.lower().strip()
        
        if 'custom_fields' not in task:
            return None
        
        for field in task.get('custom_fields', []):
            field_label = field.get('name', '').lower().strip()
            
            if field_label == field_name:
                if field['type'] == 'text':
                    return field.get('text_value', '').strip()
                elif field['type'] == 'enum':
                    if field.get('enum_value'):
                        return field['enum_value'].get('name', '').strip()
                elif field['type'] == 'multi_enum':
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
    # (Your existing create_category_subtasks function)
    try:
        base_subtasks = [
            "Initial assessment",
            "Contact tenant to confirm details",
            "Schedule inspection"
        ]
        
        if urgency == 'Emergency':
            base_subtasks.insert(1, "Immediate safety check")
            base_subtasks.insert(2, "Expedite emergency response")
        
        category_subtasks = REPAIR_CATEGORIES.get(issue_category, {}).get('subtypes', [])
        
        all_subtasks = base_subtasks + category_subtasks + [
            "Procure necessary resources",
            "Execute repair",
            "Verify repair completion",
            "Follow up with tenant"
        ]
        
        for subtask_name in all_subtasks:
            client.tasks.create_subtask_for_task(task_gid, {'name': subtask_name})
            
        logger.info(f"Created {len(all_subtasks)} subtasks for task {task_gid}")
        return True
    except Exception as e:
        logger.error(f"Error creating subtasks: {e}")
        return False

def send_email_notification(request_details, task_gid):
    """Send a comprehensive email notification about the repair request"""
    # (Your existing send_email_notification function)
    # (Make sure to use the EMAIL_CONFIG from this file)
    try:
        # Emoji and email body logic remains the same
        # Just ensure you're using EMAIL_CONFIG from this file
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Repair Request - {request_details.get('issue_category', 'Maintenance')} Issue"
        msg['From'] = EMAIL_CONFIG['user']
        msg['To'] = EMAIL_CONFIG['distribution_list']
        
        html_part = MIMEText(body, 'html')
        msg.attach(html_part)
        
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
    """Process a new repair request task with enhanced field extraction"""
    try:
        task_gid = task['gid']
        task_details = client.tasks.find_by_id(task_gid)
        
        # (Rest of your existing process_repair_request function)
        tenant_info = {
            'first_name': get_task_field_value(task_details, 'First Name') or 'Unknown',
            'last_name': get_task_field_value(task_details, 'Last Name') or '',
            'email': get_task_field_value(task_details, 'Email Address') or 'N/A',
            'phone': get_task_field_value(task_details, 'Phone Number') or 'N/A'
        }
        
        # Continue with the rest of the processing...
        
        send_email_notification(full_request_details, task_gid)
        
        return True
    except Exception as e:
        logger.error(f"Error processing repair request: {e}")
        return False

def is_repair_form_task(task):
    """Check if a task was created from the repair request form"""
    try:
        for project in task.get('projects', []):
            if project['gid'] == REPAIR_PROJECT_ID:
                return True
        return False
    except Exception as e:
        logger.error(f"Error checking if task is from repair form: {e}")
        return False

# Note: Remove any Flask route handlers from this file
