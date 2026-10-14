import os
import json
import csv
from openpyxl import Workbook

os.makedirs('demo_data/invoices', exist_ok=True)
os.makedirs('demo_data/documents', exist_ok=True)

# 1. Invoices Excel
wb_inv = Workbook()
ws_inv = wb_inv.active
ws_inv.title = 'Invoices'
ws_inv.append(['Client Name', 'Invoice Number', 'Amount', 'Invoice Date', 'Due Date', 'Payment Status', 'Client Email'])
invoices_data = [
    ['Apex Solutions', 'INV-2024-001', 45000, '2024-08-01', '2024-08-31', 'Overdue', 'billing@apexsolutions.com'],
    ['Nexus Tech', 'INV-2024-002', 18500, '2024-08-15', '2024-09-15', 'Paid', 'accounts@nexustech.io'],
    ['Quantum Corp', 'INV-2024-003', 32000, '2024-09-01', '2024-09-25', 'Unpaid', 'finance@quantumcorp.com'],
    ['Vertex Media', 'INV-2024-004', 12750, '2024-08-10', '2024-09-10', 'Overdue', 'payables@vertexmedia.org'],
    ['Horizon Labs', 'INV-2024-005', 68000, '2024-09-05', '2024-09-28', 'Unpaid', 'contact@horizonlabs.net']
]
for row in invoices_data:
    ws_inv.append(row)
try:
    wb_inv.save('demo_data/invoices.xlsx')
except PermissionError:
    print('⚠️ Note: demo_data/invoices.xlsx is currently open in Microsoft Excel. Please close Excel to update the .xlsx file.')

# Also write CSV for easy reading
with open('demo_data/invoices.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Client Name', 'Invoice Number', 'Amount', 'Invoice Date', 'Due Date', 'Payment Status', 'Client Email'])
    writer.writerows(invoices_data)

# 2. Sample Invoice Text files in demo_data/invoices/
for row in invoices_data:
    inv_file = f'demo_data/invoices/{row[1]}.txt'
    with open(inv_file, 'w', encoding='utf-8') as f:
        f.write(f'''=== TAX INVOICE ===
Invoice Number: {row[1]}
Client: {row[0]}
Billing Email: {row[6]}
Date: {row[3]}
Due Date: {row[4]}
Amount Due: INR {row[2]}
Payment Status: {row[5]}

Item Description: Enterprise Software Engineering & Cloud Support Services
Subtotal: INR {row[2] * 0.82:.2f}
GST (18%): INR {row[2] * 0.18:.2f}
Total Amount Payable: INR {row[2]:.2f}
Bank Account: HDFC BANK - AC# 5010049281729 - IFSC: HDFC0001234
''')

# 3. Products Excel
wb_prod = Workbook()
ws_prod = wb_prod.active
ws_prod.title = 'Required Products'
ws_prod.append(['Product Name', 'Category', 'Quantity', 'Max Unit Budget', 'Urgency'])
products_data = [
    ['A4 Copy Paper Ream (500 Sheets)', 'Paper & Stationery', 5, 350, 'High'],
    ['Ballpoint Pens (Pack of 50)', 'Writing Instruments', 2, 280, 'Medium'],
    ['Sticky Notes Pack (4 Pads)', 'Paper & Stationery', 4, 150, 'Low'],
    ['Whiteboard Markers (Set of 4)', 'Presentation', 3, 200, 'High']
]
for row in products_data:
    ws_prod.append(row)
wb_prod.save('demo_data/products.xlsx')

with open('demo_data/products.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Product Name', 'Category', 'Quantity', 'Max Unit Budget', 'Urgency'])
    writer.writerows(products_data)

# 4. Calendar JSON
calendar_data = [
    {'time': '09:30 AM', 'title': 'Daily Morning Standup', 'attendees': ['Team Alpha', 'Scrum Master'], 'type': 'Internal', 'notes': 'Review sprint burndown'},
    {'time': '11:00 AM', 'title': 'Q3 Deliverables Architecture Review', 'attendees': ['Lead Architect', 'Dev Team'], 'type': 'Internal', 'notes': 'API gateway architecture'},
    {'time': '03:00 PM', 'title': 'Acrom Systems Client Meeting', 'client': 'Acrom Systems', 'person': 'Sarah Jenkins (VP Operations)', 'type': 'Client', 'project': 'Acrom Cloud Portal', 'notes': 'Discussion on milestone 2 delivery and Q4 contract renewal', 'agenda': ['Milestone 2 acceptance', 'Performance benchmark review', 'Q4 retainer agreement']},
    {'time': '05:00 PM', 'title': 'Daily Wrap-up & Reporting', 'attendees': ['Engineering Manager'], 'type': 'Internal', 'notes': 'Submit daily summary'}
]
with open('demo_data/calendar.json', 'w', encoding='utf-8') as f:
    json.dump(calendar_data, f, indent=2)

# 5. Tasks JSON
tasks_data = [
    {'id': 'TASK-101', 'title': 'Prepare Acrom Systems client meeting brief & review contract specs', 'priority': 'High', 'status': 'Pending', 'due_date': 'Today, 2:30 PM', 'category': 'Client Relations'},
    {'id': 'TASK-102', 'title': 'Reconcile unpaid vendor invoices & issue reminder notices', 'priority': 'High', 'status': 'Pending', 'due_date': 'Today, 4:00 PM', 'category': 'Finance'},
    {'id': 'TASK-103', 'title': 'Order replenishment office supplies from approved catalog', 'priority': 'Medium', 'status': 'Pending', 'due_date': 'Today, 5:00 PM', 'category': 'Operations'},
    {'id': 'TASK-104', 'title': 'Prepare monthly employee activity and performance report', 'priority': 'Medium', 'status': 'Pending', 'due_date': 'Today, 6:00 PM', 'category': 'Reporting'},
    {'id': 'TASK-105', 'title': 'Update API gateway documentation in internal repository', 'priority': 'Low', 'status': 'Completed', 'due_date': 'Yesterday', 'category': 'Engineering'}
]
with open('demo_data/tasks.json', 'w', encoding='utf-8') as f:
    json.dump(tasks_data, f, indent=2)

# 6. Emails JSON
emails_data = [
    {
        'id': 'EML-001',
        'from': 'Sarah Jenkins <sjenkins@acromsystems.com>',
        'to': 'user@workpilot.com',
        'subject': 'Agenda for 3 PM Client Meeting - Milestone 2 & Contract Renewal',
        'date': 'Today, 08:45 AM',
        'body': 'Hi team,\nLooking forward to our 3 PM meeting today. We want to finalize the Milestone 2 deliverables and review the proposed contract renewal terms for Q4. Please ensure the performance benchmarks and pending deliverable schedule are ready.\n\nBest,\nSarah Jenkins\nVP Operations, Acrom Systems'
    },
    {
        'id': 'EML-002',
        'from': 'billing@apexsolutions.com',
        'to': 'accounts@workpilot.com',
        'subject': 'RE: Invoice INV-2024-001 Inquiry',
        'date': 'Yesterday, 04:15 PM',
        'body': 'Hello, we noticed Invoice INV-2024-001 has been flagged. Please send the detailed statement and copy of the invoice so we can expedite processing with our treasury department.'
    },
    {
        'id': 'EML-003',
        'from': 'admin@workpilot.com',
        'to': 'user@workpilot.com',
        'subject': 'Office Supplies Low Stock Notice',
        'date': 'Today, 09:10 AM',
        'body': 'Paper supplies (A4) and whiteboard markers are critically low in conference rooms A & B. Please place an order through the e-commerce supplier portal today.'
    },
    {
        'id': 'EML-004',
        'from': 'director@workpilot.com',
        'to': 'user@workpilot.com',
        'subject': 'End of Month Employee Performance Report Request',
        'date': 'Yesterday, 06:00 PM',
        'body': "Please compile this month's consolidated employee activity report covering completed tasks, client meetings, project milestones, and pending deliverables."
    }
]
with open('demo_data/emails.json', 'w', encoding='utf-8') as f:
    json.dump(emails_data, f, indent=2)

# 7. Project Documents in demo_data/documents/
with open('demo_data/documents/Acrom_Project_Deliverables_Q3.txt', 'w', encoding='utf-8') as f:
    f.write('''PROJECT BRIEF: Acrom Systems Cloud Portal (Q3)
Client: Acrom Systems
Key Contact: Sarah Jenkins, VP Operations
Scope of Work:
1. Microservices Architecture deployment on AWS ECS. (Status: 100% Completed)
2. Single Sign-On (SSO) integration with SAML 2.0. (Status: 95% Completed, awaiting final staging sign-off)
3. End-to-end load testing supporting 10,000 concurrent sessions. (Status: Passed with 142ms average response time)
Next Steps: Handover to client ops during 3 PM meeting today.
''')

with open('demo_data/documents/Acrom_Contract_Renewal_Terms.txt', 'w', encoding='utf-8') as f:
    f.write('''CONTRACT SUMMARY: Acrom Systems Q4 Retainer Renewal
Contract ID: AGR-2024-ACR-88
Term: 12 Months (Starting Oct 1, 2024)
Value: INR 3,60,000 per quarter
SLA: 99.9% uptime with 2-hour critical response guarantee
Special Clauses: Added 20 hours/month dedicated site reliability engineering advisory.
Status: Ready for client sign-off in today's 3 PM meeting.
''')

print('All demo data created successfully!')
