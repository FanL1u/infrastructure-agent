import os
import time
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
    max_retries = 20
    retry_interval = 5  # seconds
    
    for attempt in range(max_retries):
        try:
            response = requests.get(f"{NETBOX_URL}/api/", timeout=5)
            if response.status_code == 200:
                logger.info("NetBox API is available!")
                return True
        except requests.exceptions.RequestException:
            pass
        
        logger.info(f"Waiting for NetBox API to become available... (attempt {attempt+1}/{max_retries})")
        time.sleep(retry_interval)
    
    logger.error("NetBox API did not become available in the allotted time.")
    return False

def create_device_type():
    """Create a generic device type for our Linux hosts."""
    payload = {
        "manufacturer": {"name": "Generic"},
        "model": "Linux Host",
        "slug": "linux-host"
    }
    
    # First create manufacturer if it doesn't exist
    try:
        response = requests.post(
            f"{NETBOX_URL}/api/dcim/manufacturers/",
            headers=headers,
            json={"name": "Generic", "slug": "generic"}
        )
        if response.status_code == 201:
            logger.info("Created manufacturer: Generic")
    except Exception as e:
        logger.warning(f"Error creating manufacturer: {e}")
    
    # Then create device type
    try:
        response = requests.post(
            f"{NETBOX_URL}/api/dcim/device-types/",
            headers=headers,
            json=payload
        )
        if response.status_code == 201:
            logger.info("Created device type: Linux Host")
            return response.json()["id"]
    except Exception as e:
        logger.error(f"Error creating device type: {e}")
    
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
            json=payload
        )
        if response.status_code == 201:
            logger.info("Created site: Infrastructure Lab")
            return response.json()["id"]
    except Exception as e:
        logger.error(f"Error creating site: {e}")
    
    return None

def create_device(name, device_type_id, site_id, ip_address):
    """Create a device in NetBox."""
    device_payload = {
        "name": name,
        "device_type": device_type_id,
        "site": site_id,
        "status": "active"
    }
    
    try:
        # Create device
        response = requests.post(
            f"{NETBOX_URL}/api/dcim/devices/",
            headers=headers,
            json=device_payload
        )
        if response.status_code == 201:
            logger.info(f"Created device: {name}")
            device_id = response.json()["id"]
            
            # Create interface
            interface_payload = {
                "device": device_id,
                "name": "eth0",
                "type": "1000base-t"
            }
            interface_response = requests.post(
                f"{NETBOX_URL}/api/dcim/interfaces/",
                headers=headers,
                json=interface_payload
            )
            if interface_response.status_code == 201:
                logger.info(f"Created interface eth0 for device: {name}")
                
                # Add IP address
                ip_payload = {
                    "address": f"{ip_address}/24",
                    "assigned_object_type": "dcim.interface",
                    "assigned_object_id": interface_response.json()["id"]
                }
                ip_response = requests.post(
                    f"{NETBOX_URL}/api/ipam/ip-addresses/",
                    headers=headers,
                    json=ip_payload
                )
                if ip_response.status_code == 201:
                    logger.info(f"Assigned IP {ip_address} to {name}")
    except Exception as e:
        logger.error(f"Error creating device {name}: {e}")

def main():
    """Initialize NetBox with our devices."""
    if not wait_for_netbox():
        return
    
    device_type_id = create_device_type()
    site_id = create_site()
    
    if device_type_id and site_id:
        create_device("device1", device_type_id, site_id, "172.20.0.2")
        create_device("device2", device_type_id, site_id, "172.20.0.3")
        
        logger.info("NetBox initialization completed!")
    else:
        logger.error("Failed to initialize NetBox due to missing prerequisites.")

if __name__ == "__main__":
    main()