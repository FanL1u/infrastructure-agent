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

# Initialize NetBox with our device data
echo "Initializing NetBox..."
python init_netbox.py

# Start the Streamlit app
echo "Starting Infrastructure Agent UI..."
streamlit run main_agent.py