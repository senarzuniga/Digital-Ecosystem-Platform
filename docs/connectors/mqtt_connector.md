# MQTT Connector Documentation

## Overview

The MQTT Connector allows the platform to communicate with devices using the MQTT protocol. This is essential for real-time data ingestion and device control.

## Setup Instructions

1. Ensure that the MQTT broker is running and accessible.
2. Configure the broker settings in the `.env` file:
   ```
   MQTT_BROKER_URL=<broker_url>
   MQTT_BROKER_PORT=<broker_port>
   MQTT_USERNAME=<username>
   MQTT_PASSWORD=<password>
   ```
3. Enable the MQTT connector by setting `MQTT_ENABLED=true` in the `.env` file.

## Configuration

- **Broker URL**: The address of the MQTT broker.
- **Broker Port**: The port on which the MQTT broker is listening.
- **Username/Password**: Credentials for authenticating with the broker.

## Usage

Once configured, the platform will automatically connect to the MQTT broker and start ingesting data from the specified topics.