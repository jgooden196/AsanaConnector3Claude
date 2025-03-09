import os
import logging
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from asana.client import Client  # Explicit import
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
client = Client.access_token(ASANA_TOKEN)  # Updated client initialization

# The rest of the functions remain the same
# (Include all the existing functions from the previous implementation)

def get_task_field_value(task, field_name):
    """Enhanced field value extraction with robust handling"""
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

def process_repair_request(task):
    """Process a new repair request task with enhanced field extraction"""
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
            issue_details['urgency_level']
        )
        
        # Send email notification with comprehensive details
        send_email_notification(full_request_details, task_gid)
        
        return True
    except Exception as e:
        logger.error(f"Error processing repair request: {e}")
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

# Add other supporting functions like create_category_subtasks and send_email_notification
# from your previous implementation...
