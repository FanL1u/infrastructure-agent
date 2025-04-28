import os
import time
import yaml
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# NetBox API configuration
NETBOX_URL = os.getenv("NETBOX_BASE_URL").rstrip('/')
NETBOX_TOKEN = os.getenv("NETBOX_TOKEN")

headers = {
    'Authorization': f"Token {NETBOX_TOKEN}",
    'Content-Type': 'application/json',
    'Accept': 'application/json',
}

def wait_for_netbox():
    """Wait for NetBox to be available."""
    max_retries = 30
    retry_interval = 10  # seconds
    
    for attempt in range(max_retries):
        try:
            response = requests.get(
                f"{NETBOX_URL}/api/", 
                headers=headers,
                verify=False
            )
            if response.status_code == 200:
                logger.info("NetBox API is available!")
                return True
            logger.info(f"NetBox returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.info(f"Connection error: {e}")
        
        logger.info(f"Waiting for NetBox API... (attempt {attempt+1}/{max_retries})")
        time.sleep(retry_interval)
    
    logger.error("NetBox API did not become available in the allotted time.")
    return False

def create_manufacturer():
    """Create a generic manufacturer for our devices."""
    payload = {
        "name": "Generic",
        "slug": "generic"
    }
    
    try:
        response = requests.post(
            f"{NETBOX_URL}/api/dcim/manufacturers/",
            headers=headers,
            json=payload,
            verify=False
        )
        if response.status_code == 201:
            logger.info("Created manufacturer: Generic")
            return response.json()["id"]
        else:
            logger.warning(f"Failed to create manufacturer: {response.status_code}, {response.text}")
            # Try to get it if it already exists
            response = requests.get(
                f"{NETBOX_URL}/api/dcim/manufacturers/?name=Generic",
                headers=headers,
                verify=False
            )
            if response.status_code == 200 and response.json()["count"] > 0:
                logger.info("Manufacturer Generic already exists")
                return response.json()["results"][0]["id"]
    except Exception as e:
        logger.warning(f"Error with manufacturer: {e}")
    
    return None

def create_site():
    """Create a default site for our devices."""
    payload = {
        "name": "Infrastructure Lab",
        "slug": "infra-lab",
        "status": "active"
    }
    
    try:
        response = requests.post(
            f"{NETBOX_URL}/api/dcim/sites/",
            headers=headers,
            json=payload,
            verify=False
        )
        if response.status_code == 201:
            logger.info("Created site: Infrastructure Lab")
            return response.json()["id"]
        else:
            # Try to get it if it already exists
            response = requests.get(
                f"{NETBOX_URL}/api/dcim/sites/?name=Infrastructure Lab",
                headers=headers,
                verify=False
            )
            if response.status_code == 200 and response.json()["count"] > 0:
                logger.info("Site Infrastructure Lab already exists")
                return response.json()["results"][0]["id"]
    except Exception as e:
        logger.error(f"Error creating site: {e}")
    
    return None

def create_device_type(manufacturer_id, device_type_name):
    """Create a device type."""
    slug = device_type_name.lower().replace(" ", "-")
    payload = {
        "manufacturer": manufacturer_id,
        "model": device_type_name,
        "slug": slug
    }
    
    try:
        response = requests.post(
            f"{NETBOX_URL}/api/dcim/device-types/",
            headers=headers,
            json=payload,
            verify=False
        )
        if response.status_code == 201:
            logger.info(f"Created device type: {device_type_name}")
            return response.json()["id"]
        else:
            # Try to get it if it already exists
            response = requests.get(
                f"{NETBOX_URL}/api/dcim/device-types/?model={device_type_name}",
                headers=headers,
                verify=False
            )
            if response.status_code == 200 and response.json()["count"] > 0:
                logger.info(f"Device type {device_type_name} already exists")
                return response.json()["results"][0]["id"]
            logger.error(f"Failed to create device type: {response.status_code}, {response.text}")
    except Exception as e:
        logger.error(f"Error creating device type: {e}")
    
    return None


def create_device_role():
    """Create a default device role."""
    payload = {
        "name": "Server",
        "slug": "server",
        "color": "c0c0c0"
    }
    
    try:
        response = requests.post(
            f"{NETBOX_URL}/api/dcim/device-roles/",
            headers=headers,
            json=payload,
            verify=False
        )
        if response.status_code == 201:
            logger.info("Created device role: Server")
            return response.json()["id"]
        else:
            # Try to get it if it already exists
            response = requests.get(
                f"{NETBOX_URL}/api/dcim/device-roles/?name=Server",
                headers=headers,
                verify=False
            )
            if response.status_code == 200 and response.json()["count"] > 0:
                logger.info("Device role Server already exists")
                return response.json()["results"][0]["id"]
    except Exception as e:
        logger.warning(f"Error with device role: {e}")
    
    return None

def create_device(device_name, device_data, device_type_id, site_id, device_role_id):
    # Check if device already exists
    try:
        response = requests.get(
            f"{NETBOX_URL}/api/dcim/devices/?name={device_name}",
            headers=headers,
            verify=False
        )
        
        if response.status_code == 200 and response.json()["count"] > 0:
            logger.info(f"Device {device_name} already exists")
            return response.json()["results"][0]["id"]
    except Exception as e:
        logger.error(f"Error checking if device exists: {e}")

    # If not found, create the device
    device_payload = {
        "name": device_name,
        "device_type": device_type_id,
        "site": site_id,
        "status": "active",
        "role": device_role_id
    }
    
    try:
        response = requests.post(
            f"{NETBOX_URL}/api/dcim/devices/",
            headers=headers,
            json=device_payload,
            verify=False
        )
        
        if response.status_code == 201:
            logger.info(f"Created device: {device_name}")
            device_id = response.json()["id"]
            
            # Create management interface
            # [rest of your existing interface creation code]
            
            return device_id
        else:
            logger.error(f"Failed to create device: {response.status_code}, {response.text}")
    except Exception as e:
        logger.error(f"Error creating device {device_name}: {e}")
        
    return None



def main():
    """Initialize NetBox with data from testbed.yaml."""
    if not wait_for_netbox():
        logger.error("NetBox initialization failed: API not available")
        return
    
    try:
        # Load testbed.yaml
        with open('testbed.yaml', 'r') as file:
            testbed = yaml.safe_load(file)
        
        manufacturer_id = create_manufacturer()
        site_id = create_site()
        device_role_id = create_device_role()
        
        if not manufacturer_id or not site_id or not device_role_id:
            logger.error("Failed to create prerequisites")
            return
        
        # Process each device in testbed
        successful_devices = 0
        for device_name, device_data in testbed.get('devices', {}).items():
            device_type_name = device_data.get('type', 'Linux Host')
            device_type_id = create_device_type(manufacturer_id, device_type_name)
            
            if device_type_id:
                device_id = create_device(device_name, device_data, device_type_id, site_id, device_role_id)
                if device_id:
                    successful_devices += 1
        
        logger.info(f"NetBox initialization completed! {successful_devices} devices configured.")
        
    except Exception as e:
        logger.error(f"Error initializing NetBox: {e}")