#!/usr/bin/env python3
"""
ClickUp API Setup Script for Fido Ticketing System
Creates complete workspace structure, custom fields, and exports configuration
"""

import requests
import json
import time
from datetime import datetime

class ClickUpSetup:
    def __init__(self, api_token, team_id):
        self.api_token = api_token
        self.team_id = team_id
        self.base_url = "https://api.clickup.com/api/v2"
        self.headers = {
            "Authorization": api_token,
            "Content-Type": "application/json"
        }
        self.config = {
            "workspace_id": team_id,
            "space_id": None,
            "folder_id": None,
            "lists": {},
            "custom_fields": {},
            "statuses": {},
            "created_at": datetime.now().isoformat()
        }
    
    def make_request(self, method, endpoint, data=None):
        """Make API request with error handling"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            elif method == "PUT":
                response = requests.put(url, headers=self.headers, json=data)
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            return None
    
    def create_space(self):
        """Create Fido Operations Space"""
        print("🚀 Creating Fido Operations Space...")
        
        space_data = {
            "name": "Fido Operations",
            "multiple_assignees": True,
            "features": {
                "due_dates": {"enabled": True},
                "time_tracking": {"enabled": True},
                "tags": {"enabled": True},
                "time_estimates": {"enabled": True},
                "checklists": {"enabled": True},
                "custom_fields": {"enabled": True},
                "remap_dependencies": {"enabled": True},
                "dependency_warning": {"enabled": True},
                "portfolios": {"enabled": True}
            }
        }
        
        result = self.make_request("POST", f"/team/{self.team_id}/space", space_data)
        
        if result:
            self.config["space_id"] = result["id"]
            print(f"✅ Space created: {result['name']} (ID: {result['id']})")
            return result["id"]
        else:
            print("❌ Failed to create space")
            return None
    
    def create_folder(self, space_id):
        """Create CX Tickets Folder"""
        print("📁 Creating CX Tickets Folder...")
        
        folder_data = {
            "name": "CX Tickets"
        }
        
        result = self.make_request("POST", f"/space/{space_id}/folder", folder_data)
        
        if result:
            self.config["folder_id"] = result["id"]
            print(f"✅ Folder created: {result['name']} (ID: {result['id']})")
            return result["id"]
        else:
            print("❌ Failed to create folder")
            return None
    
    def create_lists(self, folder_id):
        """Create all three ticket lists"""
        print("📋 Creating ticket lists...")
        
        lists_config = [
            {
                "name": "Service Issues",
                "key": "service_issues",
                "content": "Customer service issues and complaints requiring operations team attention"
            },
            {
                "name": "Customer Inquiries", 
                "key": "customer_inquiries",
                "content": "Customer questions and inquiries requiring CX team response"
            },
            {
                "name": "Unit Management",
                "key": "unit_management", 
                "content": "Unit changes, additions, cancellations requiring BPO team processing"
            }
        ]
        
        for list_config in lists_config:
            print(f"  Creating {list_config['name']}...")
            
            list_data = {
                "name": list_config["name"],
                "content": list_config["content"],
                "due_date": None,
                "due_date_time": False,
                "priority": None,
                "assignee": None,
                "status": "red"
            }
            
            result = self.make_request("POST", f"/folder/{folder_id}/list", list_data)
            
            if result:
                self.config["lists"][list_config["key"]] = {
                    "id": result["id"],
                    "name": result["name"]
                }
                print(f"  ✅ {result['name']} created (ID: {result['id']})")
            else:
                print(f"  ❌ Failed to create {list_config['name']}")
        
        return len(self.config["lists"]) == 3
    
    def create_custom_fields(self):
        """Create all custom fields for each list"""
        print("🔧 Creating custom fields...")
        
        # Universal fields for all lists
        universal_fields = [
            {
                "name": "Slack Ticket ID",
                "type": "short_text",
                "required": True,
                "description": "Unique ticket identifier from Slack (FI-, FQ-, FU-)"
            },
            {
                "name": "Slack Permalink", 
                "type": "url",
                "required": True,
                "description": "Direct link to Slack thread"
            },
            {
                "name": "Submitted By",
                "type": "short_text", 
                "required": True,
                "description": "Slack user who created the ticket"
            },
            {
                "name": "Property Address",
                "type": "short_text",
                "required": True,
                "description": "Full property address including unit"
            },
            {
                "name": "Client Name",
                "type": "short_text",
                "required": True,
                "description": "Property manager or client company"
            },
            {
                "name": "Market Code",
                "type": "drop_down",
                "required": True,
                "description": "Service market location",
                "type_config": {
                    "options": [
                        {"name": "ANA", "color": "#FF6B6B"},
                        {"name": "ATX", "color": "#4ECDC4"},
                        {"name": "CHS", "color": "#45B7D1"},
                        {"name": "CLT", "color": "#96CEB4"},
                        {"name": "DEN", "color": "#FFEAA7"},
                        {"name": "DFW", "color": "#DDA0DD"},
                        {"name": "FLL", "color": "#98D8C8"},
                        {"name": "GEG", "color": "#F7DC6F"},
                        {"name": "HOT", "color": "#BB8FCE"},
                        {"name": "JAX", "color": "#85C1E9"},
                        {"name": "LAX", "color": "#F8C471"},
                        {"name": "LIT", "color": "#82E0AA"},
                        {"name": "PHX", "color": "#F1948A"},
                        {"name": "PIE", "color": "#85C1E9"},
                        {"name": "SAN", "color": "#A9DFBF"},
                        {"name": "SAT", "color": "#D7BDE2"},
                        {"name": "SDX", "color": "#FAD7A0"},
                        {"name": "SEA", "color": "#AED6F1"},
                        {"name": "SLC", "color": "#A3E4D7"},
                        {"name": "SRQ", "color": "#D5A6BD"},
                        {"name": "STA", "color": "#F9E79F"},
                        {"name": "STS", "color": "#ABEBC6"},
                        {"name": "VPS", "color": "#D2B4DE"},
                        {"name": "MISC", "color": "#BDC3C7"}
                    ]
                }
            },
            {
                "name": "Date Created",
                "type": "date",
                "required": True,
                "description": "Date ticket was submitted"
            },
            {
                "name": "Source Method",
                "type": "drop_down",
                "required": True,
                "description": "How the issue was reported",
                "type_config": {
                    "options": [
                        {"name": "OpenPhone Text", "color": "#3498DB"},
                        {"name": "Phone Call", "color": "#E74C3C"},
                        {"name": "Email", "color": "#F39C12"},
                        {"name": "Slack Message", "color": "#9B59B6"},
                        {"name": "Website Form", "color": "#1ABC9C"},
                        {"name": "In-Person", "color": "#34495E"},
                        {"name": "Internal Discovery", "color": "#95A5A6"}
                    ]
                }
            },
            {
                "name": "Source Reference",
                "type": "short_text",
                "required": False,
                "description": "Message ID, email, or other reference"
            }
        ]
        
        # Service Issues specific fields
        service_issue_fields = [
            {
                "name": "Issue Type",
                "type": "drop_down",
                "required": True,
                "description": "Category of service issue",
                "type_config": {
                    "options": [
                        {"name": "Bin Placement Issue", "color": "#E74C3C"},
                        {"name": "Property Access Problem", "color": "#F39C12"},
                        {"name": "Schedule Conflict", "color": "#F1C40F"},
                        {"name": "Property Logistics Issue", "color": "#3498DB"},
                        {"name": "Service Quality Issue", "color": "#9B59B6"},
                        {"name": "Customer Complaint", "color": "#E67E22"},
                        {"name": "Equipment Issue", "color": "#34495E"},
                        {"name": "Other Issue", "color": "#95A5A6"}
                    ]
                }
            },
            {
                "name": "Priority Level",
                "type": "drop_down",
                "required": True,
                "description": "Issue urgency and resolution timeframe",
                "type_config": {
                    "options": [
                        {"name": "URGENT - Immediate Response", "color": "#C0392B"},
                        {"name": "HIGH - Same Day Resolution", "color": "#E74C3C"},
                        {"name": "NORMAL - Next Business Day", "color": "#F39C12"},
                        {"name": "LOW - When Available", "color": "#27AE60"}
                    ]
                }
            },
            {
                "name": "Issue Description",
                "type": "long_text",
                "required": True,
                "description": "Detailed description of the problem"
            },
            {
                "name": "Resolution Status",
                "type": "drop_down",
                "required": False,
                "description": "Current resolution status",
                "type_config": {
                    "options": [
                        {"name": "Open", "color": "#E74C3C"},
                        {"name": "In Progress", "color": "#F39C12"},
                        {"name": "Resolved", "color": "#27AE60"},
                        {"name": "Closed", "color": "#95A5A6"}
                    ]
                }
            },
            {
                "name": "Assigned Operator",
                "type": "short_text",
                "required": False,
                "description": "Operations team member assigned"
            },
            {
                "name": "Resolution Notes",
                "type": "long_text",
                "required": False,
                "description": "Actions taken to resolve issue"
            }
        ]
        
        # Customer Inquiries specific fields
        customer_inquiry_fields = [
            {
                "name": "Inquiry Type",
                "type": "drop_down",
                "required": True,
                "description": "Category of customer inquiry",
                "type_config": {
                    "options": [
                        {"name": "Schedule Question", "color": "#3498DB"},
                        {"name": "Service Status Check", "color": "#1ABC9C"},
                        {"name": "Billing Question", "color": "#F39C12"},
                        {"name": "Service Details", "color": "#9B59B6"},
                        {"name": "New Service Interest", "color": "#27AE60"},
                        {"name": "Pause/Resume Service", "color": "#E67E22"},
                        {"name": "Property Information Update", "color": "#34495E"},
                        {"name": "General Information", "color": "#95A5A6"},
                        {"name": "Other Question", "color": "#BDC3C7"}
                    ]
                }
            },
            {
                "name": "Response Priority",
                "type": "drop_down",
                "required": True,
                "description": "Response urgency level",
                "type_config": {
                    "options": [
                        {"name": "URGENT - Customer Waiting", "color": "#C0392B"},
                        {"name": "HIGH - Same Day", "color": "#E74C3C"},
                        {"name": "NORMAL - Next Day", "color": "#F39C12"},
                        {"name": "LOW - When Available", "color": "#27AE60"}
                    ]
                }
            },
            {
                "name": "Customer Question",
                "type": "long_text",
                "required": True,
                "description": "Detailed customer inquiry or question"
            },
            {
                "name": "Response Status",
                "type": "drop_down",
                "required": False,
                "description": "Current response status",
                "type_config": {
                    "options": [
                        {"name": "Pending", "color": "#E74C3C"},
                        {"name": "In Progress", "color": "#F39C12"},
                        {"name": "Responded", "color": "#27AE60"},
                        {"name": "Closed", "color": "#95A5A6"}
                    ]
                }
            },
            {
                "name": "Assigned CX Rep",
                "type": "short_text",
                "required": False,
                "description": "CX team member handling inquiry"
            },
            {
                "name": "Response Notes",
                "type": "long_text",
                "required": False,
                "description": "Response provided to customer"
            },
            {
                "name": "Follow-up Required",
                "type": "checkbox",
                "required": False,
                "description": "Whether additional follow-up is needed"
            }
        ]
        
        # Unit Management specific fields
        unit_management_fields = [
            {
                "name": "Change Type",
                "type": "drop_down",
                "required": True,
                "description": "Type of unit management change",
                "type_config": {
                    "options": [
                        {"name": "NEW UNIT", "color": "#27AE60"},
                        {"name": "CANCELLATION", "color": "#E74C3C"},
                        {"name": "PAUSE SERVICE", "color": "#F39C12"},
                        {"name": "RESTART SERVICE", "color": "#3498DB"},
                        {"name": "MODIFY SERVICE", "color": "#9B59B6"}
                    ]
                }
            },
            {
                "name": "Trash Pickup Day",
                "type": "drop_down",
                "required": False,  # Conditionally required for NEW UNIT
                "description": "Scheduled trash pickup day",
                "type_config": {
                    "options": [
                        {"name": "Monday", "color": "#E74C3C"},
                        {"name": "Tuesday", "color": "#F39C12"},
                        {"name": "Wednesday", "color": "#F1C40F"},
                        {"name": "Thursday", "color": "#27AE60"},
                        {"name": "Friday", "color": "#3498DB"},
                        {"name": "Saturday", "color": "#9B59B6"},
                        {"name": "Sunday", "color": "#E67E22"}
                    ]
                }
            },
            {
                "name": "Recycling Day",
                "type": "drop_down",
                "required": False,
                "description": "Scheduled recycling pickup day",
                "type_config": {
                    "options": [
                        {"name": "Same as Trash", "color": "#1ABC9C"},
                        {"name": "Monday", "color": "#E74C3C"},
                        {"name": "Tuesday", "color": "#F39C12"},
                        {"name": "Wednesday", "color": "#F1C40F"},
                        {"name": "Thursday", "color": "#27AE60"},
                        {"name": "Friday", "color": "#3498DB"},
                        {"name": "Saturday", "color": "#9B59B6"},
                        {"name": "Sunday", "color": "#E67E22"},
                        {"name": "No Recycling", "color": "#95A5A6"}
                    ]
                }
            },
            {
                "name": "Effective Date",
                "type": "date",
                "required": True,
                "description": "Date when change should take effect"
            },
            {
                "name": "Reason for Change",
                "type": "long_text",
                "required": True,
                "description": "Business reason for the change"
            },
            {
                "name": "Special Instructions",
                "type": "long_text",
                "required": False,
                "description": "Special handling or access instructions"
            },
            {
                "name": "Processing Status",
                "type": "drop_down",
                "required": False,
                "description": "Current processing status",
                "type_config": {
                    "options": [
                        {"name": "Pending", "color": "#E74C3C"},
                        {"name": "In Progress", "color": "#F39C12"},
                        {"name": "Completed", "color": "#27AE60"},
                        {"name": "On Hold", "color": "#95A5A6"}
                    ]
                }
            },
            {
                "name": "Assigned BPO Rep",
                "type": "short_text",
                "required": False,
                "description": "BPO team member processing change"
            },
            {
                "name": "Implementation Notes",
                "type": "long_text",
                "required": False,
                "description": "Notes on implementation process"
            }
        ]
        
        # Create fields for each list
        field_sets = {
            "service_issues": universal_fields + service_issue_fields,
            "customer_inquiries": universal_fields + customer_inquiry_fields,
            "unit_management": universal_fields + unit_management_fields
        }
        
        for list_key, fields in field_sets.items():
            if list_key not in self.config["lists"]:
                continue
                
            list_id = self.config["lists"][list_key]["id"]
            print(f"  Creating fields for {self.config['lists'][list_key]['name']}...")
            
            self.config["custom_fields"][list_key] = {}
            
            for field in fields:
                field_data = {
                    "name": field["name"],
                    "type": field["type"],
                    "required": field.get("required", False)
                }
                
                # Add type-specific configuration
                if "type_config" in field:
                    field_data["type_config"] = field["type_config"]
                
                result = self.make_request("POST", f"/list/{list_id}/field", field_data)
                
                if result:
                    self.config["custom_fields"][list_key][field["name"]] = {
                        "id": result["id"],
                        "type": result["type"],
                        "required": result.get("required", False)
                    }
                    print(f"    ✅ {field['name']}")
                else:
                    print(f"    ❌ Failed to create {field['name']}")
                
                # Rate limiting
                time.sleep(0.5)
    
    def export_configuration(self):
        """Export all IDs and configuration to files"""
        print("💾 Exporting configuration...")
        
        # Main configuration file
        with open("/home/ubuntu/clickup-config.json", "w") as f:
            json.dump(self.config, f, indent=2)
        
        # Environment variables file
        env_vars = f"""# ClickUp Configuration for Fido Ticketing System
# Generated: {datetime.now().isoformat()}

# ClickUp API Configuration
CLICKUP_API_TOKEN=your_api_token_here
CLICKUP_TEAM_ID={self.team_id}
CLICKUP_SPACE_ID={self.config.get('space_id', 'SPACE_ID_HERE')}
CLICKUP_FOLDER_ID={self.config.get('folder_id', 'FOLDER_ID_HERE')}

# List IDs
CLICKUP_LIST_ID_ISSUES={self.config['lists'].get('service_issues', {}).get('id', 'LIST_ID_HERE')}
CLICKUP_LIST_ID_INQUIRIES={self.config['lists'].get('customer_inquiries', {}).get('id', 'LIST_ID_HERE')}
CLICKUP_LIST_ID_UNITS={self.config['lists'].get('unit_management', {}).get('id', 'LIST_ID_HERE')}

# Webhook Configuration
CLICKUP_WEBHOOK_SECRET=your_webhook_secret_here
"""
        
        with open("/home/ubuntu/clickup-env-vars.txt", "w") as f:
            f.write(env_vars)
        
        print("✅ Configuration exported to:")
        print("  - /home/ubuntu/clickup-config.json")
        print("  - /home/ubuntu/clickup-env-vars.txt")
    
    def run_setup(self):
        """Execute complete setup process"""
        print("🚀 Starting ClickUp Fido Ticketing Setup...")
        print(f"Team ID: {self.team_id}")
        
        # Create space
        space_id = self.create_space()
        if not space_id:
            return False
        
        # Create folder
        folder_id = self.create_folder(space_id)
        if not folder_id:
            return False
        
        # Create lists
        if not self.create_lists(folder_id):
            return False
        
        # Create custom fields
        self.create_custom_fields()
        
        # Export configuration
        self.export_configuration()
        
        print("\n🎉 ClickUp setup complete!")
        print(f"Space: Fido Operations ({space_id})")
        print(f"Folder: CX Tickets ({folder_id})")
        print(f"Lists: {len(self.config['lists'])} created")
        print(f"Custom Fields: {sum(len(fields) for fields in self.config['custom_fields'].values())} created")
        
        return True

def main():
    """Main execution function"""
    print("ClickUp Fido Ticketing System Setup")
    print("=" * 40)
    
    # Configuration - UPDATE THESE VALUES
    API_TOKEN = "YOUR_CLICKUP_API_TOKEN_HERE"  # Get from ClickUp settings
    TEAM_ID = "9013484736"  # Getfido workspace ID
    
    if API_TOKEN == "YOUR_CLICKUP_API_TOKEN_HERE":
        print("❌ Please update the API_TOKEN in the script")
        print("Get your token from: https://app.clickup.com/settings/apps")
        return
    
    # Initialize and run setup
    setup = ClickUpSetup(API_TOKEN, TEAM_ID)
    success = setup.run_setup()
    
    if success:
        print("\n✅ Setup completed successfully!")
        print("Next steps:")
        print("1. Update Railway environment variables with the exported values")
        print("2. Test API connectivity with the new structure")
        print("3. Implement Slack integration using the configuration files")
    else:
        print("\n❌ Setup failed. Check the error messages above.")

if __name__ == "__main__":
    main()

