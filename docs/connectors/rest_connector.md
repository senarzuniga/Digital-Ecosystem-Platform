# REST Connector Documentation

## Overview

The REST Connector allows the platform to interact with external systems using RESTful APIs. This is useful for integrating with web services and other HTTP-based systems.

## Setup Instructions

1. Ensure that the external REST API is accessible.
2. Configure the API settings in the `.env` file:
   ```
   REST_API_URL=<api_url>
   REST_API_KEY=<api_key>
   ```
3. Enable the REST connector by setting `REST_ENABLED=true` in the `.env` file.

## Configuration

- **API URL**: The base URL of the REST API.
- **API Key**: The key used for authenticating with the API.

## Usage

Once configured, the platform will use the REST connector to send and receive data from the specified API endpoints.