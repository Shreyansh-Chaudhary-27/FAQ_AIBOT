#!/usr/bin/env python3
"""
Backup and restore procedure testing script.
Tests the reliability and integrity of backup and restore operations.
"""

import os
import sys
import json
import time
import shutil
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict

@dataclass
class BackupTestResult:
    """Result of a backup/restore test."""
    test_name: str
    success: bool
    details: str
    duration: float
    backup_size: Optional[int] = None
    error_message: Optional[str] = None

class BackupRestoreTester:
    """Backup and restore testing framework."""
    
    def __init__(self, backup_dir: str = "./backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.results: List[BackupTestResult] = []
        self.test_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def add_result(self, test_name: str, success: bool, details: str, 
                   duration: float, backup_size: int = None, error_message: str = None):
        """Add a test result."""
        self.results.append(BackupTestResult(
            test_name=test_name,
            success=success,
            details=details,
            duration=duration,
            backup_size=backup_size,
            error_message=error_message
        ))
    
    def test_database_backup(self) -> bool:
        """Test PostgreSQL database backup."""
        start_time = time.time()
        
        try:
            backup_file = self.backup_dir / f"db_backup_{self.test_timestamp}.sql"
            
            # Create database backup using pg_dump
            cmd = [
                "docker-compose", "exec", "-T", "db",
                "pg_dump", "-U", "faq_user", "-d", "faq_production",
                "--no-password", "--verbose"
            ]
            
            with open(backup_file, 'w') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, 
                                      text=True, timeout=300)
            
            duration = time.time() - start_time
            
            if result.returncode == 0 and backup_file.exists():
                backup_size = backup_file.stat().st_size
                
                # Verify backup contains expected content
                with open(backup_file, 'r') as f:
                    content = f.read(1000)  # Read first 1KB
                
                if "PostgreSQL database dump" in content and backup_size > 1000:
                    self.add_result(
                        "Database Backup",
                        True,
                        f"Database backup created successfully ({backup_size} bytes)",
                        duration,
                        backup_size
                    )
                    return True
                else:
                    self.add_result(
                        "Database Backup",
                        False,
                        "Backup file created but appears invalid",
                        duration,
                        backup_size,
                        "Invalid backup content"
                    )
                    return False
            else:
                self.add_result(
                    "Database Backup",
                    False,
                    f"Backup failed: {result.stderr}",
                    duration,
                    error_message=result.stderr
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.add_result(
                "Database Backup",
                False,
                f"Backup test failed: {e}",
                duration,
                error_message=str(e)
            )
            return False
    
    def test_database_restore(self) -> bool:
        """Test PostgreSQL database restore."""
        start_time = time.time()
        
        try:
            # Find the most recent backup file
            backup_files = list(self.backup_dir.glob(f"db_backup_{self.test_timestamp}.sql"))
            if not backup_files:
                duration = time.time() - start_time
                self.add_result(
                    "Database Restore",
                    False,
                    "No backup file found for restore test",
                    duration,
                    error_message="Missing backup file"
                )
                return False
            
            backup_file = backup_files[0]
            
            # Create a test database for restore
            test_db_name = f"faq_test_restore_{self.test_timestamp}"
            
            # Create test database
            create_db_cmd = [
                "docker-compose", "exec", "-T", "db",
                "createdb", "-U", "faq_user", test_db_name
            ]
            
            result = subprocess.run(create_db_cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                duration = time.time() - start_time
                self.add_result(
                    "Database Restore",
                    False,
                    f"Failed to create test database: {result.stderr}",
                    duration,
                    error_message=result.stderr
                )
                return False
            
            # Restore backup to test database
            with open(backup_file, 'r') as f:
                restore_cmd = [
                    "docker-compose", "exec", "-T", "db",
                    "psql", "-U", "faq_user", "-d", test_db_name
                ]
                
                result = subprocess.run(restore_cmd, stdin=f, capture_output=True, 
                                      text=True, timeout=300)
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                # Verify restore by checking table count
                check_cmd = [
                    "docker-compose", "exec", "-T", "db",
                    "psql", "-U", "faq_user", "-d", test_db_name,
                    "-c", "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"
                ]
                
                check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=30)
                
                if check_result.returncode == 0 and "0" not in check_result.stdout:
                    self.add_result(
                        "Database Restore",
                        True,
                        f"Database restored successfully to {test_db_name}",
                        duration
                    )
                    
                    # Clean up test database
                    cleanup_cmd = [
                        "docker-compose", "exec", "-T", "db",
                        "dropdb", "-U", "faq_user", test_db_name
                    ]
                    subprocess.run(cleanup_cmd, capture_output=True, timeout=30)
                    
                    return True
                else:
                    self.add_result(
                        "Database Restore",
                        False,
                        "Restore completed but no tables found",
                        duration,
                        error_message="Empty restore result"
                    )
                    return False
            else:
                self.add_result(
                    "Database Restore",
                    False,
                    f"Restore failed: {result.stderr}",
                    duration,
                    error_message=result.stderr
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.add_result(
                "Database Restore",
                False,
                f"Restore test failed: {e}",
                duration,
                error_message=str(e)
            )
            return False
    
    def test_vector_database_backup(self) -> bool:
        """Test Qdrant vector database backup."""
        start_time = time.time()
        
        try:
            backup_file = self.backup_dir / f"qdrant_backup_{self.test_timestamp}.tar.gz"
            
            # Create Qdrant data backup
            cmd = [
                "docker-compose", "exec", "-T", "qdrant",
                "tar", "-czf", "/tmp/qdrant_backup.tar.gz", "/qdrant/storage"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                # Copy backup file from container
                copy_cmd = [
                    "docker", "cp", 
                    f"{subprocess.check_output(['docker-compose', 'ps', '-q', 'qdrant']).decode().strip()}:/tmp/qdrant_backup.tar.gz",
                    str(backup_file)
                ]
                
                copy_result = subprocess.run(copy_cmd, capture_output=True, text=True, timeout=60)
                
                duration = time.time() - start_time
                
                if copy_result.returncode == 0 and backup_file.exists():
                    backup_size = backup_file.stat().st_size
                    self.add_result(
                        "Vector Database Backup",
                        True,
                        f"Qdrant backup created successfully ({backup_size} bytes)",
                        duration,
                        backup_size
                    )
                    return True
                else:
                    self.add_result(
                        "Vector Database Backup",
                        False,
                        f"Failed to copy backup file: {copy_result.stderr}",
                        duration,
                        error_message=copy_result.stderr
                    )
                    return False
            else:
                duration = time.time() - start_time
                self.add_result(
                    "Vector Database Backup",
                    False,
                    f"Qdrant backup failed: {result.stderr}",
                    duration,
                    error_message=result.stderr
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.add_result(
                "Vector Database Backup",
                False,
                f"Vector backup test failed: {e}",
                duration,
                error_message=str(e)
            )
            return False
    
    def test_application_data_backup(self) -> bool:
        """Test application data and configuration backup."""
        start_time = time.time()
        
        try:
            backup_file = self.backup_dir / f"app_data_backup_{self.test_timestamp}.tar.gz"
            
            # Create application data backup
            backup_paths = [
                ".env",
                "faq/static/",
                "logs/",
                "vector_store_data/",
                "system_improvement_data/"
            ]
            
            # Filter existing paths
            existing_paths = [path for path in backup_paths if Path(path).exists()]
            
            if existing_paths:
                cmd = ["tar", "-czf", str(backup_file)] + existing_paths
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                duration = time.time() - start_time
                
                if result.returncode == 0 and backup_file.exists():
                    backup_size = backup_file.stat().st_size
                    self.add_result(
                        "Application Data Backup",
                        True,
                        f"Application data backup created ({backup_size} bytes)",
                        duration,
                        backup_size
                    )
                    return True
                else:
                    self.add_result(
                        "Application Data Backup",
                        False,
                        f"Backup creation failed: {result.stderr}",
                        duration,
                        error_message=result.stderr
                    )
                    return False
            else:
                duration = time.time() - start_time
                self.add_result(
                    "Application Data Backup",
                    False,
                    "No application data found to backup",
                    duration,
                    error_message="Missing data directories"
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.add_result(
                "Application Data Backup",
                False,
                f"Application backup test failed: {e}",
                duration,
                error_message=str(e)
            )
            return False
    
    def test_backup_integrity(self) -> bool:
        """Test backup file integrity."""
        start_time = time.time()
        
        try:
            # Check all backup files created in this test session
            backup_files = list(self.backup_dir.glob(f"*_{self.test_timestamp}.*"))
            
            if not backup_files:
                duration = time.time() - start_time
                self.add_result(
                    "Backup Integrity",
                    False,
                    "No backup files found for integrity check",
                    duration,
                    error_message="Missing backup files"
                )
                return False
            
            integrity_results = []
            
            for backup_file in backup_files:
                if backup_file.suffix == '.sql':
                    # Check SQL backup integrity
                    try:
                        with open(backup_file, 'r') as f:
                            content = f.read()
                        
                        if "PostgreSQL database dump" in content and content.strip().endswith("-- PostgreSQL database dump complete"):
                            integrity_results.append(f"{backup_file.name}: Valid SQL backup")
                        else:
                            integrity_results.append(f"{backup_file.name}: Invalid SQL backup")
                    except Exception as e:
                        integrity_results.append(f"{backup_file.name}: Read error - {e}")
                
                elif backup_file.suffix == '.gz':
                    # Check compressed file integrity
                    cmd = ["gzip", "-t", str(backup_file)]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 0:
                        integrity_results.append(f"{backup_file.name}: Valid compressed file")
                    else:
                        integrity_results.append(f"{backup_file.name}: Corrupted compressed file")
            
            duration = time.time() - start_time
            
            # Check if all files passed integrity check
            failed_checks = [result for result in integrity_results if "Invalid" in result or "Corrupted" in result or "error" in result]
            
            if not failed_checks:
                self.add_result(
                    "Backup Integrity",
                    True,
                    f"All backup files passed integrity check: {'; '.join(integrity_results)}",
                    duration
                )
                return True
            else:
                self.add_result(
                    "Backup Integrity",
                    False,
                    f"Some backups failed integrity check: {'; '.join(failed_checks)}",
                    duration,
                    error_message="Integrity check failures"
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.add_result(
                "Backup Integrity",
                False,
                f"Integrity check failed: {e}",
                duration,
                error_message=str(e)
            )
            return False
    
    def test_backup_automation(self) -> bool:
        """Test automated backup script functionality."""
        start_time = time.time()
        
        try:
            # Test the backup script
            if Path("scripts/backup.sh").exists():
                cmd = ["./scripts/backup.sh", "--test-mode"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                
                duration = time.time() - start_time
                
                if result.returncode == 0:
                    self.add_result(
                        "Backup Automation",
                        True,
                        "Automated backup script executed successfully",
                        duration
                    )
                    return True
                else:
                    self.add_result(
                        "Backup Automation",
                        False,
                        f"Backup script failed: {result.stderr}",
                        duration,
                        error_message=result.stderr
                    )
                    return False
            else:
                duration = time.time() - start_time
                self.add_result(
                    "Backup Automation",
                    False,
                    "Backup script not found",
                    duration,
                    error_message="Missing backup script"
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.add_result(
                "Backup Automation",
                False,
                f"Backup automation test failed: {e}",
                duration,
                error_message=str(e)
            )
            return False
    
    def run_all_tests(self) -> Dict:
        """Run all backup and restore tests."""
        print("💾 Starting backup and restore procedure tests...")
        print("=" * 60)
        
        tests = [
            ("Database Backup", self.test_database_backup),
            ("Vector Database Backup", self.test_vector_database_backup),
            ("Application Data Backup", self.test_application_data_backup),
            ("Backup Integrity", self.test_backup_integrity),
            ("Database Restore", self.test_database_restore),
            ("Backup Automation", self.test_backup_automation),
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
                    0.0,
                    error_message=str(e)
                )
        
        return self.generate_report()
    
    def generate_report(self) -> Dict:
        """Generate backup/restore test report."""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - passed_tests
        
        total_duration = sum(r.duration for r in self.results)
        total_backup_size = sum(r.backup_size for r in self.results if r.backup_size)
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "total_duration": total_duration,
                "total_backup_size": total_backup_size
            },
            "test_results": [asdict(result) for result in self.results],
            "backup_files": list(str(f) for f in self.backup_dir.glob(f"*_{self.test_timestamp}.*")),
            "recommendations": self.generate_recommendations()
        }
    
    def generate_recommendations(self) -> List[str]:
        """Generate backup/restore recommendations."""
        recommendations = []
        
        failed_tests = [r for r in self.results if not r.success]
        
        if any("Database Backup" in r.test_name for r in failed_tests):
            recommendations.append("Fix database backup issues before production deployment")
        
        if any("Vector Database Backup" in r.test_name for r in failed_tests):
            recommendations.append("Ensure Qdrant vector database backup procedures work correctly")
        
        if any("Restore" in r.test_name for r in failed_tests):
            recommendations.append("Test and fix restore procedures - critical for disaster recovery")
        
        if any("Integrity" in r.test_name for r in failed_tests):
            recommendations.append("Backup integrity issues detected - verify backup processes")
        
        if any("Automation" in r.test_name for r in failed_tests):
            recommendations.append("Fix automated backup scripts for reliable scheduled backups")
        
        # Performance recommendations
        slow_tests = [r for r in self.results if r.duration > 60]  # > 1 minute
        if slow_tests:
            recommendations.append("Consider optimizing backup procedures for better performance")
        
        if not recommendations:
            recommendations.append("All backup and restore procedures are working correctly")
        
        return recommendations

def print_backup_report(report: Dict):
    """Print formatted backup/restore report."""
    print("\n" + "=" * 80)
    print("BACKUP AND RESTORE TEST REPORT")
    print("=" * 80)
    
    summary = report["summary"]
    print(f"\nTest Summary:")
    print(f"  Total Tests: {summary['total_tests']}")
    print(f"  Passed: {summary['passed']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Success Rate: {summary['success_rate']:.1f}%")
    print(f"  Total Duration: {summary['total_duration']:.1f} seconds")
    print(f"  Total Backup Size: {summary['total_backup_size']} bytes ({summary['total_backup_size'] / 1024 / 1024:.1f} MB)")
    
    # Test results
    print(f"\nTest Results:")
    for result in report["test_results"]:
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        print(f"  {status} {result['test_name']}: {result['details']}")
        if result["duration"] > 0:
            print(f"    Duration: {result['duration']:.1f}s")
        if result["backup_size"]:
            print(f"    Size: {result['backup_size']} bytes ({result['backup_size'] / 1024 / 1024:.1f} MB)")
        if not result["success"] and result["error_message"]:
            print(f"    Error: {result['error_message']}")
    
    # Backup files created
    if report["backup_files"]:
        print(f"\nBackup Files Created:")
        for backup_file in report["backup_files"]:
            print(f"  📁 {backup_file}")
    
    # Recommendations
    if report["recommendations"]:
        print(f"\nRecommendations:")
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"  {i}. {rec}")

def main():
    """Main function to run backup/restore testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test backup and restore procedures')
    parser.add_argument('--backup-dir', default='./backups', help='Backup directory')
    parser.add_argument('--output', help='Output file for detailed results (JSON)')
    parser.add_argument('--cleanup', action='store_true', help='Clean up test backup files after testing')
    
    args = parser.parse_args()
    
    tester = BackupRestoreTester(args.backup_dir)
    
    try:
        report = tester.run_all_tests()
        
        # Print report
        print_backup_report(report)
        
        # Save detailed results if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\nDetailed results saved to: {args.output}")
        
        # Cleanup test files if requested
        if args.cleanup:
            for backup_file in report["backup_files"]:
                try:
                    Path(backup_file).unlink()
                    print(f"Cleaned up: {backup_file}")
                except:
                    pass
        
        # Exit with appropriate code
        success_rate = report['summary']['success_rate']
        
        if success_rate >= 80:  # Allow some tolerance for backup/restore tests
            print("\n🎉 Backup/restore tests PASSED")
            return 0
        else:
            print("\n❌ Backup/restore tests FAILED")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ Backup/restore tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Backup/restore tests failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())