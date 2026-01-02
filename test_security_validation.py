#!/usr/bin/env python3
"""
Security validation script for Django FAQ/RAG application.
Tests security configurations and validates production security settings.
"""

import os
import sys
import json
import requests
import subprocess
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from urllib.parse import urljoin

@dataclass
class SecurityTestResult:
    """Result of a security test."""
    test_name: str
    passed: bool
    details: str
    severity: str = "medium"  # low, medium, high, critical
    recommendation: Optional[str] = None

class SecurityValidator:
    """Security validation framework for the FAQ/RAG application."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[SecurityTestResult] = []
        
    def add_result(self, test_name: str, passed: bool, details: str, 
                   severity: str = "medium", recommendation: str = None):
        """Add a test result."""
        self.results.append(SecurityTestResult(
            test_name=test_name,
            passed=passed,
            details=details,
            severity=severity,
            recommendation=recommendation
        ))
    
    def test_debug_mode_disabled(self) -> bool:
        """Test that DEBUG mode is disabled in production."""
        try:
            # Try to trigger a 404 error to see if debug info is exposed
            response = requests.get(f"{self.base_url}/nonexistent-page-12345/", timeout=10)
            
            # Check if debug information is exposed
            debug_indicators = [
                "DEBUG = True",
                "Django Debug",
                "Traceback",
                "INSTALLED_APPS",
                "django.core.exceptions",
                "Request information"
            ]
            
            response_text = response.text.lower()
            debug_exposed = any(indicator.lower() in response_text for indicator in debug_indicators)
            
            if debug_exposed:
                self.add_result(
                    "Debug Mode Check",
                    False,
                    "Debug information is exposed in error pages",
                    "critical",
                    "Set DEBUG = False in production settings"
                )
                return False
            else:
                self.add_result(
                    "Debug Mode Check",
                    True,
                    "Debug mode is properly disabled",
                    "low"
                )
                return True
                
        except Exception as e:
            self.add_result(
                "Debug Mode Check",
                False,
                f"Failed to test debug mode: {e}",
                "medium",
                "Ensure application is accessible for testing"
            )
            return False
    
    def test_security_headers(self) -> bool:
        """Test for proper security headers."""
        try:
            response = requests.get(self.base_url, timeout=10)
            headers = response.headers
            
            # Required security headers
            security_headers = {
                'X-Content-Type-Options': 'nosniff',
                'X-Frame-Options': ['DENY', 'SAMEORIGIN'],
                'X-XSS-Protection': '1; mode=block',
                'Strict-Transport-Security': None,  # Should exist for HTTPS
                'Content-Security-Policy': None,    # Should exist
            }
            
            missing_headers = []
            weak_headers = []
            
            for header, expected_values in security_headers.items():
                if header not in headers:
                    missing_headers.append(header)
                elif expected_values and isinstance(expected_values, list):
                    if headers[header] not in expected_values:
                        weak_headers.append(f"{header}: {headers[header]}")
            
            if missing_headers or weak_headers:
                details = []
                if missing_headers:
                    details.append(f"Missing headers: {', '.join(missing_headers)}")
                if weak_headers:
                    details.append(f"Weak headers: {', '.join(weak_headers)}")
                
                self.add_result(
                    "Security Headers",
                    False,
                    "; ".join(details),
                    "high",
                    "Configure security headers in Nginx and Django settings"
                )
                return False
            else:
                self.add_result(
                    "Security Headers",
                    True,
                    "All required security headers are present",
                    "low"
                )
                return True
                
        except Exception as e:
            self.add_result(
                "Security Headers",
                False,
                f"Failed to test security headers: {e}",
                "medium"
            )
            return False
    
    def test_csrf_protection(self) -> bool:
        """Test CSRF protection."""
        try:
            # Try to make a POST request without CSRF token
            response = requests.post(f"{self.base_url}/admin/login/", 
                                   data={'username': 'test', 'password': 'test'}, 
                                   timeout=10)
            
            # Should get CSRF error or forbidden
            if response.status_code == 403 or 'csrf' in response.text.lower():
                self.add_result(
                    "CSRF Protection",
                    True,
                    "CSRF protection is active",
                    "low"
                )
                return True
            else:
                self.add_result(
                    "CSRF Protection",
                    False,
                    f"CSRF protection may be disabled (status: {response.status_code})",
                    "high",
                    "Ensure CSRF middleware is enabled in Django settings"
                )
                return False
                
        except Exception as e:
            self.add_result(
                "CSRF Protection",
                False,
                f"Failed to test CSRF protection: {e}",
                "medium"
            )
            return False
    
    def test_https_enforcement(self) -> bool:
        """Test HTTPS enforcement (if applicable)."""
        try:
            # Check if HTTPS redirect is configured
            if self.base_url.startswith('http://'):
                https_url = self.base_url.replace('http://', 'https://')
                try:
                    response = requests.get(https_url, timeout=10, verify=False)
                    if response.status_code == 200:
                        self.add_result(
                            "HTTPS Enforcement",
                            True,
                            "HTTPS is available",
                            "low"
                        )
                        return True
                except:
                    pass
            
            # Check for HTTPS-related headers
            response = requests.get(self.base_url, timeout=10)
            
            # Check for HSTS header (indicates HTTPS enforcement)
            if 'Strict-Transport-Security' in response.headers:
                self.add_result(
                    "HTTPS Enforcement",
                    True,
                    "HSTS header present, HTTPS enforcement configured",
                    "low"
                )
                return True
            else:
                self.add_result(
                    "HTTPS Enforcement",
                    False,
                    "No HTTPS enforcement detected",
                    "medium",
                    "Configure HTTPS and HSTS headers for production"
                )
                return False
                
        except Exception as e:
            self.add_result(
                "HTTPS Enforcement",
                False,
                f"Failed to test HTTPS enforcement: {e}",
                "medium"
            )
            return False
    
    def test_admin_interface_security(self) -> bool:
        """Test admin interface security."""
        try:
            # Check if admin interface is accessible
            response = requests.get(f"{self.base_url}/admin/", timeout=10)
            
            # Admin should require authentication
            if response.status_code == 200 and 'login' in response.text.lower():
                self.add_result(
                    "Admin Interface Security",
                    True,
                    "Admin interface requires authentication",
                    "low"
                )
                return True
            elif response.status_code == 404:
                self.add_result(
                    "Admin Interface Security",
                    True,
                    "Admin interface is not exposed (404)",
                    "low"
                )
                return True
            else:
                self.add_result(
                    "Admin Interface Security",
                    False,
                    f"Admin interface may be unsecured (status: {response.status_code})",
                    "high",
                    "Ensure admin interface requires authentication"
                )
                return False
                
        except Exception as e:
            self.add_result(
                "Admin Interface Security",
                False,
                f"Failed to test admin interface: {e}",
                "medium"
            )
            return False
    
    def test_information_disclosure(self) -> bool:
        """Test for information disclosure vulnerabilities."""
        try:
            # Test various endpoints for information disclosure
            test_paths = [
                '/.env',
                '/settings.py',
                '/config/',
                '/debug/',
                '/server-status',
                '/server-info',
                '/.git/',
                '/backup/',
                '/logs/',
            ]
            
            disclosed_paths = []
            
            for path in test_paths:
                try:
                    response = requests.get(f"{self.base_url}{path}", timeout=5)
                    if response.status_code == 200 and len(response.content) > 100:
                        disclosed_paths.append(path)
                except:
                    continue
            
            if disclosed_paths:
                self.add_result(
                    "Information Disclosure",
                    False,
                    f"Sensitive paths accessible: {', '.join(disclosed_paths)}",
                    "high",
                    "Block access to sensitive files and directories"
                )
                return False
            else:
                self.add_result(
                    "Information Disclosure",
                    True,
                    "No sensitive information disclosed",
                    "low"
                )
                return True
                
        except Exception as e:
            self.add_result(
                "Information Disclosure",
                False,
                f"Failed to test information disclosure: {e}",
                "medium"
            )
            return False
    
    def test_sql_injection_basic(self) -> bool:
        """Basic SQL injection test on RAG endpoints."""
        try:
            # Test SQL injection payloads on RAG query endpoint
            sql_payloads = [
                "' OR '1'='1",
                "'; DROP TABLE users; --",
                "' UNION SELECT * FROM users --",
                "admin'--",
                "' OR 1=1 --"
            ]
            
            vulnerable = False
            
            for payload in sql_payloads:
                try:
                    response = requests.post(
                        f"{self.base_url}/api/rag/query/",
                        json={"query": payload},
                        timeout=10
                    )
                    
                    # Check for SQL error messages
                    error_indicators = [
                        'sql syntax',
                        'mysql error',
                        'postgresql error',
                        'sqlite error',
                        'database error',
                        'syntax error'
                    ]
                    
                    response_text = response.text.lower()
                    if any(indicator in response_text for indicator in error_indicators):
                        vulnerable = True
                        break
                        
                except:
                    continue
            
            if vulnerable:
                self.add_result(
                    "SQL Injection Protection",
                    False,
                    "Potential SQL injection vulnerability detected",
                    "critical",
                    "Use parameterized queries and input validation"
                )
                return False
            else:
                self.add_result(
                    "SQL Injection Protection",
                    True,
                    "No SQL injection vulnerabilities detected",
                    "low"
                )
                return True
                
        except Exception as e:
            self.add_result(
                "SQL Injection Protection",
                False,
                f"Failed to test SQL injection: {e}",
                "medium"
            )
            return False
    
    def test_rate_limiting(self) -> bool:
        """Test rate limiting implementation."""
        try:
            # Make rapid requests to test rate limiting
            rapid_requests = 50
            blocked_count = 0
            
            for i in range(rapid_requests):
                try:
                    response = requests.get(f"{self.base_url}/api/rag/query/", timeout=2)
                    if response.status_code == 429:  # Too Many Requests
                        blocked_count += 1
                except:
                    continue
            
            if blocked_count > 0:
                self.add_result(
                    "Rate Limiting",
                    True,
                    f"Rate limiting active ({blocked_count}/{rapid_requests} requests blocked)",
                    "low"
                )
                return True
            else:
                self.add_result(
                    "Rate Limiting",
                    False,
                    "No rate limiting detected",
                    "medium",
                    "Implement rate limiting to prevent abuse"
                )
                return False
                
        except Exception as e:
            self.add_result(
                "Rate Limiting",
                False,
                f"Failed to test rate limiting: {e}",
                "medium"
            )
            return False
    
    def test_docker_security(self) -> bool:
        """Test Docker container security configurations."""
        try:
            # Check if running as non-root user
            result = subprocess.run([
                "docker-compose", "exec", "-T", "app", "whoami"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                user = result.stdout.strip()
                if user != 'root':
                    self.add_result(
                        "Docker Security",
                        True,
                        f"Application running as non-root user: {user}",
                        "low"
                    )
                    return True
                else:
                    self.add_result(
                        "Docker Security",
                        False,
                        "Application running as root user",
                        "high",
                        "Configure container to run as non-root user"
                    )
                    return False
            else:
                self.add_result(
                    "Docker Security",
                    False,
                    "Failed to check container user",
                    "medium"
                )
                return False
                
        except Exception as e:
            self.add_result(
                "Docker Security",
                False,
                f"Failed to test Docker security: {e}",
                "medium"
            )
            return False
    
    def test_environment_variable_security(self) -> bool:
        """Test environment variable security."""
        try:
            # Check if sensitive environment variables are exposed
            response = requests.get(f"{self.base_url}/health/", timeout=10)
            
            # Look for exposed environment variables in response
            sensitive_patterns = [
                'SECRET_KEY',
                'DATABASE_URL',
                'GEMINI_API_KEY',
                'PASSWORD',
                'TOKEN'
            ]
            
            response_text = response.text
            exposed_vars = [pattern for pattern in sensitive_patterns 
                          if pattern in response_text]
            
            if exposed_vars:
                self.add_result(
                    "Environment Variable Security",
                    False,
                    f"Sensitive variables may be exposed: {', '.join(exposed_vars)}",
                    "critical",
                    "Ensure sensitive environment variables are not logged or exposed"
                )
                return False
            else:
                self.add_result(
                    "Environment Variable Security",
                    True,
                    "No sensitive environment variables exposed",
                    "low"
                )
                return True
                
        except Exception as e:
            self.add_result(
                "Environment Variable Security",
                False,
                f"Failed to test environment variable security: {e}",
                "medium"
            )
            return False
    
    def run_all_tests(self) -> Dict:
        """Run all security tests."""
        print("🔒 Starting security validation tests...")
        print("=" * 60)
        
        tests = [
            ("Debug Mode", self.test_debug_mode_disabled),
            ("Security Headers", self.test_security_headers),
            ("CSRF Protection", self.test_csrf_protection),
            ("HTTPS Enforcement", self.test_https_enforcement),
            ("Admin Interface", self.test_admin_interface_security),
            ("Information Disclosure", self.test_information_disclosure),
            ("SQL Injection", self.test_sql_injection_basic),
            ("Rate Limiting", self.test_rate_limiting),
            ("Docker Security", self.test_docker_security),
            ("Environment Variables", self.test_environment_variable_security),
        ]
        
        for test_name, test_func in tests:
            print(f"Running {test_name} test...")
            try:
                test_func()
            except Exception as e:
                self.add_result(
                    test_name,
                    False,
                    f"Test crashed: {e}",
                    "medium"
                )
        
        return self.generate_report()
    
    def generate_report(self) -> Dict:
        """Generate security test report."""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.passed)
        failed_tests = total_tests - passed_tests
        
        # Categorize by severity
        severity_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        failed_by_severity = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        
        for result in self.results:
            severity_counts[result.severity] += 1
            if not result.passed:
                failed_by_severity[result.severity] += 1
        
        # Calculate risk score (weighted by severity)
        severity_weights = {"low": 1, "medium": 2, "high": 4, "critical": 8}
        max_score = sum(severity_weights[sev] * count for sev, count in severity_counts.items())
        current_score = sum(severity_weights[sev] * count for sev, count in failed_by_severity.items())
        risk_score = (current_score / max_score * 100) if max_score > 0 else 0
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "risk_score": risk_score
            },
            "severity_breakdown": {
                "total": severity_counts,
                "failed": failed_by_severity
            },
            "test_results": [asdict(result) for result in self.results],
            "recommendations": [
                result.recommendation for result in self.results 
                if not result.passed and result.recommendation
            ]
        }

def print_security_report(report: Dict):
    """Print formatted security report."""
    print("\n" + "=" * 80)
    print("SECURITY VALIDATION REPORT")
    print("=" * 80)
    
    summary = report["summary"]
    print(f"\nTest Summary:")
    print(f"  Total Tests: {summary['total_tests']}")
    print(f"  Passed: {summary['passed']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Success Rate: {summary['success_rate']:.1f}%")
    print(f"  Risk Score: {summary['risk_score']:.1f}%")
    
    # Risk assessment
    risk_score = summary['risk_score']
    if risk_score == 0:
        risk_level = "🟢 LOW"
    elif risk_score < 25:
        risk_level = "🟡 MEDIUM"
    elif risk_score < 50:
        risk_level = "🟠 HIGH"
    else:
        risk_level = "🔴 CRITICAL"
    
    print(f"  Risk Level: {risk_level}")
    
    # Severity breakdown
    severity = report["severity_breakdown"]
    print(f"\nSeverity Breakdown:")
    for level in ["critical", "high", "medium", "low"]:
        total = severity["total"][level]
        failed = severity["failed"][level]
        if total > 0:
            print(f"  {level.upper()}: {failed}/{total} failed")
    
    # Failed tests
    failed_tests = [result for result in report["test_results"] if not result["passed"]]
    if failed_tests:
        print(f"\nFailed Tests:")
        for test in failed_tests:
            severity_icon = {
                "low": "🟡",
                "medium": "🟠", 
                "high": "🔴",
                "critical": "💀"
            }.get(test["severity"], "❓")
            
            print(f"  {severity_icon} {test['test_name']}: {test['details']}")
    
    # Recommendations
    if report["recommendations"]:
        print(f"\nSecurity Recommendations:")
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"  {i}. {rec}")
    
    # Overall assessment
    print(f"\nOverall Security Assessment:")
    if summary['success_rate'] >= 90 and risk_score < 25:
        print("  ✅ Security configuration is good")
    elif summary['success_rate'] >= 75 and risk_score < 50:
        print("  ⚠️ Security configuration needs improvement")
    else:
        print("  ❌ Security configuration has significant issues")

def main():
    """Main function to run security validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate security configuration')
    parser.add_argument('--url', default='http://localhost:8000', help='Base URL for testing')
    parser.add_argument('--output', help='Output file for detailed results (JSON)')
    
    args = parser.parse_args()
    
    validator = SecurityValidator(args.url)
    
    try:
        report = validator.run_all_tests()
        
        # Print report
        print_security_report(report)
        
        # Save detailed results if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\nDetailed results saved to: {args.output}")
        
        # Exit with appropriate code
        success_rate = report['summary']['success_rate']
        risk_score = report['summary']['risk_score']
        
        if success_rate >= 90 and risk_score < 25:
            print("\n🎉 Security validation PASSED")
            return 0
        else:
            print("\n❌ Security validation FAILED")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ Security validation interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Security validation failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())