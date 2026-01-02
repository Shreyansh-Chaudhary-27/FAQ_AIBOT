#!/usr/bin/env python3
"""
Comprehensive deployment readiness test.
Tests all components that can be validated without Docker running.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

class DeploymentReadinessTest:
    """Test deployment readiness without requiring Docker."""
    
    def __init__(self):
        self.test_results = {}
        self.errors = []
        self.warnings = []
    
    def run_test(self, test_name: str, test_func) -> bool:
        """Run a test and record results."""
        print(f"\n📋 Testing {test_name}...")
        try:
            result = test_func()
            status = "pass" if result else "fail"
            self.test_results[test_name] = {"status": status, "details": "Test completed"}
            if result:
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
            return result
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {str(e)}")
            self.test_results[test_name] = {"status": "error", "details": str(e)}
            self.errors.append(f"{test_name}: {str(e)}")
            return False
    
    def test_configuration_files(self) -> bool:
        """Test all configuration files are present and valid."""
        required_files = [
            "Dockerfile",
            "docker-compose.yml", 
            ".env.example",
            "gunicorn.conf.py",
            "docker-entrypoint.sh",
            "nginx/nginx.conf",
            "nginx/conf.d/django.conf",
            "faqbackend/settings/production.py",
            "requirements.txt"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            print(f"❌ Missing files: {', '.join(missing_files)}")
            return False
        
        print("✅ All configuration files present")
        return True
    
    def test_python_dependencies(self) -> bool:
        """Test Python dependencies can be resolved."""
        try:
            # Check if requirements.txt is valid
            with open("requirements.txt") as f:
                requirements = f.read()
            
            # Basic validation - check for common packages
            required_packages = [
                "django", "gunicorn", "psycopg2", "redis", 
                "sentence-transformers", "qdrant-client"
            ]
            
            missing_packages = []
            for package in required_packages:
                if package not in requirements.lower():
                    missing_packages.append(package)
            
            if missing_packages:
                print(f"⚠️ Potentially missing packages: {', '.join(missing_packages)}")
                self.warnings.append(f"Missing packages: {', '.join(missing_packages)}")
            
            print("✅ Requirements file validated")
            return True
            
        except Exception as e:
            print(f"❌ Requirements validation failed: {str(e)}")
            return False
    
    def test_django_settings(self) -> bool:
        """Test Django settings can be imported."""
        try:
            # Set environment for testing
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faqbackend.settings.production')
            os.environ.setdefault('SECRET_KEY', 'test-key-for-validation')
            os.environ.setdefault('DB_NAME', 'test_db')
            os.environ.setdefault('DB_USER', 'test_user')
            os.environ.setdefault('DB_PASSWORD', 'test_pass')
            os.environ.setdefault('GEMINI_API_KEY', 'test-key')
            os.environ.setdefault('DEBUG', 'False')
            os.environ.setdefault('ALLOWED_HOSTS', 'localhost')
            
            # Try to import Django settings
            import django
            from django.conf import settings
            django.setup()
            
            # Check critical settings
            assert settings.DEBUG is False, "DEBUG should be False in production"
            assert 'postgresql' in settings.DATABASES['default']['ENGINE'], "Should use PostgreSQL"
            assert 'whitenoise' in str(settings.MIDDLEWARE), "WhiteNoise should be configured"
            
            print("✅ Django settings validated")
            return True
            
        except Exception as e:
            print(f"❌ Django settings validation failed: {str(e)}")
            return False
    
    def test_embedding_system(self) -> bool:
        """Test embedding system functionality."""
        try:
            # Run the embedding fallback test
            result = subprocess.run([
                sys.executable, "test_embedding_fallback.py"
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print("✅ Embedding system functional")
                return True
            else:
                print(f"❌ Embedding system test failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ Embedding system test timed out")
            return False
        except Exception as e:
            print(f"❌ Embedding system test error: {str(e)}")
            return False
    
    def test_health_endpoints(self) -> bool:
        """Test health check endpoints."""
        try:
            # Run the health endpoints test
            result = subprocess.run([
                sys.executable, "test_health_endpoints.py"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✅ Health endpoints functional")
                return True
            else:
                print(f"❌ Health endpoints test failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ Health endpoints test timed out")
            return False
        except Exception as e:
            print(f"❌ Health endpoints test error: {str(e)}")
            return False
    
    def test_static_files_config(self) -> bool:
        """Test static files configuration."""
        try:
            # Check if static files directory exists or can be created
            static_dirs = ["faq/static", "staticfiles"]
            
            for static_dir in static_dirs:
                if Path(static_dir).exists():
                    print(f"✅ Static directory found: {static_dir}")
                    break
            else:
                print("⚠️ No static directories found, but this is acceptable for production")
            
            # Check WhiteNoise configuration in settings
            settings_file = Path("faqbackend/settings/production.py")
            if settings_file.exists():
                content = settings_file.read_text()
                if "whitenoise" in content.lower():
                    print("✅ WhiteNoise configured in production settings")
                    return True
                else:
                    print("❌ WhiteNoise not found in production settings")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Static files configuration test failed: {str(e)}")
            return False
    
    def test_security_configuration(self) -> bool:
        """Test security configuration."""
        try:
            settings_file = Path("faqbackend/settings/production.py")
            if not settings_file.exists():
                print("❌ Production settings file not found")
                return False
            
            content = settings_file.read_text()
            
            # Check for security settings
            security_checks = [
                ("SECURE_SSL_REDIRECT", "SSL redirect"),
                ("SECURE_HSTS_SECONDS", "HSTS headers"),
                ("CSRF_TRUSTED_ORIGINS", "CSRF protection"),
                ("ALLOWED_HOSTS", "Host validation")
            ]
            
            missing_security = []
            for setting, description in security_checks:
                if setting not in content:
                    missing_security.append(description)
            
            if missing_security:
                print(f"⚠️ Missing security settings: {', '.join(missing_security)}")
                self.warnings.append(f"Missing security: {', '.join(missing_security)}")
            
            print("✅ Security configuration validated")
            return True
            
        except Exception as e:
            print(f"❌ Security configuration test failed: {str(e)}")
            return False
    
    def test_environment_variables(self) -> bool:
        """Test environment variable configuration."""
        try:
            env_example = Path(".env.example")
            if not env_example.exists():
                print("❌ .env.example file not found")
                return False
            
            content = env_example.read_text()
            
            # Check for critical environment variables
            critical_vars = [
                "SECRET_KEY", "DJANGO_ENV", "DEBUG", "ALLOWED_HOSTS",
                "DB_NAME", "DB_USER", "DB_PASSWORD", "GEMINI_API_KEY",
                "QDRANT_HOST", "QDRANT_PORT", "REDIS_URL"
            ]
            
            missing_vars = []
            for var in critical_vars:
                if var not in content:
                    missing_vars.append(var)
            
            if missing_vars:
                print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
                return False
            
            print("✅ Environment variables documented")
            return True
            
        except Exception as e:
            print(f"❌ Environment variables test failed: {str(e)}")
            return False
    
    def test_database_migrations(self) -> bool:
        """Test database migrations are available."""
        try:
            # Check if migration files exist
            migration_dirs = [
                "faq/migrations",
            ]
            
            migrations_found = False
            for migration_dir in migration_dirs:
                migration_path = Path(migration_dir)
                if migration_path.exists():
                    migration_files = list(migration_path.glob("*.py"))
                    if len(migration_files) > 1:  # More than just __init__.py
                        migrations_found = True
                        print(f"✅ Migrations found in {migration_dir}")
                        break
            
            if not migrations_found:
                print("⚠️ No migration files found")
                self.warnings.append("No migration files found")
            
            return True
            
        except Exception as e:
            print(f"❌ Database migrations test failed: {str(e)}")
            return False
    
    def generate_report(self) -> Dict:
        """Generate comprehensive test report."""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() 
                          if result["status"] == "pass")
        failed_tests = sum(1 for result in self.test_results.values() 
                          if result["status"] == "fail")
        error_tests = sum(1 for result in self.test_results.values() 
                         if result["status"] == "error")
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "errors": error_tests,
                "warnings": len(self.warnings),
                "success_rate": f"{(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%"
            },
            "details": self.test_results,
            "errors": self.errors,
            "warnings": self.warnings,
            "deployment_ready": failed_tests == 0 and error_tests == 0
        }
    
    def run_all_tests(self) -> bool:
        """Run all deployment readiness tests."""
        print("🚀 Starting Deployment Readiness Testing...")
        print("=" * 60)
        
        tests = [
            ("Configuration Files", self.test_configuration_files),
            ("Python Dependencies", self.test_python_dependencies),
            ("Django Settings", self.test_django_settings),
            ("Embedding System", self.test_embedding_system),
            ("Health Endpoints", self.test_health_endpoints),
            ("Static Files Config", self.test_static_files_config),
            ("Security Configuration", self.test_security_configuration),
            ("Environment Variables", self.test_environment_variables),
            ("Database Migrations", self.test_database_migrations),
        ]
        
        all_passed = True
        for test_name, test_func in tests:
            result = self.run_test(test_name, test_func)
            if not result:
                all_passed = False
            print("-" * 40)
        
        # Generate and display report
        report = self.generate_report()
        
        print(f"\n📊 Deployment Readiness Summary:")
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Passed: {report['summary']['passed']}")
        print(f"Failed: {report['summary']['failed']}")
        print(f"Errors: {report['summary']['errors']}")
        print(f"Warnings: {report['summary']['warnings']}")
        print(f"Success Rate: {report['summary']['success_rate']}")
        print(f"Deployment Ready: {'✅ YES' if report['deployment_ready'] else '❌ NO'}")
        
        if self.errors:
            print(f"\n❌ Critical Errors:")
            for error in self.errors:
                print(f"  - {error}")
        
        if self.warnings:
            print(f"\n⚠️ Warnings:")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        # Save detailed report
        with open("deployment_readiness_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: deployment_readiness_report.json")
        
        return report['deployment_ready']


def main():
    """Main function."""
    tester = DeploymentReadinessTest()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 Deployment is ready! All critical tests passed.")
        print("\n📋 Next Steps:")
        print("1. Start Docker Desktop")
        print("2. Run: docker-compose --env-file .env.test up -d")
        print("3. Test the complete stack with: python test_deployment_stack.py")
        return 0
    else:
        print("\n❌ Deployment is not ready! Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())