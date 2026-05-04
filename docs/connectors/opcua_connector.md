# OPC UA Connector Documentation

## Overview

The OPC UA Connector enables the platform to interface with industrial devices using the OPC UA protocol, which is widely used in industrial automation.

## Setup Instructions

1. Ensure that the OPC UA server is running and accessible.
2. Configure the server settings in the `.env` file:
   ```
   OPCUA_SERVER_URL=<server_url>
   OPCUA_SECURITY_MODE=<security_mode>
   OPCUA_SECURITY_POLICY=<security_policy>
   ```
3. Enable the OPC UA connector by setting `OPCUA_ENABLED=true` in the `.env` file.

## Configuration

- **Server URL**: The address of the OPC UA server.
- **Security Mode**: The security mode to use (e.g., `None`, `Sign`, `SignAndEncrypt`).
- **Security Policy**: The security policy to use (e.g., `Basic256Sha256`).

## Usage

Once configured, the platform will connect to the OPC UA server and start interacting with the available nodes.