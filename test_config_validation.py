#!/usr/bin/env python3
"""
Configuration validation tests for deployment stack.
Tests configuration files, environment variables, and settings without requiring Docker.
"""

import os
import sys
import yaml
import json
from pathlib import Path
from typing import Dict, List, Any

class ConfigValidator:
    """Validate deployment configuration files."""
    
    def __init__(self):
        self.test_results = {}
        self.errors = []
        self.warnings = []
    
    def test_dockerfile_syntax(self) -> bool:
        """Test Dockerfile syntax and best practices."""
        print("🐳 Testing Dockerfile configuration...")
        
        dockerfile_path = Path("Dockerfile")
        if not dockerfile_path.exists():
            self.errors.append("Dockerfile not found")
            return False
        
        content = dockerfile_path.read_text()
        
        # Check for multi-stage build
        if "FROM" in content and "as builder" in content and "as production" in content:
            print("✅ Multi-stage build detected")
        else:
            self.warnings.append("Multi-stage build not detected")
        
        # Check for non-root user
        if "USER django" in content or "USER " in content:
            print("✅ Non-root user configured")
        else:
            self.errors.append("Non-root user not configured")
        
        # Check for health check
        if "HEALTHCHECK" in content:
            print("✅ Health check configured")
        else:
            self.warnings.append("Health check not configured")
        
        # Check for security best practices
        if "PYTHONDONTWRITEBYTECODE=1" in content:
            print("✅ Python bytecode writing disabled")
        else:
            self.warnings.append("Python bytecode writing not disabled")
        
        self.test_results["dockerfile"] = {
            "status": "pass" if len(self.errors) == 0 else "fail",
            "errors": len(self.errors),
            "warnings": len(self.warnings)
        }
        
        return len(self.errors) == 0
    
    def test_docker_compose_config(self) -> bool:
        """Test Docker Compose configuration."""
        print("🔧 Testing Docker Compose configuration...")
        
        compose_path = Path("docker-compose.yml")
        if not compose_path.exists():
            self.errors.append("docker-compose.yml not found")
            return False
        
        try:
            with open(compose_path) as f:
                compose_config = yaml.safe_load(f)
            
            # Check required services
            required_services = ["db", "qdrant", "redis", "app", "nginx"]
            services = compose_config.get("services", {})
            
            for service in required_services:
                if service in services:
                    print(f"✅ Service '{service}' configured")
                else:
                    self.errors.append(f"Required service '{service}' not found")
            
            # Check volumes
            if "volumes" in compose_config:
                print("✅ Volumes configured for data persistence")
            else:
                self.warnings.append("No volumes configured")
            
            # Check networks
            if "networks" in compose_config:
                print("✅ Networks configured")
            else:
                self.warnings.append("No custom networks configured")
            
            # Check health checks
            health_check_services = 0
            for service_name, service_config in services.items():
                if "healthcheck" in service_config:
                    health_check_services += 1
            
            print(f"✅ {health_check_services}/{len(services)} services have health checks")
            
            self.test_results["docker_compose"] = {
                "status": "pass" if len(self.errors) == 0 else "fail",
                "services_found": len(services),
                "health_checks": health_check_services
            }
            
            return len(self.errors) == 0
            
        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML in docker-compose.yml: {str(e)}")
            return False
        except Exception as e:
            self.errors.append(f"Error reading docker-compose.yml: {str(e)}")
            return False
    
    def test_nginx_config(self) -> bool:
        """Test Nginx configuration."""
        print("🌐 Testing Nginx configuration...")
        
        nginx_conf = Path("nginx/nginx.conf")
        django_conf = Path("nginx/conf.d/django.conf")
        
        if not nginx_conf.exists():
            self.errors.append("nginx/nginx.conf not found")
            return False
        
        if not django_conf.exists():
            self.errors.append("nginx/conf.d/django.conf not found")
            return False
        
        # Check nginx.conf
        nginx_content = nginx_conf.read_text()
        if "worker_processes" in nginx_content:
            print("✅ Worker processes configured")
        else:
            self.warnings.append("Worker processes not explicitly configured")
        
        # Check django.conf
        django_content = django_conf.read_text()
        if "proxy_pass" in django_content:
            print("✅ Proxy pass configured")
        else:
            self.errors.append("Proxy pass not configured")
        
        if "location /static/" in django_content:
            print("✅ Static file serving configured")
        else:
            self.warnings.append("Static file serving not configured")
        
        self.test_results["nginx"] = {
            "status": "pass" if len(self.errors) == 0 else "fail",
            "config_files": 2
        }
        
        return len(self.errors) == 0
    
    def test_environment_config(self) -> bool:
        """Test environment configuration."""
        print("🔐 Testing environment configuration...")
        
        env_example = Path(".env.example")
        env_test = Path(".env.test")
        
        if not env_example.exists():
            self.errors.append(".env.example not found")
            return False
        
        if not env_test.exists():
            self.warnings.append(".env.test not found (created for testing)")
        
        # Check required environment variables
        required_vars = [
            "SECRET_KEY", "DJANGO_ENV", "DEBUG", "ALLOWED_HOSTS",
            "DB_NAME", "DB_USER", "DB_PASSWORD", "GEMINI_API_KEY",
            "QDRANT_HOST", "QDRANT_PORT", "REDIS_URL"
        ]
        
        env_content = env_example.read_text()
        missing_vars = []
        
        for var in required_vars:
            if var in env_content:
                print(f"✅ {var} documented")
            else:
                missing_vars.append(var)
        
        if missing_vars:
            self.warnings.append(f"Missing environment variables: {', '.join(missing_vars)}")
        
        self.test_results["environment"] = {
            "status": "pass" if len(missing_vars) == 0 else "warn",
            "documented_vars": len(required_vars) - len(missing_vars),
            "total_required": len(required_vars)
        }
        
        return len(missing_vars) == 0
    
    def test_django_settings(self) -> bool:
        """Test Django settings configuration."""
        print("⚙️ Testing Django settings...")
        
        settings_base = Path("faqbackend/settings/base.py")
        settings_prod = Path("faqbackend/settings/production.py")
        
        if not settings_base.exists():
            self.errors.append("faqbackend/settings/base.py not found")
        
        if not settings_prod.exists():
            self.errors.append("faqbackend/settings/production.py not found")
        
        if len(self.errors) > 0:
            return False
        
        # Check production settings
        prod_content = settings_prod.read_text()
        
        # Check database configuration
        if "postgresql" in prod_content.lower() or "psycopg" in prod_content.lower():
            print("✅ PostgreSQL database configured")
        else:
            self.warnings.append("PostgreSQL database not explicitly configured")
        
        # Check static files
        if "whitenoise" in prod_content.lower():
            print("✅ WhiteNoise static file serving configured")
        else:
            self.warnings.append("WhiteNoise not configured")
        
        # Check security settings
        security_settings = ["SECURE_SSL_REDIRECT", "SECURE_HSTS_SECONDS", "CSRF_TRUSTED_ORIGINS"]
        for setting in security_settings:
            if setting in prod_content:
                print(f"✅ {setting} configured")
            else:
                self.warnings.append(f"{setting} not configured")
        
        self.test_results["django_settings"] = {
            "status": "pass" if len(self.errors) == 0 else "fail",
            "files_found": 2
        }
        
        return len(self.errors) == 0
    
    def test_gunicorn_config(self) -> bool:
        """Test Gunicorn configuration."""
        print("🦄 Testing Gunicorn configuration...")
        
        gunicorn_conf = Path("gunicorn.conf.py")
        if not gunicorn_conf.exists():
            self.errors.append("gunicorn.conf.py not found")
            return False
        
        content = gunicorn_conf.read_text()
        
        # Check worker configuration
        if "workers" in content:
            print("✅ Worker count configured")
        else:
            self.warnings.append("Worker count not configured")
        
        # Check timeout settings
        if "timeout" in content:
            print("✅ Timeout configured")
        else:
            self.warnings.append("Timeout not configured")
        
        # Check preload
        if "preload_app" in content:
            print("✅ Application preloading configured")
        else:
            self.warnings.append("Application preloading not configured")
        
        self.test_results["gunicorn"] = {
            "status": "pass" if len(self.errors) == 0 else "fail",
            "config_found": True
        }
        
        return len(self.errors) == 0
    
    def test_entrypoint_script(self) -> bool:
        """Test Docker entrypoint script."""
        print("🚪 Testing entrypoint script...")
        
        entrypoint = Path("docker-entrypoint.sh")
        if not entrypoint.exists():
            self.errors.append("docker-entrypoint.sh not found")
            return False
        
        content = entrypoint.read_text()
        
        # Check migration execution
        if "migrate" in content:
            print("✅ Database migrations configured")
        else:
            self.warnings.append("Database migrations not in entrypoint")
        
        # Check static file collection
        if "collectstatic" in content:
            print("✅ Static file collection configured")
        else:
            self.warnings.append("Static file collection not in entrypoint")
        
        # Check executable permissions (on Unix systems)
        if os.name != 'nt':  # Not Windows
            if os.access(entrypoint, os.X_OK):
                print("✅ Entrypoint script is executable")
            else:
                self.warnings.append("Entrypoint script may not be executable")
        
        self.test_results["entrypoint"] = {
            "status": "pass" if len(self.errors) == 0 else "fail",
            "script_found": True
        }
        
        return len(self.errors) == 0
    
    def generate_report(self) -> Dict:
        """Generate configuration validation report."""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() 
                          if result["status"] == "pass")
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": total_tests - passed_tests,
                "errors": len(self.errors),
                "warnings": len(self.warnings)
            },
            "details": self.test_results,
            "errors": self.errors,
            "warnings": self.warnings
        }
    
    def run_all_tests(self) -> bool:
        """Run all configuration validation tests."""
        print("🔍 Starting configuration validation...")
        print("=" * 50)
        
        tests = [
            ("Dockerfile", self.test_dockerfile_syntax),
            ("Docker Compose", self.test_docker_compose_config),
            ("Nginx Configuration", self.test_nginx_config),
            ("Environment Variables", self.test_environment_config),
            ("Django Settings", self.test_django_settings),
            ("Gunicorn Configuration", self.test_gunicorn_config),
            ("Entrypoint Script", self.test_entrypoint_script),
        ]
        
        all_passed = True
        for test_name, test_func in tests:
            print(f"\n📋 Testing {test_name}...")
            try:
                result = test_func()
                if not result:
                    all_passed = False
            except Exception as e:
                print(f"❌ {test_name} test failed: {str(e)}")
                all_passed = False
            print("-" * 30)
        
        # Generate report
        report = self.generate_report()
        
        print(f"\n📊 Configuration Validation Summary:")
        print(f"Tests: {report['summary']['passed']}/{report['summary']['total_tests']} passed")
        print(f"Errors: {report['summary']['errors']}")
        print(f"Warnings: {report['summary']['warnings']}")
        
        if self.errors:
            print(f"\n❌ Errors found:")
            for error in self.errors:
                print(f"  - {error}")
        
        if self.warnings:
            print(f"\n⚠️ Warnings:")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        # Save report
        with open("config_validation_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Report saved to: config_validation_report.json")
        
        return all_passed and len(self.errors) == 0


def main():
    """Main function."""
    validator = ConfigValidator()
    success = validator.run_all_tests()
    
    if success:
        print("\n🎉 All configuration tests passed!")
        return 0
    else:
        print("\n❌ Configuration validation failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())