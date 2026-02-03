"""
HTML-Based Component System for Guided Workflow Building
Each component uses HTML card templates with real-time preview
"""
import uuid
from typing import Dict, Any, List, Callable
from django import forms

# Base class for all HTML-based component templates
class HTMLComponentTemplate:
    """Base class for all HTML-based component templates"""
    def __init__(self, 
                 component_type: str,
                 label: str,
                 icon: str = "📝",
                 description: str = "",
                 fields: List[Dict] = None,
                 html_template: str = None,
                 generator: Callable = None):
        self.component_type = component_type
        self.label = label
        self.icon = icon
        self.description = description
        self.fields = fields or []
        self.html_template = html_template
        self.generator = generator

# Date/Time Picker Component
class DateTimePickerComponent(HTMLComponentTemplate):
    def __init__(self):
        super().__init__(
            component_type="datetime_picker",
            label="Date/Time Picker",
            icon="📅",
            description="Pick a date and time (e.g. for scheduling access)",
            fields=[
                {"name": "label", "type": "text", "label": "Label", "default": "Select Date & Time"},
                {"name": "required", "type": "checkbox", "label": "Required", "default": True}
            ]
        )
    def default_template(self, props):
        return f'''<div style="margin:10px 0;"><label>{props.get('label','Date & Time')}</label><input type="datetime-local" style="width:100%;padding:8px;margin-top:4px;"></div>'''

# Photo Capture Component
class PhotoCaptureComponent(HTMLComponentTemplate):
    def __init__(self):
        super().__init__(
            component_type="photo_capture",
            label="Photo Capture",
            icon="📸",
            description="Capture a visitor photo",
            fields=[
                {"name": "label", "type": "text", "label": "Label", "default": "Take Photo"},
                {"name": "required", "type": "checkbox", "label": "Required", "default": True}
            ]
        )
    def default_template(self, props):
        return f'''<div style="margin:10px 0;"><label>{props.get('label','Photo')}</label><button style="margin-left:10px;">📸 Capture</button></div>'''

# Signature Pad Component
class SignaturePadComponent(HTMLComponentTemplate):
    def __init__(self):
        super().__init__(
            component_type="signature_pad",
            label="Signature Pad",
            icon="✍️",
            description="Digital signature input",
            fields=[
                {"name": "label", "type": "text", "label": "Label", "default": "Signature"},
                {"name": "required", "type": "checkbox", "label": "Required", "default": True}
            ]
        )
    def default_template(self, props):
        return f'''<div style="margin:10px 0;"><label>{props.get('label','Signature')}</label><div style="border:1px dashed #bbb;min-height:60px;margin-top:4px;background:#f9fafb;">[Signature Pad]</div></div>'''

# Badge/QR Display Component
class BadgeQRDisplayComponent(HTMLComponentTemplate):
    def __init__(self):
        super().__init__(
            component_type="badge_qr_display",
            label="Badge/QR Display",
            icon="🔳",
            description="Show generated badge or QR code",
            fields=[
                {"name": "label", "type": "text", "label": "Label", "default": "Access Badge"},
                {"name": "qr_data", "type": "text", "label": "QR Data", "default": ""}
            ]
        )
    def default_template(self, props):
        return f'''<div style="margin:10px 0;"><label>{props.get('label','Badge')}</label><div style="margin-top:4px;">[QR: {props.get('qr_data','')}]</div></div>'''

# Gate/Zone Selector Component
class GateZoneSelectorComponent(HTMLComponentTemplate):
    def __init__(self):
        super().__init__(
            component_type="gate_zone_selector",
            label="Gate/Zone Selector",
            icon="🚪",
            description="Select entry/exit point",
            fields=[
                {"name": "label", "type": "text", "label": "Label", "default": "Select Gate/Zone"},
                {"name": "options", "type": "textarea", "label": "Options (one per line)", "default": "Main Gate\nSide Gate\nLoading Dock"}
            ]
        )
    def default_template(self, props):
        opts = [o.strip() for o in props.get('options','').split('\n') if o.strip()]
        opts_html = ''.join([f'<option>{o}</option>' for o in opts])
        return f'''<div style="margin:10px 0;"><label>{props.get('label','Gate/Zone')}</label><select style="width:100%;padding:8px;margin-top:4px;">{opts_html}</select></div>'''

# Access Reason Component
class AccessReasonComponent(HTMLComponentTemplate):
    def __init__(self):
        super().__init__(
            component_type="access_reason",
            label="Access Reason",
            icon="📝",
            description="Textarea for purpose of visit",
            fields=[
                {"name": "label", "type": "text", "label": "Label", "default": "Reason for Access"},
                {"name": "required", "type": "checkbox", "label": "Required", "default": True}
            ]
        )
    def default_template(self, props):
        return f'''<div style="margin:10px 0;"><label>{props.get('label','Reason')}</label><textarea style="width:100%;padding:8px;margin-top:4px;"></textarea></div>'''

# Host Selection Component
class HostSelectionComponent(HTMLComponentTemplate):
    def __init__(self):
        super().__init__(
            component_type="host_selection",
            label="Host Selection",
            icon="🧑‍💼",
            description="Dropdown for selecting host/employee",
            fields=[
                {"name": "label", "type": "text", "label": "Label", "default": "Select Host"},
                {"name": "options", "type": "textarea", "label": "Host Options (one per line)", "default": "John Doe\nJane Smith\nReception"}
            ]
        )
    def default_template(self, props):
        opts = [o.strip() for o in props.get('options','').split('\n') if o.strip()]
        opts_html = ''.join([f'<option>{o}</option>' for o in opts])
        return f'''<div style="margin:10px 0;"><label>{props.get('label','Host')}</label><select style="width:100%;padding:8px;margin-top:4px;">{opts_html}</select></div>'''

# Vehicle Type Selector Component
class VehicleTypeSelectorComponent(HTMLComponentTemplate):
    def __init__(self):
        super().__init__(
            component_type="vehicle_type_selector",
            label="Vehicle Type Selector",
            icon="🚙",
            description="Dropdown for vehicle type",
            fields=[
                {"name": "label", "type": "text", "label": "Label", "default": "Select Vehicle Type"},
                {"name": "options", "type": "textarea", "label": "Vehicle Types (one per line)", "default": "Car\nTruck\nMotorcycle\nBicycle"}
            ]
        )
    def default_template(self, props):
        opts = [o.strip() for o in props.get('options','').split('\n') if o.strip()]
        opts_html = ''.join([f'<option>{o}</option>' for o in opts])
        return f'''<div style="margin:10px 0;"><label>{props.get('label','Vehicle Type')}</label><select style="width:100%;padding:8px;margin-top:4px;">{opts_html}</select></div>'''

# Terms & Conditions Checkbox Component
class TermsCheckboxComponent(HTMLComponentTemplate):
    def __init__(self):
        super().__init__(
            component_type="terms_checkbox",
            label="Terms & Conditions",
            icon="✅",
            description="Checkbox for terms acceptance",
            fields=[
                {"name": "label", "type": "text", "label": "Label", "default": "I accept the terms and conditions"},
                {"name": "required", "type": "checkbox", "label": "Required", "default": True},
                {"name": "link", "type": "text", "label": "Terms Link", "default": "#"}
            ]
        )
    def default_template(self, props):
        return f'''<div style="margin:10px 0;"><label><input type="checkbox"> {props.get('label','I accept the terms')} <a href="{props.get('link','#')}" target="_blank">Read</a></label></div>'''

# Custom Info Display Component
class CustomInfoDisplayComponent(HTMLComponentTemplate):
    def __init__(self):
        super().__init__(
            component_type="custom_info_display",
            label="Custom Info Display",
            icon="ℹ️",
            description="Display custom instructions or warnings",
            fields=[
                {"name": "text", "type": "textarea", "label": "Display Text", "default": "Important instructions here."},
                {"name": "style", "type": "select", "label": "Style", "options": ["info","warning","danger"], "default": "info"}
            ]
        )
    def default_template(self, props):
        color = {'info':'#e0f2fe','warning':'#fef9c3','danger':'#fee2e2'}.get(props.get('style','info'),'#e0f2fe')
        return f'''<div style="margin:10px 0;padding:10px 14px;border-radius:8px;background:{color};">{props.get('text','Info')}</div>'''


### Registry of all available components (single instance, always at module level)
HTML_COMPONENT_REGISTRY: Dict[str, HTMLComponentTemplate] = {}

def register_html_component(template: HTMLComponentTemplate):
    """Register a component template"""
    HTML_COMPONENT_REGISTRY[template.component_type] = template
    return template

# Register access control components at module load
DATETIME_PICKER = register_html_component(DateTimePickerComponent())
PHOTO_CAPTURE = register_html_component(PhotoCaptureComponent())
SIGNATURE_PAD = register_html_component(SignaturePadComponent())
BADGE_QR_DISPLAY = register_html_component(BadgeQRDisplayComponent())
GATE_ZONE_SELECTOR = register_html_component(GateZoneSelectorComponent())
ACCESS_REASON = register_html_component(AccessReasonComponent())
HOST_SELECTION = register_html_component(HostSelectionComponent())
VEHICLE_TYPE_SELECTOR = register_html_component(VehicleTypeSelectorComponent())
TERMS_CHECKBOX = register_html_component(TermsCheckboxComponent())
CUSTOM_INFO_DISPLAY = register_html_component(CustomInfoDisplayComponent())


## Card component registrations moved to end of file

class HTMLComponentTemplate:
    """Base class for all HTML-based component templates"""
    
    def __init__(self, 
                 component_type: str,
                 label: str,
                 icon: str = "📝",
                 description: str = "",
                 fields: List[Dict] = None,
                 html_template: str = None,
                 generator: Callable = None):
        self.component_type = component_type
        self.label = label
        self.icon = icon
        self.description = description
        self.fields = fields or []
        self.html_template = html_template or self.default_template
        self.generator = generator or self.default_generator
    
    def default_template(self, props: Dict[str, Any]) -> str:
        """Default HTML template for the component"""
        return f"<div>Component: {self.component_type}</div>"
    
    def default_generator(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Default JSON generator"""
        return {
            "id": f"{self.component_type}_{uuid.uuid4().hex[:8]}",
            "type": self.component_type,
            "props": data,
            "html_preview": self.html_template(data)
        }
    
    def create_form(self, initial_data: Dict = None) -> forms.Form:
        """Create Django form for this component"""
        form_fields = {}
        for field_def in self.fields:
            field_name = field_def['name']
            
            if field_def['type'] == 'text':
                form_fields[field_name] = forms.CharField(
                    label=field_def['label'],
                    required=field_def.get('required', True),
                    max_length=field_def.get('max_length', 255),
                    initial=initial_data.get(field_name) if initial_data else field_def.get('default', '')
                )
            elif field_def['type'] == 'textarea':
                form_fields[field_name] = forms.CharField(
                    label=field_def['label'],
                    required=field_def.get('required', True),
                    widget=forms.Textarea(attrs={'rows': 3}),
                    initial=initial_data.get(field_name) if initial_data else field_def.get('default', '')
                )
            elif field_def['type'] == 'checkbox':
                form_fields[field_name] = forms.BooleanField(
                    label=field_def['label'],
                    required=False,
                    initial=initial_data.get(field_name) if initial_data else field_def.get('default', False)
                )
            elif field_def['type'] == 'select':
                form_fields[field_name] = forms.ChoiceField(
                    label=field_def['label'],
                    choices=[(opt, opt) for opt in field_def['options']],
                    initial=initial_data.get(field_name) if initial_data else field_def.get('default')
                )
            elif field_def['type'] == 'number':
                form_fields[field_name] = forms.IntegerField(
                    label=field_def['label'],
                    required=field_def.get('required', True),
                    min_value=field_def.get('min', 0),
                    max_value=field_def.get('max', 100),
                    initial=initial_data.get(field_name) if initial_data else field_def.get('default', 0)
                )
        
        # Create dynamic form class
        form_class = type(f'{self.component_type.capitalize()}Form', 
                         (forms.Form,), 
                         form_fields)
        return form_class(initial=initial_data) if initial_data else form_class()


# Registry of all available components
HTML_COMPONENT_REGISTRY: Dict[str, HTMLComponentTemplate] = {}

def register_html_component(template: HTMLComponentTemplate):
    """Register a component template"""
    HTML_COMPONENT_REGISTRY[template.component_type] = template
    return template

# ============================================================================
# HTML CARD COMPONENTS
# ============================================================================

class IDCardComponent(HTMLComponentTemplate):
    """
    Personal ID Card component following our HTML card design.
    
    Android Instructions:
    - Displays ID information in card format
    - Shows camera icon for photo capture
    - Layout: Left icon, middle info, right camera
    - Real-time preview in builder
    
    Props:
        id_number (str): ID/Passport number
        full_name (str): Full name to display
        gender (str): Gender information
        expiry_date (str): Expiry date for ID
        card_label (str): Label shown above card
    """
    def __init__(self):
        super().__init__(
            component_type="id_card",
            label="ID Card",
            icon="🪪",
            description="Personal identification card with camera icon",
            fields=[
                {
                    "name": "card_label",
                    "type": "text",
                    "label": "Card Label",
                    "required": True,
                    "default": "Personal Identification"
                },
                {
                    "name": "id_number",
                    "type": "text",
                    "label": "ID Number",
                    "required": True,
                    "default": "Enter ID number"
                },
                {
                    "name": "full_name",
                    "type": "text",
                    "label": "Full Name",
                    "required": True,
                    "default": "Enter full name"
                },
                {
                    "name": "gender",
                    "type": "select",
                    "label": "Gender",
                    "options": ["Male", "Female", "Other"],
                    "default": "Male"
                },
                {
                    "name": "expiry_date",
                    "type": "text",
                    "label": "Expiry Date",
                    "required": False,
                    "default": "DD/MM/YYYY"
                }
            ]
        )
    
    def default_template(self, props: Dict[str, Any]) -> str:
        """HTML template for ID Card component"""
        return f'''
        <div class="id-card" style="background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 20px; border: 1px solid #eef2f7; margin: 10px 0;">
            <div style="font-size: 0.9rem; color: #4b5563; font-weight: 600; margin-bottom: 10px;">{props.get('card_label', 'ID Information')}</div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div style="display: flex; align-items: center; flex: 1;">
                    <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #3a7bd5, #00d2ff); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.2rem; margin-right: 16px;">
                        <i class="fas fa-id-card"></i>
                    </div>
                    <div style="display: flex; flex-direction: column;">
                        <div style="font-size: 0.8rem; color: #6b7280; margin-bottom: 2px;">{props.get('id_number', 'ID: XXXXXXXX')}</div>
                        <div style="font-size: 1.1rem; color: #111827; font-weight: 600; margin-bottom: 4px;">{props.get('full_name', 'Full Name')}</div>
                        <div style="font-size: 0.85rem; color: #4f46e5; font-weight: 500;">{props.get('gender', 'Gender')}</div>
                    </div>
                </div>
                <div style="display: flex; flex-direction: column; align-items: flex-end;">
                    <div style="width: 40px; height: 40px; background: #f8fafc; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #4b5563; font-size: 1.1rem; border: 1px solid #e5e7eb; margin-bottom: 8px;">
                        <i class="fas fa-camera"></i>
                    </div>
                    <div style="font-size: 0.75rem; color: #dc2626; font-weight: 500;">{props.get('expiry_date', 'Expiry')}</div>
                </div>
            </div>
        </div>
        '''

class VehicleCardComponent(HTMLComponentTemplate):
    """
    Vehicle Information Card component.
    
    Android Instructions:
    - Displays vehicle information in card format
    - Shows camera icon for number plate scanning
    - Layout: Left vehicle icon, middle details, right camera
    
    Props:
        card_label (str): Card label/header
        number_plate (str): Vehicle registration number
        make_model (str): Vehicle make and model
        color (str): Vehicle color
        expiry_date (str): Registration expiry date
    """
    def __init__(self):
        super().__init__(
            component_type="vehicle_card",
            label="Vehicle Card",
            icon="🚗",
            description="Vehicle information card with camera icon",
            fields=[
                {
                    "name": "card_label",
                    "type": "text",
                    "label": "Card Label",
                    "required": True,
                    "default": "Vehicle Information"
                },
                {
                    "name": "number_plate",
                    "type": "text",
                    "label": "Number Plate",
                    "required": True,
                    "default": "Enter plate number"
                },
                {
                    "name": "make_model",
                    "type": "text",
                    "label": "Make & Model",
                    "required": True,
                    "default": "Enter make & model"
                },
                {
                    "name": "color",
                    "type": "text",
                    "label": "Color",
                    "required": False,
                    "default": "Enter color"
                },
                {
                    "name": "expiry_date",
                    "type": "text",
                    "label": "Expiry Date",
                    "required": False,
                    "default": "DD/MM/YYYY"
                }
            ]
        )
    
    def default_template(self, props: Dict[str, Any]) -> str:
        """HTML template for Vehicle Card component"""
        return f'''
        <div class="vehicle-card" style="background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 20px; border: 1px solid #eef2f7; margin: 10px 0;">
            <div style="font-size: 0.9rem; color: #4b5563; font-weight: 600; margin-bottom: 10px;">{props.get('card_label', 'Vehicle Information')}</div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div style="display: flex; align-items: center; flex: 1;">
                    <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #10b981, #059669); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.2rem; margin-right: 16px;">
                        <i class="fas fa-car"></i>
                    </div>
                    <div style="display: flex; flex-direction: column;">
                        <div style="font-size: 1rem; color: #111827; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 2px;">{props.get('number_plate', 'ABC-1234')}</div>
                        <div style="font-size: 0.9rem; color: #374151; font-weight: 600; margin-bottom: 1px;">{props.get('make_model', 'Make & Model')}</div>
                        <div style="font-size: 0.85rem; color: #6b7280; font-weight: 500; margin-bottom: 2px;">{props.get('color', 'Color')}</div>
                    </div>
                </div>
                <div style="display: flex; flex-direction: column; align-items: flex-end;">
                    <div style="width: 40px; height: 40px; background: #f8fafc; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #4b5563; font-size: 1.1rem; border: 1px solid #e5e7eb; margin-bottom: 8px;">
                        <i class="fas fa-camera"></i>
                    </div>
                    <div style="font-size: 0.75rem; color: #dc2626; font-weight: 500;">{props.get('expiry_date', 'Expiry')}</div>
                </div>
            </div>
        </div>
        '''

class PINCardComponent(HTMLComponentTemplate):
    """
    One-Time PIN Card component.
    
    Android Instructions:
    - PIN input field with call icon
    - Layout: Left PIN icon, middle input, right call button
    - Phone icon triggers PIN delivery
    
    Props:
        card_label (str): Card label/header
        placeholder (str): Input placeholder text
        call_label (str): Label for call button
        instructions (str): Instructions below input
    """
    def __init__(self):
        super().__init__(
            component_type="pin_card",
            label="PIN Card",
            icon="🔐",
            description="One-time PIN input with call button",
            fields=[
                {
                    "name": "card_label",
                    "type": "text",
                    "label": "Card Label",
                    "required": True,
                    "default": "PIN Verification"
                },
                {
                    "name": "placeholder",
                    "type": "text",
                    "label": "Input Placeholder",
                    "required": False,
                    "default": "Enter 6-digit PIN"
                },
                {
                    "name": "call_label",
                    "type": "text",
                    "label": "Call Button Label",
                    "required": False,
                    "default": "Call"
                },
                {
                    "name": "instructions",
                    "type": "textarea",
                    "label": "Instructions",
                    "required": False,
                    "default": "Enter 6-digit PIN received via SMS"
                }
            ]
        )
    
    def default_template(self, props: Dict[str, Any]) -> str:
        """HTML template for PIN Card component"""
        return f'''
        <div class="pin-card" style="background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 20px; border: 1px solid #eef2f7; margin: 10px 0;">
            <div style="font-size: 0.9rem; color: #4b5563; font-weight: 600; margin-bottom: 10px;">{props.get('card_label', 'PIN Verification')}</div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center; flex: 1;">
                    <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #8b5cf6, #7c3aed); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.2rem; margin-right: 16px;">
                        <i class="fas fa-key"></i>
                    </div>
                    <div style="display: flex; flex-direction: column; flex: 1;">
                        <div style="font-size: 0.75rem; color: #6b7280; font-weight: 500; margin-bottom: 4px;">ONE-TIME PIN</div>
                        <input type="text" style="width: 100%; padding: 10px 0; border: none; border-bottom: 1px solid #e5e7eb; font-size: 1.05rem; color: #111827; background-color: transparent;" placeholder="{props.get('placeholder', 'Enter 6-digit PIN')}">
                    </div>
                </div>
                <div style="display: flex; flex-direction: column; align-items: center; margin-left: 16px;">
                    <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #10b981, #059669); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.1rem; border: none; margin-bottom: 6px;">
                        <i class="fas fa-phone-alt"></i>
                    </div>
                    <div style="font-size: 0.7rem; color: #6b7280; font-weight: 500;">{props.get('call_label', 'Call')}</div>
                </div>
            </div>
            <div style="margin-top: 16px; font-size: 0.75rem; color: #6b7280; text-align: center; padding-top: 12px; border-top: 1px dashed #e5e7eb;">
                {props.get('instructions', 'Enter 6-digit PIN received via SMS')}
            </div>
        </div>
        '''

class NameInputCard(HTMLComponentTemplate):
    """
    Full Name Input Card component.
    
    Android Instructions:
    - Simple name input in card format
    - Left user icon, middle input field
    
    Props:
        card_label (str): Card label/header
        placeholder (str): Input placeholder
        icon_color (str): Icon gradient colors
    """
    def __init__(self):
        super().__init__(
            component_type="name_card",
            label="Name Card",
            icon="👤",
            description="Full name input card",
            fields=[
                {
                    "name": "card_label",
                    "type": "text",
                    "label": "Card Label",
                    "required": True,
                    "default": "Full Name"
                },
                {
                    "name": "placeholder",
                    "type": "text",
                    "label": "Placeholder",
                    "required": False,
                    "default": "Enter your full name"
                },
                {
                    "name": "icon_color",
                    "type": "select",
                    "label": "Icon Color",
                    "options": ["orange", "blue", "purple", "green"],
                    "default": "orange"
                }
            ]
        )
    
    def default_template(self, props: Dict[str, Any]) -> str:
        """HTML template for Name Input Card"""
        color_map = {
            "orange": "linear-gradient(135deg, #f59e0b, #d97706)",
            "blue": "linear-gradient(135deg, #3b82f6, #2563eb)",
            "purple": "linear-gradient(135deg, #8b5cf6, #7c3aed)",
            "green": "linear-gradient(135deg, #10b981, #059669)"
        }
        gradient = color_map.get(props.get('icon_color', 'orange'), color_map["orange"])
        
        return f'''
        <div class="name-card" style="background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 20px; border: 1px solid #eef2f7; margin: 10px 0;">
            <div style="font-size: 0.9rem; color: #4b5563; font-weight: 600; margin-bottom: 10px;">{props.get('card_label', 'Full Name')}</div>
            <div style="display: flex; align-items: center;">
                <div style="width: 40px; height: 40px; background: {gradient}; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.2rem; margin-right: 16px;">
                    <i class="fas fa-user"></i>
                </div>
                <div style="flex: 1;">
                    <input type="text" style="width: 100%; padding: 10px 0; border: none; border-bottom: 1px solid #e5e7eb; font-size: 1.05rem; color: #111827; background-color: transparent;" placeholder="{props.get('placeholder', 'Enter your full name')}">
                </div>
            </div>
        </div>
        '''

class PhoneInputCard(HTMLComponentTemplate):
    """
    Phone Number Input Card component.
    
    Android Instructions:
    - Phone number input in card format
    - Left phone icon, middle input field
    
    Props:
        card_label (str): Card label/header
        placeholder (str): Input placeholder
        phone_format (str): Format example shown
    """
    def __init__(self):
        super().__init__(
            component_type="phone_card",
            label="Phone Card",
            icon="📱",
            description="Phone number input card",
            fields=[
                {
                    "name": "card_label",
                    "type": "text",
                    "label": "Card Label",
                    "required": True,
                    "default": "Phone Number"
                },
                {
                    "name": "placeholder",
                    "type": "text",
                    "label": "Placeholder",
                    "required": False,
                    "default": "Enter phone number"
                },
                {
                    "name": "phone_format",
                    "type": "select",
                    "label": "Phone Format",
                    "options": ["International", "US", "UK", "EU"],
                    "default": "International"
                }
            ]
        )
    
    def default_template(self, props: Dict[str, Any]) -> str:
        """HTML template for Phone Input Card"""
        format_examples = {
            "International": "+1 (555) 000-0000",
            "US": "(555) 000-0000",
            "UK": "020 0000 0000",
            "EU": "+49 000 000000"
        }
        example = format_examples.get(props.get('phone_format', 'International'), "+1 (555) 000-0000")
        
        return f'''
        <div class="phone-card" style="background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 20px; border: 1px solid #eef2f7; margin: 10px 0;">
            <div style="font-size: 0.9rem; color: #4b5563; font-weight: 600; margin-bottom: 10px;">{props.get('card_label', 'Phone Number')}</div>
            <div style="display: flex; align-items: center;">
                <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #3b82f6, #2563eb); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.2rem; margin-right: 16px;">
                    <i class="fas fa-phone"></i>
                </div>
                <div style="flex: 1;">
                    <input type="tel" style="width: 100%; padding: 10px 0; border: none; border-bottom: 1px solid #e5e7eb; font-size: 1.05rem; color: #111827; background-color: transparent;" placeholder="{props.get('placeholder', example)}">
                    <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Format: {example}</div>
                </div>
            </div>
        </div>
        '''

class PassengersCard(HTMLComponentTemplate):
    """
    Passengers Count Card component.
    
    Android Instructions:
    - Counter for number of passengers
    - Left users icon, middle counter with +/- buttons
    
    Props:
        card_label (str): Card label/header
        min_value (int): Minimum passengers
        max_value (int): Maximum passengers
        default_value (int): Starting value
    """
    def __init__(self):
        super().__init__(
            component_type="passengers_card",
            label="Passengers Card",
            icon="👥",
            description="Passenger count card with counter",
            fields=[
                {
                    "name": "card_label",
                    "type": "text",
                    "label": "Card Label",
                    "required": True,
                    "default": "Number of Passengers"
                },
                {
                    "name": "min_value",
                    "type": "number",
                    "label": "Minimum Value",
                    "required": True,
                    "min": 1,
                    "max": 100,
                    "default": 1
                },
                {
                    "name": "max_value",
                    "type": "number",
                    "label": "Maximum Value",
                    "required": True,
                    "min": 1,
                    "max": 100,
                    "default": 20
                },
                {
                    "name": "default_value",
                    "type": "number",
                    "label": "Default Value",
                    "required": True,
                    "min": 1,
                    "max": 100,
                    "default": 1
                }
            ]
        )
    
    def default_template(self, props: Dict[str, Any]) -> str:
        """HTML template for Passengers Card"""
        min_val = props.get('min_value', 1)
        max_val = props.get('max_value', 20)
        default_val = props.get('default_value', 1)
        
        return f'''
        <div class="passengers-card" style="background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 20px; border: 1px solid #eef2f7; margin: 10px 0;">
            <div style="font-size: 0.9rem; color: #4b5563; font-weight: 600; margin-bottom: 10px;">{props.get('card_label', 'Passengers')}</div>
            <div style="display: flex; align-items: center;">
                <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #8b5cf6, #7c3aed); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.2rem; margin-right: 16px;">
                    <i class="fas fa-users"></i>
                </div>
                <div style="flex: 1;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <div style="width: 36px; height: 36px; background: #f9fafb; border-radius: 8px; border: 1px solid #d1d5db; color: #6b7280; font-size: 1.2rem; display: flex; align-items: center; justify-content: center;">-</div>
                        <div style="font-size: 1.2rem; font-weight: 600; color: #111827; min-width: 30px; text-align: center;">{default_val}</div>
                        <div style="width: 36px; height: 36px; background: #f9fafb; border-radius: 8px; border: 1px solid #d1d5db; color: #6b7280; font-size: 1.2rem; display: flex; align-items: center; justify-content: center;">+</div>
                    </div>
                    <div style="font-size: 0.75rem; color: #6b7280; margin-top: 8px;">Range: {min_val} - {max_val} passengers</div>
                </div>
            </div>
        </div>
        '''

class CompanyCard(HTMLComponentTemplate):
    """
    Company Selection Card component.
    
    Android Instructions:
    - Dropdown for company selection
    - Left building icon, middle dropdown
    
    Props:
        card_label (str): Card label/header
        options (str): Newline-separated company options
        allow_custom (bool): Allow custom company entry
    """
    def __init__(self):
        super().__init__(
            component_type="company_card",
            label="Company Card",
            icon="🏢",
            description="Company selection card with dropdown",
            fields=[
                {
                    "name": "card_label",
                    "type": "text",
                    "label": "Card Label",
                    "required": True,
                    "default": "Company Selection"
                },
                {
                    "name": "options",
                    "type": "textarea",
                    "label": "Company Options (one per line)",
                    "required": True,
                    "default": "Global Transport Inc.\nLogistics Solutions Ltd.\nSwift Delivery Corp."
                },
                {
                    "name": "allow_custom",
                    "type": "checkbox",
                    "label": "Allow Custom Company",
                    "default": True
                }
            ]
        )
    
    def default_template(self, props: Dict[str, Any]) -> str:
        """HTML template for Company Card"""
        options = props.get('options', '').split('\n')
        options = [opt.strip() for opt in options if opt.strip()]
        if not options:
            options = ["Select company", "Option 1", "Option 2"]
        
        options_html = ''.join([f'<option value="{opt}">{opt}</option>' for opt in options])
        
        return f'''
        <div class="company-card" style="background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 20px; border: 1px solid #eef2f7; margin: 10px 0;">
            <div style="font-size: 0.9rem; color: #4b5563; font-weight: 600; margin-bottom: 10px;">{props.get('card_label', 'Company')}</div>
            <div style="display: flex; align-items: center;">
                <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #10b981, #059669); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.2rem; margin-right: 16px;">
                    <i class="fas fa-building"></i>
                </div>
                <div style="flex: 1; position: relative;">
                    <select style="width: 100%; padding: 10px 0; border: none; border-bottom: 1px solid #e5e7eb; font-size: 1.05rem; color: #111827; background-color: transparent; appearance: none; padding-right: 25px;">
                        {options_html}
                    </select>
                    <div style="position: absolute; right: 0; top: 50%; transform: translateY(-50%); pointer-events: none;">
                        <i class="fas fa-chevron-down" style="color: #6b7280;"></i>
                    </div>
                    {"<div style='font-size: 0.75rem; color: #6b7280; margin-top: 4px;'>Custom entry allowed</div>" if props.get('allow_custom', True) else ""}
                </div>
            </div>
        </div>
        '''

class TrailerCard(HTMLComponentTemplate):
    """
    Trailer Details Card component.
    
    Android Instructions:
    - Trailer information input card
    - Left trailer icon, multiple input fields
    
    Props:
        card_label (str): Card label/header
        plate_placeholder (str): Plate number placeholder
        model_placeholder (str): Make/model placeholder
        expiry_placeholder (str): Expiry date placeholder
    """
    def __init__(self):
        super().__init__(
            component_type="trailer_card",
            label="Trailer Card",
            icon="🚚",
            description="Trailer details card with multiple fields",
            fields=[
                {
                    "name": "card_label",
                    "type": "text",
                    "label": "Card Label",
                    "required": True,
                    "default": "Trailer Details"
                },
                {
                    "name": "plate_placeholder",
                    "type": "text",
                    "label": "Plate Placeholder",
                    "required": False,
                    "default": "Trailer number plate"
                },
                {
                    "name": "model_placeholder",
                    "type": "text",
                    "label": "Make/Model Placeholder",
                    "required": False,
                    "default": "Make & model"
                },
                {
                    "name": "expiry_placeholder",
                    "type": "text",
                    "label": "Expiry Placeholder",
                    "required": False,
                    "default": "Registration expiry"
                }
            ]
        )
    
    def default_template(self, props: Dict[str, Any]) -> str:
        """HTML template for Trailer Card"""
        return f'''
        <div class="trailer-card" style="background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 20px; border: 1px solid #eef2f7; margin: 10px 0;">
            <div style="font-size: 0.9rem; color: #4b5563; font-weight: 600; margin-bottom: 10px;">{props.get('card_label', 'Trailer')}</div>
            <div style="display: flex; align-items: flex-start;">
                <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #ef4444, #dc2626); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.2rem; margin-right: 16px; margin-top: 8px;">
                    <i class="fas fa-trailer"></i>
                </div>
                <div style="flex: 1;">
                    <input type="text" style="width: 100%; padding: 10px 0; border: none; border-bottom: 1px solid #e5e7eb; font-size: 1.05rem; color: #111827; background-color: transparent; margin-bottom: 12px;" placeholder="{props.get('plate_placeholder', 'Trailer number plate')}">
                    <input type="text" style="width: 100%; padding: 10px 0; border: none; border-bottom: 1px solid #e5e7eb; font-size: 1.05rem; color: #111827; background-color: transparent;" placeholder="{props.get('model_placeholder', 'Make & model')}">
                    <div style="font-size: 0.75rem; color: #6b7280; margin-top: 8px; padding-left: 4px;">{props.get('expiry_placeholder', 'Registration expiry date')}</div>
                </div>
            </div>
        </div>
        '''

class ResidenceCard(HTMLComponentTemplate):
    """
    Residence Type Card component.
    
    Android Instructions:
    - Residence type dropdown card
    - Left home icon, middle dropdown
    
    Props:
        card_label (str): Card label/header
        options (str): Newline-separated residence options
        allow_custom (bool): Allow custom residence type
    """
    def __init__(self):
        super().__init__(
            component_type="residence_card",
            label="Residence Card",
            icon="🏠",
            description="Residence type selection card",
            fields=[
                {
                    "name": "card_label",
                    "type": "text",
                    "label": "Card Label",
                    "required": True,
                    "default": "Residence Type"
                },
                {
                    "name": "options",
                    "type": "textarea",
                    "label": "Residence Options (one per line)",
                    "required": True,
                    "default": "Apartment / Condo\nSingle Family House\nTownhouse\nDuplex\nVilla"
                },
                {
                    "name": "allow_custom",
                    "type": "checkbox",
                    "label": "Allow Custom Residence",
                    "default": False
                }
            ]
        )
    
    def default_template(self, props: Dict[str, Any]) -> str:
        """HTML template for Residence Card"""
        options = props.get('options', '').split('\n')
        options = [opt.strip() for opt in options if opt.strip()]
        if not options:
            options = ["Select residence", "Apartment", "House"]
        
        options_html = ''.join([f'<option value="{opt}">{opt}</option>' for opt in options])
        
        return f'''
        <div class="residence-card" style="background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 20px; border: 1px solid #eef2f7; margin: 10px 0;">
            <div style="font-size: 0.9rem; color: #4b5563; font-weight: 600; margin-bottom: 10px;">{props.get('card_label', 'Residence')}</div>
            <div style="display: flex; align-items: center;">
                <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #8b5cf6, #7c3aed); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.2rem; margin-right: 16px;">
                    <i class="fas fa-home"></i>
                </div>
                <div style="flex: 1; position: relative;">
                    <select style="width: 100%; padding: 10px 0; border: none; border-bottom: 1px solid #e5e7eb; font-size: 1.05rem; color: #111827; background-color: transparent; appearance: none; padding-right: 25px;">
                        {options_html}
                    </select>
                    <div style="position: absolute; right: 0; top: 50%; transform: translateY(-50%); pointer-events: none;">
                        <i class="fas fa-chevron-down" style="color: #6b7280;"></i>
                    </div>
                    {"<div style='font-size: 0.75rem; color: #6b7280; margin-top: 4px;'>Custom type allowed</div>" if props.get('allow_custom', False) else ""}
                </div>
            </div>
        </div>
        '''

class ButtonCard(HTMLComponentTemplate):
    """
    Action Button Card component.
    
    Android Instructions:
    - Action button in card format
    - Various styles and actions
    
    Props:
        button_text (str): Button label
        action_type (str): Button action
        button_style (str): Visual style
        destination (str): Destination step ID
    """
    def __init__(self):
        super().__init__(
            component_type="button_card",
            label="Button Card",
            icon="🔘",
            description="Action button card",
            fields=[
                {
                    "name": "button_text",
                    "type": "text",
                    "label": "Button Text",
                    "required": True,
                    "default": "Continue"
                },
                {
                    "name": "action_type",
                    "type": "select",
                    "label": "Action Type",
                    "options": ["next", "submit", "back", "cancel", "custom"],
                    "default": "next"
                },
                {
                    "name": "button_style",
                    "type": "select",
                    "label": "Button Style",
                    "options": ["primary", "secondary", "outline", "danger"],
                    "default": "primary"
                },
                {
                    "name": "destination",
                    "type": "text",
                    "label": "Destination Step ID",
                    "required": False,
                    "default": ""
                }
            ]
        )
    
    def default_template(self, props: Dict[str, Any]) -> str:
        """HTML template for Button Card"""
        style_map = {
            "primary": "background: linear-gradient(135deg, #3b82f6, #2563eb); color: white;",
            "secondary": "background: white; color: #4b5563; border: 1px solid #d1d5db;",
            "outline": "background: transparent; color: #3b82f6; border: 1px solid #3b82f6;",
            "danger": "background: linear-gradient(135deg, #ef4444, #dc2626); color: white;"
        }
        button_style = style_map.get(props.get('button_style', 'primary'), style_map['primary'])
        action_text = f"Action: {props.get('action_type', 'next')}"
        if props.get('destination'):
            action_text += f" → {props.get('destination')}"
        
        return f'''
        <div class="button-card" style="background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 20px; border: 1px solid #eef2f7; margin: 10px 0;">
            <div style="display: flex; justify-content: center;">
                <button style="{button_style} padding: 14px 32px; border: none; border-radius: 10px; font-weight: 600; font-size: 1rem; cursor: pointer; display: flex; align-items: center; gap: 8px; min-width: 200px; justify-content: center;">
                    <i class="fas fa-arrow-right"></i>
                    {props.get('button_text', 'Continue')}
                </button>
            </div>
            <div style="font-size: 0.75rem; color: #6b7280; text-align: center; margin-top: 8px;">
                {action_text}
            </div>
        </div>
        '''

class TextDisplayCard(HTMLComponentTemplate):
    """
    Text Display Card component.
    
    Android Instructions:
    - Text display in card format
    - Various alignments and sizes
    
    Props:
        text_content (str): Text to display
        alignment (str): Text alignment
        text_size (str): Text size category
        show_border (bool): Show card border
    """
    def __init__(self):
        super().__init__(
            component_type="text_card",
            label="Text Card",
            icon="📝",
            description="Text display card",
            fields=[
                {
                    "name": "text_content",
                    "type": "textarea",
                    "label": "Text Content",
                    "required": True,
                    "default": "Enter your text here"
                },
                {
                    "name": "alignment",
                    "type": "select",
                    "label": "Text Alignment",
                    "options": ["left", "center", "right"],
                    "default": "left"
                },
                {
                    "name": "text_size",
                    "type": "select",
                    "label": "Text Size",
                    "options": ["small", "medium", "large", "title"],
                    "default": "medium"
                },
                {
                    "name": "show_border",
                    "type": "checkbox",
                    "label": "Show Card Border",
                    "default": True
                }
            ]
        )
    
    def default_template(self, props: Dict[str, Any]) -> str:
        """HTML template for Text Display Card"""
        size_map = {
            "small": "0.9rem",
            "medium": "1rem",
            "large": "1.2rem",
            "title": "1.4rem"
        }
        font_size = size_map.get(props.get('text_size', 'medium'), "1rem")
        alignment = props.get('alignment', 'left')
        border_style = "border: 1px solid #eef2f7;" if props.get('show_border', True) else ""
        
        return f'''
        <div class="text-card" style="background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); padding: 20px; {border_style} margin: 10px 0;">
            <div style="font-size: {font_size}; color: #111827; text-align: {alignment}; line-height: 1.5; white-space: pre-line;">
                {props.get('text_content', 'Text content')}
            </div>
        </div>
        '''

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_html_component_template(component_type: str) -> HTMLComponentTemplate:
    """
    Retrieve a component template by its type name.
    """
    return HTML_COMPONENT_REGISTRY.get(component_type)

def get_all_html_component_templates() -> List[Dict]:
    """
    Get all available HTML component templates for the builder UI.
    """
    return [
        {
            "type": template.component_type,
            "label": template.label,
            "icon": template.icon,
            "description": template.description,
            "fields": template.fields,
            "html_preview": template.default_template({field['name']: field.get('default', '') for field in template.fields})
        }
        for template in HTML_COMPONENT_REGISTRY.values()
    ]

def generate_workflow_preview(components: List[Dict]) -> str:
    """
    Generate HTML preview for a workflow screen.
    
    Args:
        components: List of component configurations
        
    Returns:
        HTML string for preview
    """
    preview_html = '<div style="max-width: 420px; margin: 0 auto; background: #f5f7fa; padding: 20px; border-radius: 12px;">'
    
    for component in components:
        comp_type = component.get('type')
        template = get_html_component_template(comp_type)
        if template:
            preview_html += template.default_template(component.get('props', {}))
    
    preview_html += '</div>'
    return preview_html

# ============================================================================
# EXAMPLE WORKFLOWS USING HTML COMPONENTS
# ============================================================================

HTML_EXAMPLE_WORKFLOWS = {
    "vehicle_registration": {
        "name": "Vehicle Registration",
        "description": "Complete vehicle registration with all cards",
        "steps": ["registration"],
        "screens": {
            "registration": {
                "title": "Vehicle Registration",
                "components": [
                    {
                        "id": "text_header",
                        "type": "text_card",
                        "props": {
                            "text_content": "Vehicle Registration\nComplete all sections below",
                            "alignment": "center",
                            "text_size": "large",
                            "show_border": True
                        }
                    },
                    {
                        "id": "id_card_component",
                        "type": "id_card",
                        "props": {
                            "card_label": "Driver Identification",
                            "id_number": "Enter ID number",
                            "full_name": "Enter full name",
                            "gender": "Male",
                            "expiry_date": "DD/MM/YYYY"
                        }
                    },
                    {
                        "id": "vehicle_card_component",
                        "type": "vehicle_card",
                        "props": {
                            "card_label": "Vehicle Information",
                            "number_plate": "Enter plate number",
                            "make_model": "Enter make & model",
                            "color": "Enter color",
                            "expiry_date": "DD/MM/YYYY"
                        }
                    },
                    {
                        "id": "name_card_component",
                        "type": "name_card",
                        "props": {
                            "card_label": "Full Name",
                            "placeholder": "Enter your full name",
                            "icon_color": "orange"
                        }
                    },
                    {
                        "id": "phone_card_component",
                        "type": "phone_card",
                        "props": {
                            "card_label": "Phone Number",
                            "placeholder": "Enter phone number",
                            "phone_format": "International"
                        }
                    },
                    {
                        "id": "passengers_card_component",
                        "type": "passengers_card",
                        "props": {
                            "card_label": "Number of Passengers",
                            "min_value": 1,
                            "max_value": 20,
                            "default_value": 1
                        }
                    },
                    {
                        "id": "company_card_component",
                        "type": "company_card",
                        "props": {
                            "card_label": "Company Selection",
                            "options": "Global Transport Inc.\nLogistics Solutions Ltd.\nSwift Delivery Corp.",
                            "allow_custom": True
                        }
                    },
                    {
                        "id": "trailer_card_component",
                        "type": "trailer_card",
                        "props": {
                            "card_label": "Trailer Details",
                            "plate_placeholder": "Trailer number plate",
                            "model_placeholder": "Make & model",
                            "expiry_placeholder": "Registration expiry"
                        }
                    },
                    {
                        "id": "residence_card_component",
                        "type": "residence_card",
                        "props": {
                            "card_label": "Residence Type",
                            "options": "Apartment / Condo\nSingle Family House\nTownhouse\nDuplex\nVilla",
                            "allow_custom": False
                        }
                    },
                    {
                        "id": "pin_card_component",
                        "type": "pin_card",
                        "props": {
                            "card_label": "PIN Verification",
                            "placeholder": "Enter 6-digit PIN",
                            "call_label": "Call",
                            "instructions": "Enter 6-digit PIN received via SMS"
                        }
                    },
                    {
                        "id": "submit_button",
                        "type": "button_card",
                        "props": {
                            "button_text": "Submit Registration",
                            "action_type": "submit",
                            "button_style": "primary"
                        }
                    }
                ]
            }
        }
    },
    
    "quick_checkin": {
        "name": "Quick Check-in",
        "description": "Simple check-in with essential information",
        "steps": ["checkin"],
        "screens": {
            "checkin": {
                "title": "Visitor Check-in",
                "components": [
                    {
                        "id": "welcome_text",
                        "type": "text_card",
                        "props": {
                            "text_content": "Welcome!\nPlease check in below",
                            "alignment": "center",
                            "text_size": "large",
                            "show_border": False
                        }
                    },
                    {
                        "id": "name_input",
                        "type": "name_card",
                        "props": {
                            "card_label": "Your Name",
                            "placeholder": "Enter your name",
                            "icon_color": "blue"
                        }
                    },
                    {
                        "id": "company_select",
                        "type": "company_card",
                        "props": {
                            "card_label": "Company",
                            "options": "ACME Corp\nTech Solutions\nGlobal Industries",
                            "allow_custom": True
                        }
                    },
                    {
                        "id": "checkin_button",
                        "type": "button_card",
                        "props": {
                            "button_text": "Check In",
                            "action_type": "submit",
                            "button_style": "primary"
                        }
                    }
                ]
            }
        }
    }
}

# Register component instances at module load
ID_CARD = register_html_component(IDCardComponent())
VEHICLE_CARD = register_html_component(VehicleCardComponent())
PIN_CARD = register_html_component(PINCardComponent())
NAME_CARD = register_html_component(NameInputCard())
PHONE_CARD = register_html_component(PhoneInputCard())
PASSENGERS_CARD = register_html_component(PassengersCard())
COMPANY_CARD = register_html_component(CompanyCard())
TRAILER_CARD = register_html_component(TrailerCard())
RESIDENCE_CARD = register_html_component(ResidenceCard())
BUTTON_CARD = register_html_component(ButtonCard())
TEXT_CARD = register_html_component(TextDisplayCard())