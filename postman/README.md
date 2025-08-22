# Postman Collections - Polymer NLP Extractor

## Overview

This directory contains four comprehensive Postman collections for testing and interacting with the Polymer NLP Extractor API ecosystem. All collections follow a standardized structure for consistency and ease of use.

## Collections

### 1. Polymer NLP Extractor - SETUP
**File**: `setup.postman_collection.json`
**Purpose**: System orchestration and lifecycle management

**Key Endpoints**:
- **Health Check**: Comprehensive system health validation
- **System Status**: Current configuration and component states  
- **Environment Info**: Configuration details and enabled services
- **Initialize System**: Safe and clean installation options
- **Reset Components**: Selective or complete data reset
- **Component Management**: Individual database, graph, storage initialization
- **Bulk Operations**: Complete setup and recovery workflows

**Use Cases**:
- Initial system setup and configuration
- Health monitoring and troubleshooting
- System recovery and maintenance
- Component-specific operations

### 2. Polymer NLP Extractor - MODELS
**File**: `models.postman_collection.json`
**Purpose**: GitHub-based models synchronization and management

**Key Endpoints**:
- **Models Status**: Current models directory and GitHub configuration status
- **Validate Models**: Version compatibility checking between models and tokenizers
- **Sync Models (Safe)**: Download missing models without overwriting existing
- **Sync Models (Force)**: Force redownload of all models for recovery
- **Bulk Operations**: Complete setup and recovery workflows

**Use Cases**:
- Initial models download and setup
- Model version validation and compatibility checking
- Model recovery and troubleshooting
- Regular model maintenance and updates

### 3. Polymer NLP Extractor - SESSION
**File**: `session.postman_collection.json`
**Purpose**: User session management and lifecycle operations for multi-user workflows

**Key Endpoints**:
- **Create User**: Register new users with quotas and permissions
- **Get User Info**: User information, quotas, and session statistics
- **Create Session**: Start new sessions with resource allocation
- **Get Session Details**: Session status, resources, and activity
- **List User Sessions**: View all sessions for a user with filtering
- **Get Session Health**: Comprehensive session monitoring
- **Terminate Session**: Clean session shutdown with optional data saving
- **System Status**: Overall session management system health

**Use Cases**:
- Multi-user environment management
- Session-aware document processing
- Resource allocation and monitoring
- User quota and permission management
- Session lifecycle administration

### 4. Polymer NLP Extractor - GROBID
**File**: `grobid.postman_collection.json`
**Purpose**: Session-aware document processing with GROBID

**Important**: GROBID endpoints require valid UUID format for `default_session_id` and `default_user_id`. The collection includes demo UUIDs, but for production use:

1. First create a user with the SESSION collection (Create User endpoint)
2. Then create a session with the SESSION collection (Create Session endpoint)
3. Use the returned session UUID values in the GROBID collection variables
4. For testing: Use the default UUIDs `550e8400-e29b-41d4-a716-446655440000` (session) and `6ba7b810-9dad-11d1-80b4-00c04fd430c8` (user)

**Key Endpoints**:
- **Server Status**: GROBID server availability check
- **Health Check**: Comprehensive service dependencies validation
- **Process Single Document**: Upload and process individual files
- **Process Multiple Documents**: Batch processing with parallel execution
- **Process Zip Archive**: Extract and process zip files containing documents
- **Process Local File**: Legacy endpoint for processing existing files
- **Download TEI XML**: Retrieve processed documents
- **List TEI Files**: View session processing history

**Use Cases**:
- Document processing and text extraction
- Batch processing of multiple files
- Session-aware file management
- TEI XML generation and retrieval

## Collection Standards

### Naming Convention
- Format: `Polymer NLP Extractor - [PURPOSE]`
- Examples: "GROBID", "SETUP", "MODELS"
- Clear, concise, single-word purposes

### Structure
- **Flat organization**: Direct endpoints under main collection
- **Minimal subfolders**: Only "Bulk Operations" for workflow sequences
- **One-level depth**: No nested subfolders beyond bulk operations

### Variables
All collections include standardized variables:
- `{{pnlp}}`: Base URL (default: `http://localhost:8000`)
- `{{default_user_id}}`: Default user UUID for testing (6ba7b810-9dad-11d1-80b4-00c04fd430c8)
- `{{default_session_id}}`: Default session UUID for testing (550e8400-e29b-41d4-a716-446655440000)

### Documentation
- **Detailed descriptions**: Every endpoint includes comprehensive documentation
- **Parameter explanations**: Clear descriptions of all parameters and their purposes
- **Use case guidance**: When and how to use each endpoint
- **Pre-filled values**: Realistic demo values for immediate testing

### Testing
- **Response validation**: Automatic status code and structure validation
- **Performance monitoring**: Response time limits appropriate for each operation type
- **Error reporting**: Clear logging of success/failure states
- **Pre-request scripts**: Automatic session ID generation for GROBID operations

## Usage Instructions

### Getting Started
1. **Import Collections**: Import all three JSON files into Postman
2. **Configure Base URL**: Ensure `{{pnlp}}` variable points to your API server
3. **System Setup**: Start with SETUP collection health check
4. **Models Setup**: Use MODELS collection to download required ML models
5. **Document Processing**: Use GROBID collection for document processing

### Recommended Workflows

#### Initial System Setup
1. SETUP → Health Check
2. SETUP → Initialize System (Safe)
3. SETUP → Create Standard Buckets
4. MODELS → Models Status
5. MODELS → Sync Models (Safe)
6. MODELS → Validate Models

#### Session Management Setup
1. SESSION → Create User
2. SESSION → Get User Info (verify user creation)
3. SESSION → Create Session
4. SESSION → Get Session Details (verify session creation)
5. Use session UUIDs in GROBID collection variables

#### Document Processing Workflow
1. GROBID → Health Check
2. GROBID → Server Status
3. GROBID → Process Single Document (or Multiple/Zip)
4. GROBID → List TEI Files
5. GROBID → Download TEI XML

#### Troubleshooting Workflow
1. SETUP → Health Check (identify issues)
2. SETUP → System Status (detailed diagnosis)
3. MODELS → Models Status (check model availability)
4. MODELS → Validate Models (verify model integrity)
5. Use appropriate recovery operations as needed

### Authentication
All collections use `"noauth"` as these are internal API endpoints. No authentication headers are required for local development environments.

### Error Handling
Each collection includes:
- Automatic response validation
- Clear error messages and troubleshooting guidance
- Detailed parameter descriptions to prevent common errors
- Performance monitoring to identify timeout issues

## Development Guidelines

When creating new endpoints or collections:

1. **Follow naming standards**: Use the established format and structure
2. **Include comprehensive documentation**: Document purpose, parameters, and use cases
3. **Pre-fill parameters**: Provide realistic demo values for immediate testing
4. **Add validation scripts**: Include response validation and performance monitoring
5. **Keep structure flat**: Avoid unnecessary nesting beyond bulk operations
6. **Update this documentation**: Add new collections or significant changes to this README

## File Structure
```
postman/
├── grobid.postman_collection.json     # Document processing endpoints
├── models.postman_collection.json     # Model synchronization endpoints  
├── session.postman_collection.json    # Session management endpoints
├── setup.postman_collection.json      # System management endpoints
└── README.md                          # This documentation file
```

This standardized approach ensures consistent, maintainable, and user-friendly API testing capabilities across the entire Polymer NLP Extractor ecosystem.
