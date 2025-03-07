# AsanaConnector3Claude
Property Repair Management Workflow Automation
Overview
This Flask-based application automates the property repair request process using Asana and email notifications. The system streamlines repair management by:

Capturing tenant repair requests
Creating structured Asana tasks
Generating dynamic subtasks
Sending email notifications
Tracking repair progress

Features
🔧 Automated Repair Workflow

Webhook integration with Asana
Automatic subtask generation
Categorized repair tracking
Email notifications

Repair Categories

Plumbing 🚿
Electrical ⚡
Appliance 🔌
HVAC ❄️
Structural 🏠
Other 🔧

Prerequisites

Python 3.8+
Asana Account
SMTP Email Service
Railway or similar PaaS

Environment Variables
Set the following environment variables:
Asana Configuration

ASANA_TOKEN: Your Asana Personal Access Token
REPAIR_PROJECT_ID: Asana project ID for repair requests
SUBTASKS_PROJECT_ID: Project ID for creating subtasks (can be same as repair project)

Email Configuration

EMAIL_USER: SMTP email username
EMAIL_PASSWORD: SMTP email password
EMAIL_SERVER: SMTP server (default: smtp.gmail.com)
EMAIL_PORT: SMTP port (default: 587)
EMAIL_DISTRIBUTION_LIST: Comma-separated list of notification recipients

Asana Form Design
Required Fields

Tenant Information

Full Name
Contact Email
Phone Number


Property Details

Property/Unit Address
Unit Number


Repair Request

Issue Category (Dropdown)

Plumbing
Electrical
Appliance
HVAC
Structural
Other


Urgency Level (Dropdown)

Low
Standard
Urgent
Emergency


Detailed Description
Optional: Upload Photos/Documents



Workflow Process

Tenant submits repair request via Asana form
Webhook triggers task creation in Asana
System generates category-specific subtasks
Email notification sent to distribution list
Maintenance team tracks and updates task

Installation
bashCopy# Clone the repository
git clone <your-repo-url>

# Install dependencies
pip install -r requirements.txt

# Set environment variables
# (Use Railway or local .env file)

# Run the application
python main.py
Endpoints

/webhook: Asana webhook handler
/setup: Initialize webhook
/manual-trigger: Manual workflow management
/process-recent: Process recent repair requests
/test-email: Send test email notification

Logging
Logs are written to:

Console
repair_workflow.log file

Contributing

Fork the repository
Create feature branch
Commit changes
Push to branch
Create pull request

License
[Your License Here]
Support
For issues or questions, contact [Your Contact Information]
