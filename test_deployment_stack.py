#!/usr/bin/env python3
"""
Comprehensive deployment stack testing script.
Tests Docker images, services, embedding system, and static file serving.
"""

import os
import sys
import time
import json
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Tuple, Optional

class DeploymentTester:
    """Test the complete deployment stack."""
    
    def __init__(self, env_file: str = ".env.test"):
        self.env_file = env_file
        self.test_results = {}
        self.services = ["db", "qdrant", "redis", "app", "nginx"]
        
    def run_command(self, command: List[str], timeout: int = 60) -> Tuple[bool, str]:
        """Run a command and return success status and output."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {timeout} seconds"
        except Exception as e:
            return False, str(e)
    
    def test_docker_build(self) -> bool:
        """Test Docker image building."""
        print("🔨 Testing Docker image build...")
        
        # Test multi-stage build
        success, output = self.run_command([
            "docker", "build", "--load", "-t", "faq-app:test", "."
        ], timeout=300)
        
        if success:
            print("✅ Docker image built successfully")
            self.test_results["docker_build"] = {"status": "pass", "details": "Image built"}
            
            # Test image size and layers
            success, output = self.run_command([
                "docker", "images", "faq-app:test", "--format", "table {{.Size}}"
            ])
            if success:
                print(f"📊 Image size: {output.strip()}")
            
            return True
        else:
            print(f"❌ Docker build failed: {output}")
            self.test_results["docker_build"] = {"status": "fail", "details": output}
            return False
    
    def test_docker_compose_services(self) -> bool:
        """Test Docker Compose service orchestration."""
        print("🚀 Testing Docker Compose services...")
        
        # Start services
        success, output = self.run_command([
            "docker-compose", "--env-file", self.env_file, "up", "-d"
        ], timeout=180)
        
        if not success:
            print(f"❌ Failed to start services: {output}")
            self.test_results["compose_start"] = {"status": "fail", "details": output}
            return False
        
        print("✅ Services started successfully")
        
        # Wait for services to be ready
        print("⏳ Waiting for services to be ready...")
        time.sleep(30)
        
        # Check service health
        all_healthy = True
        for service in self.services:
            healthy = self.check_service_health(service)
            if healthy:
                print(f"✅ {service} is healthy")
            else:
                print(f"❌ {service} is not healthy")
                all_healthy = False
        
        self.test_results["service_health"] = {
            "status": "pass" if all_healthy else "fail",
            "details": f"Services health check completed"
        }
        
        return all_healthy
    
    def check_service_health(self, service: str) -> bool:
        """Check if a specific service is healthy."""
        success, output = self.run_command([
            "docker-compose", "--env-file", self.env_file, "ps", service
        ])
        
        if success and "healthy" in output.lower():
            return True
        
        # For services without health checks, check if they're running
        if success and "up" in output.lower():
            return True
        
        return False
    
    def test_application_endpoints(self) -> bool:
        """Test application endpoints and responses."""
        print("🌐 Testing application endpoints...")
        
        base_url = "http://localhost:8000"
        endpoints = [
            ("/health/", "Health check endpoint"),
            ("/", "Home page"),
            ("/admin/", "Admin interface"),
        ]
        
        all_passed = True
        for endpoint, description in endpoints:
            try:
                response = requests.get(f"{base_url}{endpoint}", timeout=10)
                if response.status_code in [200, 302, 403]:  # 403 for admin without auth
                    print(f"✅ {description}: {response.status_code}")
                else:
                    print(f"❌ {description}: {response.status_code}")
                    all_passed = False
            except Exception as e:
                print(f"❌ {description}: {str(e)}")
                all_passed = False
        
        self.test_results["app_endpoints"] = {
            "status": "pass" if all_passed else "fail",
            "details": "Application endpoints tested"
        }
        
        return all_passed
    
    def test_embedding_system(self) -> bool:
        """Test embedding system functionality and fallbacks."""
        print("🧠 Testing embedding system...")
        
        try:
            # Test embedding health endpoint
            response = requests.get("http://localhost:8000/health/embedding/", timeout=10)
            if response.status_code == 200:
                print("✅ Embedding health endpoint accessible")
            else:
                print(f"⚠️ Embedding health endpoint returned: {response.status_code}")
            
            # Test RAG query endpoint
            test_query = {"query": "What is this system about?"}
            response = requests.post(
                "http://localhost:8000/api/rag/query/",
                json=test_query,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if "I don't know" not in result.get("answer", ""):
                    print("✅ RAG system providing meaningful responses")
                    embedding_works = True
                else:
                    print("⚠️ RAG system returning 'I don't know' - checking fallbacks")
                    embedding_works = False
            else:
                print(f"❌ RAG query failed: {response.status_code}")
                embedding_works = False
            
            # Test vector database connectivity
            try:
                response = requests.get("http://localhost:6333/health", timeout=10)
                if response.status_code == 200:
                    print("✅ Qdrant vector database is accessible")
                    vector_db_works = True
                else:
                    print(f"❌ Qdrant health check failed: {response.status_code}")
                    vector_db_works = False
            except Exception as e:
                print(f"❌ Qdrant connection failed: {str(e)}")
                vector_db_works = False
            
            self.test_results["embedding_system"] = {
                "status": "pass" if (embedding_works or vector_db_works) else "fail",
                "details": {
                    "embedding_responses": embedding_works,
                    "vector_db_connectivity": vector_db_works
                }
            }
            
            return embedding_works or vector_db_works
            
        except Exception as e:
            print(f"❌ Embedding system test failed: {str(e)}")
            self.test_results["embedding_system"] = {"status": "fail", "details": str(e)}
            return False
    
    def test_static_file_serving(self) -> bool:
        """Test static file serving through Nginx."""
        print("📁 Testing static file serving...")
        
        try:
            # Test static file through Nginx
            response = requests.get("http://localhost/static/faq/style.css", timeout=10)
            if response.status_code == 200:
                print("✅ Static files served through Nginx")
                nginx_static = True
            else:
                print(f"⚠️ Nginx static file serving: {response.status_code}")
                nginx_static = False
            
            # Test static file through Django (should be handled by WhiteNoise)
            response = requests.get("http://localhost:8000/static/faq/style.css", timeout=10)
            if response.status_code == 200:
                print("✅ Static files served through Django/WhiteNoise")
                django_static = True
            else:
                print(f"⚠️ Django static file serving: {response.status_code}")
                django_static = False
            
            self.test_results["static_files"] = {
                "status": "pass" if (nginx_static or django_static) else "fail",
                "details": {
                    "nginx_serving": nginx_static,
                    "django_serving": django_static
                }
            }
            
            return nginx_static or django_static
            
        except Exception as e:
            print(f"❌ Static file test failed: {str(e)}")
            self.test_results["static_files"] = {"status": "fail", "details": str(e)}
            return False
    
    def test_database_connectivity(self) -> bool:
        """Test database connectivity and migrations."""
        print("🗄️ Testing database connectivity...")
        
        try:
            # Check if migrations ran successfully
            success, output = self.run_command([
                "docker-compose", "--env-file", self.env_file, "exec", "-T", "app",
                "python", "manage.py", "showmigrations", "--plan"
            ])
            
            if success and "[X]" in output:
                print("✅ Database migrations applied successfully")
                migrations_ok = True
            else:
                print(f"❌ Database migrations issue: {output}")
                migrations_ok = False
            
            # Test database connection
            success, output = self.run_command([
                "docker-compose", "--env-file", self.env_file, "exec", "-T", "app",
                "python", "manage.py", "check", "--database", "default"
            ])
            
            if success:
                print("✅ Database connection successful")
                db_connection = True
            else:
                print(f"❌ Database connection failed: {output}")
                db_connection = False
            
            self.test_results["database"] = {
                "status": "pass" if (migrations_ok and db_connection) else "fail",
                "details": {
                    "migrations": migrations_ok,
                    "connection": db_connection
                }
            }
            
            return migrations_ok and db_connection
            
        except Exception as e:
            print(f"❌ Database test failed: {str(e)}")
            self.test_results["database"] = {"status": "fail", "details": str(e)}
            return False
    
    def cleanup(self):
        """Clean up test resources."""
        print("🧹 Cleaning up test resources...")
        
        # Stop and remove containers
        self.run_command([
            "docker-compose", "--env-file", self.env_file, "down", "-v"
        ])
        
        # Remove test image
        self.run_command(["docker", "rmi", "faq-app:test"])
        
        print("✅ Cleanup completed")
    
    def generate_report(self) -> Dict:
        """Generate a comprehensive test report."""
        passed_tests = sum(1 for result in self.test_results.values() 
                          if result["status"] == "pass")
        total_tests = len(self.test_results)
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": total_tests - passed_tests,
                "success_rate": f"{(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%"
            },
            "details": self.test_results,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return report
    
    def run_all_tests(self) -> bool:
        """Run all deployment tests."""
        print("🚀 Starting comprehensive deployment stack testing...")
        print("=" * 60)
        
        try:
            # Test sequence
            tests = [
                ("Docker Build", self.test_docker_build),
                ("Service Orchestration", self.test_docker_compose_services),
                ("Database Connectivity", self.test_database_connectivity),
                ("Application Endpoints", self.test_application_endpoints),
                ("Embedding System", self.test_embedding_system),
                ("Static File Serving", self.test_static_file_serving),
            ]
            
            all_passed = True
            for test_name, test_func in tests:
                print(f"\n📋 Running {test_name} test...")
                try:
                    result = test_func()
                    if not result:
                        all_passed = False
                except Exception as e:
                    print(f"❌ {test_name} test failed with exception: {str(e)}")
                    all_passed = False
                
                print("-" * 40)
            
            # Generate and display report
            report = self.generate_report()
            print(f"\n📊 Test Summary:")
            print(f"Total Tests: {report['summary']['total_tests']}")
            print(f"Passed: {report['summary']['passed']}")
            print(f"Failed: {report['summary']['failed']}")
            print(f"Success Rate: {report['summary']['success_rate']}")
            
            # Save detailed report
            with open("deployment_test_report.json", "w") as f:
                json.dump(report, f, indent=2)
            
            print(f"\n📄 Detailed report saved to: deployment_test_report.json")
            
            return all_passed
            
        except KeyboardInterrupt:
            print("\n⚠️ Testing interrupted by user")
            return False
        except Exception as e:
            print(f"\n❌ Testing failed with exception: {str(e)}")
            return False
        finally:
            # Always cleanup
            self.cleanup()


def main():
    """Main function to run deployment tests."""
    if len(sys.argv) > 1:
        env_file = sys.argv[1]
    else:
        env_file = ".env.test"
    
    print(f"Using environment file: {env_file}")
    
    if not os.path.exists(env_file):
        print(f"❌ Environment file {env_file} not found!")
        sys.exit(1)
    
    tester = DeploymentTester(env_file)
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All deployment tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some deployment tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()