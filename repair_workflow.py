import os
import logging
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asana  # Simple import
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
client = asana.client.Client.access_token(ASANA_TOKEN)  # Updated client initialization

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

# The rest of the functions (get_task_field_value, process_repair_request, etc.) 
# remain the same as in the previous implementation
