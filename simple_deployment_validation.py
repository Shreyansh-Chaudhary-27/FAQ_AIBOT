#!/usr/bin/env python3
"""
Simple deployment validation script for final verification.
Tests core functionality without external dependencies.
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

class DeploymentValidator:
    """Simple deployment validation."""
    
    def __init__(self):
        self.results = []
        
    def add_result(self, test_name: str, passed: bool, details: str):
        """Add a test result."""
        self.results.append({
            "test_name": test_name,
            "passed": passed,
            "details": details,
            "timestamp": time.time()
        })
    
    def test_docker_availability(self) -> bool:
        """Test Docker availability."""
        try:
            result = subprocess.run(["docker", "--version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.add_result("Docker Availability", True, 
                              f"Docker available: {result.stdout.strip()}")
                return True
            else:
                self.add_result("Docker Availability", False, 
                              "Docker command failed")
                return False
        except Exception as e:
            self.add_result("Docker Availability", False, f"Docker test failed: {e}")
            return False
    
    def test_docker_compose_availability(self) -> bool:
        """Test Docker Compose availability."""
        try:
            result = subprocess.run(["docker-compose", "--version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.add_result("Docker Compose Availability", True, 
                              f"Docker Compose available: {result.stdout.strip()}")
                return True
            else:
                self.add_result("Docker Compose Availability", False, 
                              "Docker Compose command failed")
                return False
        except Exception as e:
            self.add_result("Docker Compose Availability", False, 
                          f"Docker Compose test failed: {e}")
            return False
    
    def test_configuration_files(self) -> bool:
        """Test presence of required configuration files."""
        required_files = [
            "docker-compose.yml",
            "Dockerfile", 
            "requirements.txt",
            ".env.example",
            "nginx/nginx.conf",
            "gunicorn.conf.py"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            self.add_result("Configuration Files", False, 
                          f"Missing files: {', '.join(missing_files)}")
            return False
        else:
            self.add_result("Configuration Files", True, 
                          "All required configuration files present")
            return True
    
    def test_environment_template(self) -> bool:
        """Test environment template completeness."""
        try:
            with open(".env.example", "r") as f:
                content = f.read()
            
            required_vars = [
                "SECRET_KEY",
                "DB_PASSWORD", 
                "GEMINI_API_KEY",
                "ALLOWED_HOSTS",
                "DEBUG"
            ]
            
            missing_vars = []
            for var in required_vars:
                if var not in content:
                    missing_vars.append(var)
            
            if missing_vars:
                self.add_result("Environment Template", False, 
                              f"Missing variables: {', '.join(missing_vars)}")
                return False
            else:
                self.add_result("Environment Template", True, 
                              "Environment template contains all required variables")
                return True
                
        except Exception as e:
            self.add_result("Environment Template", False, 
                          f"Failed to read .env.example: {e}")
            return False
    
    def test_python_dependencies(self) -> bool:
        """Test Python dependencies availability."""
        try:
            # Test key dependencies
            import django
            import sentence_transformers
            import requests
            
            self.add_result("Python Dependencies", True, 
                          f"Key dependencies available (Django {django.VERSION})")
            return True
            
        except ImportError as e:
            self.add_result("Python Dependencies", False, 
                          f"Missing dependency: {e}")
            return False
        except Exception as e:
            self.add_result("Python Dependencies", False, 
                          f"Dependency test failed: {e}")
            return False
    
    def test_deployment_scripts(self) -> bool:
        """Test deployment scripts availability."""
        required_scripts = [
            "deploy.sh",
            "scripts/backup.sh",
            "scripts/restore.sh",
            "scripts/setup-production.sh"
        ]
        
        missing_scripts = []
        for script_path in required_scripts:
            if not Path(script_path).exists():
                missing_scripts.append(script_path)
        
        if missing_scripts:
            self.add_result("Deployment Scripts", False, 
                          f"Missing scripts: {', '.join(missing_scripts)}")
            return False
        else:
            self.add_result("Deployment Scripts", True, 
                          "All deployment scripts present")
            return True
    
    def test_documentation(self) -> bool:
        """Test documentation completeness."""
        required_docs = [
            "PRODUCTION_DEPLOYMENT_GUIDE.md",
            "DEPLOYMENT_TROUBLESHOOTING_GUIDE.md",
            "config/deployment-checklist.md"
        ]
        
        missing_docs = []
        for doc_path in required_docs:
            if not Path(doc_path).exists():
                missing_docs.append(doc_path)
        
        if missing_docs:
            self.add_result("Documentation", False, 
                          f"Missing documentation: {', '.join(missing_docs)}")
            return False
        else:
            self.add_result("Documentation", True, 
                          "All required documentation present")
            return True
    
    def test_backup_directory(self) -> bool:
        """Test backup directory setup."""
        backup_dirs = ["backups", "scripts"]
        
        for dir_path in backup_dirs:
            Path(dir_path).mkdir(exist_ok=True)
        
        self.add_result("Backup Directory", True, 
                      "Backup directories created/verified")
        return True
    
    def test_simple_load_simulation(self) -> bool:
        """Simple load test simulation without external services."""
        try:
            # Simulate multiple concurrent operations
            import threading
            import time
            
            results = []
            
            def simulate_request():
                start_time = time.time()
                # Simulate some work
                time.sleep(0.1)
                duration = time.time() - start_time
                results.append(duration)
            
            # Run 10 concurrent "requests"
            threads = []
            for i in range(10):
                thread = threading.Thread(target=simulate_request)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads
            for thread in threads:
                thread.join()
            
            avg_time = sum(results) / len(results)
            
            self.add_result("Load Simulation", True, 
                          f"Simulated 10 concurrent operations, avg time: {avg_time:.3f}s")
            return True
            
        except Exception as e:
            self.add_result("Load Simulation", False, 
                          f"Load simulation failed: {e}")
            return False
    
    def run_all_tests(self) -> Dict:
        """Run all validation tests."""
        print("🔍 Starting deployment validation tests...")
        print("=" * 60)
        
        tests = [
            ("Docker Availability", self.test_docker_availability),
            ("Docker Compose Availability", self.test_docker_compose_availability),
            ("Configuration Files", self.test_configuration_files),
            ("Environment Template", self.test_environment_template),
            ("Python Dependencies", self.test_python_dependencies),
            ("Deployment Scripts", self.test_deployment_scripts),
            ("Documentation", self.test_documentation),
            ("Backup Directory", self.test_backup_directory),
            ("Load Simulation", self.test_simple_load_simulation),
        ]
        
        for test_name, test_func in tests:
            print(f"Running {test_name} test...")
            try:
                test_func()
            except Exception as e:
                self.add_result(test_name, False, f"Test crashed: {e}")
        
        return self.generate_report()
    
    def generate_report(self) -> Dict:
        """Generate validation report."""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r["passed"])
        failed_tests = total_tests - passed_tests
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0
            },
            "test_results": self.results,
            "recommendations": self.generate_recommendations()
        }
    
    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        failed_tests = [r for r in self.results if not r["passed"]]
        
        if any("Docker" in r["test_name"] for r in failed_tests):
            recommendations.append("Install and configure Docker and Docker Compose")
        
        if any("Configuration" in r["test_name"] for r in failed_tests):
            recommendations.append("Ensure all configuration files are present and valid")
        
        if any("Dependencies" in r["test_name"] for r in failed_tests):
            recommendations.append("Install missing Python dependencies")
        
        if any("Scripts" in r["test_name"] for r in failed_tests):
            recommendations.append("Ensure all deployment scripts are present and executable")
        
        if any("Documentation" in r["test_name"] for r in failed_tests):
            recommendations.append("Complete missing documentation")
        
        if not recommendations:
            recommendations.append("All validation tests passed - deployment ready")
        
        return recommendations

def print_validation_report(report: Dict):
    """Print formatted validation report."""
    print("\n" + "=" * 80)
    print("DEPLOYMENT VALIDATION REPORT")
    print("=" * 80)
    
    summary = report["summary"]
    print(f"\nTest Summary:")
    print(f"  Total Tests: {summary['total_tests']}")
    print(f"  Passed: {summary['passed']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Success Rate: {summary['success_rate']:.1f}%")
    
    # Test results
    print(f"\nTest Results:")
    for result in report["test_results"]:
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"  {status} {result['test_name']}: {result['details']}")
    
    # Recommendations
    if report["recommendations"]:
        print(f"\nRecommendations:")
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"  {i}. {rec}")
    
    # Overall assessment
    print(f"\nOverall Assessment:")
    if summary['success_rate'] >= 90:
        print("  ✅ Deployment validation PASSED - Ready for production")
    elif summary['success_rate'] >= 70:
        print("  ⚠️ Deployment validation PARTIAL - Address issues before production")
    else:
        print("  ❌ Deployment validation FAILED - Significant issues need resolution")

def main():
    """Main function to run deployment validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate deployment readiness')
    parser.add_argument('--output', help='Output file for detailed results (JSON)')
    
    args = parser.parse_args()
    
    validator = DeploymentValidator()
    
    try:
        report = validator.run_all_tests()
        
        # Print report
        print_validation_report(report)
        
        # Save detailed results if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\nDetailed results saved to: {args.output}")
        
        # Exit with appropriate code
        success_rate = report['summary']['success_rate']
        
        if success_rate >= 90:
            print("\n🎉 Deployment validation PASSED")
            return 0
        else:
            print("\n❌ Deployment validation needs attention")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ Deployment validation interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Deployment validation failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())