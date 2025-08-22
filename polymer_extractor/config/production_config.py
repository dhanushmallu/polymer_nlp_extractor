"""
polymer_extractor/config/production_config.py

Production configuration for multi-user polymer NLP extraction.

Purpose
-------
Provides production-ready configuration templates and environment management for:
- Multi-user session management with appropriate limits
- Resource allocation strategies for concurrent extraction workflows
- Storage isolation and quota management
- Performance monitoring and capacity planning

Configuration Profiles
----------------------
- development: Single-user, minimal resources, local storage
- staging: Multi-user testing, moderate resources, mixed storage
- production: Enterprise multi-user, scaled resources, redundant storage

Environment Management
---------------------
Validates and provides defaults for all multi-user configuration parameters
with production-ready values and comprehensive documentation.

Examples
--------
>>> from polymer_extractor.config.production_config import get_production_config
>>> config = get_production_config("production")
>>> print(f"Max sessions: {config['MAX_CONCURRENT_SESSIONS']}")
>>> print(f"Storage strategy: {config['STORAGE_STRATEGY']}")

Notes
-----
- Environment-specific configurations optimize for different deployment scenarios
- Validation ensures all required parameters are present and valid
- Documentation helps operations teams understand configuration impact
"""

import os
from typing import Dict, Any, Optional
from enum import Enum


class DeploymentEnvironment(Enum):
    """Deployment environment types with different configuration profiles."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ProductionConfig:
    """Production configuration manager for multi-user polymer NLP extraction."""
    
    @staticmethod
    def _get_env_value(key: str, default: Any, env_type: type = str) -> Any:
        """Get environment variable value with type conversion and default fallback."""
        env_value = os.getenv(key)
        if env_value is None:
            return default
        
        try:
            if env_type == bool:
                return env_value.lower() in ("true", "1", "yes", "on")
            elif env_type == int:
                return int(env_value)
            elif env_type == float:
                return float(env_value)
            else:
                return env_value
        except (ValueError, TypeError):
            return default
    
    # Configuration profiles for different environments
    # These now use .env values as defaults where available
    @classmethod
    def _build_environment_configs(cls) -> Dict[str, Dict[str, Any]]:
        """Build environment configurations using .env values as defaults."""
        
        # Base configuration from .env file
        base_config = {
            # Session Management - from .env or defaults
            "MAX_CONCURRENT_SESSIONS": cls._get_env_value("MAX_CONCURRENT_SESSIONS", 10, int),
            "SESSION_TIMEOUT_MINUTES": cls._get_env_value("SESSION_TIMEOUT_MINUTES", 60, int),
            "RESOURCE_SHARING_STRATEGY": cls._get_env_value("RESOURCE_SHARING_STRATEGY", "hybrid", str),
            "USER_STORAGE_ISOLATION": cls._get_env_value("USER_STORAGE_ISOLATION", True, bool),
            "SESSION_CLEANUP_INTERVAL": cls._get_env_value("SESSION_CLEANUP_INTERVAL", 15, int),
            
            # Storage Configuration - from .env
            "STORAGE_BACKEND": cls._get_env_value("STORAGE_BACKEND", "local", str),
            "STORAGE_BACKENDS_ACTIVE": cls._get_env_value("STORAGE_BACKENDS_ACTIVE", "local", str),
            "STORAGE_STRATEGY": cls._get_env_value("STORAGE_STRATEGY", "primary", str),
            "DEFAULT_STORAGE_QUOTA_GB": cls._get_env_value("DEFAULT_STORAGE_QUOTA_GB", 10.0, float),
            
            # Resource Limits - from .env or defaults
            "DEFAULT_MEMORY_LIMIT_GB": cls._get_env_value("DEFAULT_MEMORY_LIMIT_GB", 4.0, float),
            "DEFAULT_CPU_CORES": cls._get_env_value("MAX_WORKERS", 4, int),
            "ENABLE_GPU_ALLOCATION": cls._get_env_value("ENABLE_GPU_ALLOCATION", False, bool),
            
            # Monitoring - from .env or defaults
            "ENABLE_PERFORMANCE_MONITORING": cls._get_env_value("ENABLE_PERFORMANCE_MONITORING", True, bool),
            "METRICS_RETENTION_DAYS": cls._get_env_value("METRICS_RETENTION_DAYS", 30, int),
            "LOG_LEVEL": cls._get_env_value("LOG_LEVEL", "INFO", str)
        }
        
        return {
            "development": {
                **base_config,
                # Development-specific overrides
                "MAX_CONCURRENT_SESSIONS": min(base_config["MAX_CONCURRENT_SESSIONS"], 3),
                "MAX_CONCURRENT_SESSIONS_PER_USER": 2,
                "SESSION_TIMEOUT_MINUTES": min(base_config["SESSION_TIMEOUT_MINUTES"], 30),
                "RESOURCE_SHARING_STRATEGY": "shared",  # Simplest for development
                "USER_STORAGE_ISOLATION": False,  # Simpler for development
                "SESSION_CLEANUP_INTERVAL": 5,
                "DEFAULT_STORAGE_QUOTA_GB": min(base_config["DEFAULT_STORAGE_QUOTA_GB"], 5.0),
                "DEFAULT_MEMORY_LIMIT_GB": min(base_config["DEFAULT_MEMORY_LIMIT_GB"], 2.0),
                "DEFAULT_CPU_CORES": min(base_config["DEFAULT_CPU_CORES"], 1),
                "ENABLE_GPU_ALLOCATION": False,
                "METRICS_RETENTION_DAYS": 7,
                "LOG_LEVEL": "DEBUG" if cls._get_env_value("DEBUG", False, bool) else base_config["LOG_LEVEL"]
            },
            
            "staging": {
                **base_config,
                # Staging-specific overrides
                "MAX_CONCURRENT_SESSIONS": min(base_config["MAX_CONCURRENT_SESSIONS"], 10),
                "MAX_CONCURRENT_SESSIONS_PER_USER": 3,
                "SESSION_TIMEOUT_MINUTES": min(base_config["SESSION_TIMEOUT_MINUTES"], 60),
                "DEFAULT_STORAGE_QUOTA_GB": min(base_config["DEFAULT_STORAGE_QUOTA_GB"], 20.0),
                "DEFAULT_MEMORY_LIMIT_GB": min(base_config["DEFAULT_MEMORY_LIMIT_GB"], 4.0),
                "DEFAULT_CPU_CORES": min(base_config["DEFAULT_CPU_CORES"], 2),
                "ENABLE_GPU_ALLOCATION": False,  # Usually no GPU in staging
                "METRICS_RETENTION_DAYS": 30
            },
            
            "production": {
                **base_config,
                # Production uses .env values directly with higher limits
                "MAX_CONCURRENT_SESSIONS": max(base_config["MAX_CONCURRENT_SESSIONS"], 20),
                "MAX_CONCURRENT_SESSIONS_PER_USER": 5,
                "SESSION_TIMEOUT_MINUTES": max(base_config["SESSION_TIMEOUT_MINUTES"], 120),
                "USER_STORAGE_ISOLATION": True,  # Always enabled in production
                "DEFAULT_STORAGE_QUOTA_GB": max(base_config["DEFAULT_STORAGE_QUOTA_GB"], 50.0),
                "DEFAULT_MEMORY_LIMIT_GB": max(base_config["DEFAULT_MEMORY_LIMIT_GB"], 8.0),
                "METRICS_RETENTION_DAYS": max(base_config["METRICS_RETENTION_DAYS"], 90),
                "LOG_LEVEL": "INFO"  # Never DEBUG in production
            }
        }
    
    @classmethod
    def get_environment_configs(cls) -> Dict[str, Dict[str, Any]]:
        """Get the current environment configurations built from .env values."""
        return cls._build_environment_configs()
    
    # Legacy property for backward compatibility
    @property 
    def ENVIRONMENT_CONFIGS(self) -> Dict[str, Dict[str, Any]]:
        """Legacy property for backward compatibility."""
        return self.get_environment_configs()
    
    # Required environment variables for multi-user operation
    REQUIRED_ENV_VARS = {
        "database": [
            "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", 
            "POSTGRES_USER", "POSTGRES_PASSWORD"
        ],
        "storage": [
            "STORAGE_PATH"  # Always required, even for cloud storage
        ],
        "session_management": [
            "ENVIRONMENT"  # Determines which config profile to use
        ]
    }
    
    # Optional environment variables with defaults
    OPTIONAL_ENV_VARS = {
        # Session configuration
        "MAX_CONCURRENT_SESSIONS": {"type": int, "default": 10},
        "SESSION_TIMEOUT_MINUTES": {"type": int, "default": 60},
        "RESOURCE_SHARING_STRATEGY": {"type": str, "default": "hybrid"},
        "USER_STORAGE_ISOLATION": {"type": bool, "default": True},
        
        # Storage configuration
        "STORAGE_BACKENDS_ACTIVE": {"type": str, "default": "local"},
        "STORAGE_STRATEGY": {"type": str, "default": "primary"},
        "DEFAULT_STORAGE_QUOTA_GB": {"type": float, "default": 10.0},
        
        # User management
        "ENABLE_GUEST_ACCESS": {"type": bool, "default": False},
        "DEFAULT_USER_ROLE": {"type": str, "default": "researcher"},
        
        # Performance
        "ENABLE_PERFORMANCE_MONITORING": {"type": bool, "default": True},
        "METRICS_RETENTION_DAYS": {"type": int, "default": 30}
    }


def get_production_config(environment: Optional[str] = None) -> Dict[str, Any]:
    """
    Get production configuration for specified environment.
    
    Parameters
    ----------
    environment : str, optional
        Environment name (development, staging, production)
        If None, reads from ENVIRONMENT env var
    
    Returns
    -------
    dict
        Complete configuration with environment overrides from .env values
    
    Examples
    --------
    >>> config = get_production_config("production")
    >>> print(f"Max sessions: {config['MAX_CONCURRENT_SESSIONS']}")
    >>> # Will show value from .env or computed default
    """
    # Determine environment
    env = environment or os.getenv("ENVIRONMENT", "development")
    
    # Get current configurations built from .env values
    environment_configs = ProductionConfig.get_environment_configs()
    
    if env not in environment_configs:
        raise ValueError(f"Unknown environment: {env}. Must be one of: {list(environment_configs.keys())}")
    
    # Start with environment-specific defaults (already incorporating .env values)
    config = environment_configs[env].copy()
    
    # Override with any additional environment variables not already incorporated
    for var_name, var_config in ProductionConfig.OPTIONAL_ENV_VARS.items():
        env_value = os.getenv(var_name)
        if env_value is not None and var_name not in config:
            # Type conversion for variables not already processed
            if var_config["type"] == int:
                config[var_name] = int(env_value)
            elif var_config["type"] == float:
                config[var_name] = float(env_value)
            elif var_config["type"] == bool:
                config[var_name] = env_value.lower() in ("true", "1", "yes", "on")
            else:
                config[var_name] = env_value
    
    # Add environment metadata
    config["_meta"] = {
        "environment": env,
        "config_source": "production_config.py (using .env values)",
        "timestamp": os.getenv("CONFIG_TIMESTAMP", "unknown"),
        "env_based": True
    }
    
    return config


def validate_production_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate production configuration and return validation report.
    
    Parameters
    ----------
    config : dict
        Configuration to validate
    
    Returns
    -------
    dict
        Validation report with issues and recommendations
    """
    issues = []
    warnings = []
    recommendations = []
    
    # Check session limits
    max_sessions = config.get("MAX_CONCURRENT_SESSIONS", 0)
    max_per_user = config.get("MAX_CONCURRENT_SESSIONS_PER_USER", 0)
    
    if max_sessions <= 0:
        issues.append("MAX_CONCURRENT_SESSIONS must be positive")
    elif max_sessions > 100:
        warnings.append("Very high concurrent session limit may impact performance")
    
    if max_per_user <= 0:
        issues.append("MAX_CONCURRENT_SESSIONS_PER_USER must be positive")
    elif max_per_user >= max_sessions:
        warnings.append("Per-user limit should be less than global limit")
    
    # Check resource sharing strategy
    strategy = config.get("RESOURCE_SHARING_STRATEGY", "")
    valid_strategies = ["shared", "isolated", "hybrid"]
    if strategy not in valid_strategies:
        issues.append(f"Invalid RESOURCE_SHARING_STRATEGY: {strategy}. Must be one of: {valid_strategies}")
    
    # Check storage configuration
    storage_backends = config.get("STORAGE_BACKENDS_ACTIVE", "").split(",")
    storage_strategy = config.get("STORAGE_STRATEGY", "")
    
    if len(storage_backends) > 1 and storage_strategy == "primary":
        recommendations.append("Consider using 'failover' or 'sync' strategy with multiple storage backends")
    
    # Check storage quota
    quota = config.get("DEFAULT_STORAGE_QUOTA_GB", 0)
    if quota <= 0:
        issues.append("DEFAULT_STORAGE_QUOTA_GB must be positive")
    elif quota < 1.0:
        warnings.append("Very low storage quota may limit user productivity")
    
    # Check timeout configuration
    timeout = config.get("SESSION_TIMEOUT_MINUTES", 0)
    if timeout <= 0:
        issues.append("SESSION_TIMEOUT_MINUTES must be positive")
    elif timeout < 30:
        warnings.append("Short session timeout may cause frequent disconnections")
    elif timeout > 480:  # 8 hours
        warnings.append("Very long session timeout may waste resources")
    
    # Production-specific checks
    env = config.get("_meta", {}).get("environment", "unknown")
    if env == "production":
        if not config.get("USER_STORAGE_ISOLATION", False):
            warnings.append("Production should enable USER_STORAGE_ISOLATION for security")
        
        if config.get("LOG_LEVEL", "") == "DEBUG":
            warnings.append("Production should not use DEBUG log level")
        
        if max_sessions < 10:
            recommendations.append("Production deployment may need higher session limits")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "recommendations": recommendations,
        "summary": {
            "total_issues": len(issues),
            "total_warnings": len(warnings),
            "environment": env,
            "max_concurrent_sessions": max_sessions
        }
    }


def get_environment_recommendations(environment: str) -> Dict[str, Any]:
    """
    Get deployment recommendations for specific environment.
    
    Parameters
    ----------
    environment : str
        Environment name (development, staging, production)
    
    Returns
    -------
    dict
        Environment-specific recommendations and best practices
    """
    recommendations = {
        "development": {
            "description": "Single developer environment with minimal resources",
            "session_strategy": "Use 'shared' resource strategy for simplicity",
            "storage_strategy": "Local storage only for fast iteration",
            "monitoring": "Enable debug logging for development insights",
            "scaling": "Not applicable - single user focus",
            "security": "Disable user isolation for simpler development",
            "best_practices": [
                "Use shorter session timeouts for quick iteration",
                "Enable verbose logging for debugging",
                "Keep resource limits low to simulate constraints",
                "Use local storage for faster access"
            ]
        },
        
        "staging": {
            "description": "Pre-production testing with realistic multi-user simulation",
            "session_strategy": "Use 'hybrid' resource strategy to test sharing",
            "storage_strategy": "Test failover with local + cloud storage",
            "monitoring": "Enable performance monitoring for testing",
            "scaling": "Test with moderate concurrent load",
            "security": "Enable user isolation to test production behavior",
            "best_practices": [
                "Simulate production user patterns",
                "Test resource exhaustion scenarios",
                "Validate storage failover behavior",
                "Monitor session cleanup effectiveness"
            ]
        },
        
        "production": {
            "description": "Enterprise deployment with full multi-user capabilities",
            "session_strategy": "Use 'hybrid' for balanced efficiency and isolation",
            "storage_strategy": "Use 'sync' or 'failover' for redundancy",
            "monitoring": "Comprehensive monitoring and alerting required",
            "scaling": "Plan for peak concurrent usage patterns",
            "security": "Enable all isolation and security features",
            "best_practices": [
                "Set conservative resource limits initially",
                "Monitor quota utilization closely",
                "Implement automated cleanup policies",
                "Plan capacity based on user growth",
                "Enable comprehensive audit logging",
                "Regular backup and disaster recovery testing"
            ]
        }
    }
    
    return recommendations.get(environment, {
        "description": "Unknown environment",
        "best_practices": ["Define proper environment configuration"]
    })


# Example usage and configuration validation
if __name__ == "__main__":
    import json
    
    print("=== PRODUCTION CONFIG WITH .ENV INTEGRATION ===")
    print(f"Current .env values:")
    print(f"ENVIRONMENT: {os.getenv('ENVIRONMENT', 'not set')}")
    print(f"STORAGE_BACKEND: {os.getenv('STORAGE_BACKEND', 'not set')}")
    print(f"STORAGE_STRATEGY: {os.getenv('STORAGE_STRATEGY', 'not set')}")
    print(f"MAX_WORKERS: {os.getenv('MAX_WORKERS', 'not set')}")
    print()
    
    # Test different environment configurations
    for env in ["development", "staging", "production"]:
        print(f"\n=== {env.upper()} CONFIGURATION ===")
        
        config = get_production_config(env)
        validation = validate_production_config(config)
        recommendations = get_environment_recommendations(env)
        
        print(f"Max Concurrent Sessions: {config['MAX_CONCURRENT_SESSIONS']} (.env: {os.getenv('MAX_CONCURRENT_SESSIONS', 'not set')})")
        print(f"Resource Strategy: {config['RESOURCE_SHARING_STRATEGY']} (.env: {os.getenv('RESOURCE_SHARING_STRATEGY', 'not set')})")
        print(f"Storage Isolation: {config['USER_STORAGE_ISOLATION']}")
        print(f"Storage Strategy: {config['STORAGE_STRATEGY']} (.env: {os.getenv('STORAGE_STRATEGY', 'not set')})")
        print(f"Storage Backend: {config['STORAGE_BACKEND']} (.env: {os.getenv('STORAGE_BACKEND', 'not set')})")
        
        print(f"\nValidation: {'✓ VALID' if validation['valid'] else '✗ INVALID'}")
        if validation['issues']:
            print(f"Issues: {', '.join(validation['issues'])}")
        if validation['warnings']:
            print(f"Warnings: {', '.join(validation['warnings'])}")
        
        print(f"\nConfiguration Source: {config.get('_meta', {}).get('config_source', 'unknown')}")
        print(f"Environment-based: {config.get('_meta', {}).get('env_based', False)}")
    
    print("\n=== CUSTOM ENVIRONMENT OVERRIDE TEST ===")
    
    # Test environment variable override
    original_sessions = os.getenv("MAX_CONCURRENT_SESSIONS")
    original_strategy = os.getenv("RESOURCE_SHARING_STRATEGY")
    
    os.environ["MAX_CONCURRENT_SESSIONS"] = "25"
    os.environ["RESOURCE_SHARING_STRATEGY"] = "isolated"
    
    custom_config = get_production_config("production")
    print(f"Original .env Max Sessions: {original_sessions}")
    print(f"Overridden Max Sessions: {custom_config['MAX_CONCURRENT_SESSIONS']}")
    print(f"Original .env Strategy: {original_strategy}")
    print(f"Overridden Strategy: {custom_config['RESOURCE_SHARING_STRATEGY']}")
    
    # Restore original values
    if original_sessions:
        os.environ["MAX_CONCURRENT_SESSIONS"] = original_sessions
    else:
        os.environ.pop("MAX_CONCURRENT_SESSIONS", None)
    
    if original_strategy:
        os.environ["RESOURCE_SHARING_STRATEGY"] = original_strategy
    else:
        os.environ.pop("RESOURCE_SHARING_STRATEGY", None)
