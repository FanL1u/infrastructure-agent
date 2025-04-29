#!/bin/bash

# Wait for devices to be available
echo "Waiting for devices to become available..."
for i in {1..30}; do
    if ping -c 1 device1 &> /dev/null && ping -c 1 device2 &> /dev/null; then
        echo "Devices are available!"
        break
    fi
    echo "Waiting for devices... ($i/30)"
    sleep 2
done

# Wait for NetBox API to be available
echo "Waiting for NetBox API to be available..."
for i in {1..60}; do  # Increased timeout
    if curl -sSf -k -H "Authorization: Token $NETBOX_TOKEN" -o /dev/null -w "%{http_code}" "http://netbox:8080/api/" > /dev/null 2>&1; then
        echo "NetBox API is available!"
        # Give NetBox a moment to fully initialize
        sleep 10
        break
    fi
    echo "Waiting for NetBox API... ($i/60)"
    sleep 5
done

# Initialize NetBox with our device data
echo "Initializing NetBox..."
python init_netbox.py

# Verify NetBox initialization
echo "Verifying NetBox initialization..."
DEVICE_COUNT=$(curl -s -k -H "Authorization: Token $NETBOX_TOKEN" "http://netbox:8080/api/dcim/devices/" | python -c "import json,sys; data=json.load(sys.stdin); print(data.get('count', 0))")
echo "Found $DEVICE_COUNT devices in NetBox"

# Start the Streamlit app
echo "Starting Infrastructure Agent UI with LangGraph..."
streamlit run main_agent.py